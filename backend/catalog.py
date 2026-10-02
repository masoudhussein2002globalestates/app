import math
import re
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from core import db, uid, now, authorize, owned_property, COUNTRIES
from auth import current_user
from models import PropertyInput, PropertyOut, PropertyList

router = APIRouter(prefix='/api', tags=['Properties'])

@router.get('/properties', response_model=PropertyList)
async def properties(location: str = Query('', max_length=120), country: str = '', category: str = '', minPrice: float = Query(0, ge=0), maxPrice: float | None = Query(None, ge=0), bedrooms: int = Query(0, ge=0), guests: int = Query(0, ge=0), sort: str = 'newest', page: int = Query(1, ge=1), limit: int = Query(12, ge=1, le=60)):
    query = {'status': 'active'}
    if location.strip():
        pattern = {'$regex': re.escape(location.strip()), '$options': 'i'}
        query['$or'] = [{'location': pattern}, {'title': pattern}, {'country': pattern}]
    if country:
        query['country'] = country
    if category and category != 'All':
        if category not in ['Rent', 'Vacation', 'Outings', 'Land']:
            raise HTTPException(422, 'Choose a valid category.')
        query['category'] = category
    query['price'] = {'$gte': minPrice}
    if maxPrice is not None:
        if maxPrice < minPrice:
            raise HTTPException(422, 'Maximum price must be at least the minimum price.')
        query['price']['$lte'] = maxPrice
    if bedrooms:
        query['bedrooms'] = {'$gte': bedrooms}
    if guests:
        query['guests'] = {'$gte': guests}
    order = [('price', 1), ('created_at', -1)] if sort == 'price_asc' else [('price', -1), ('created_at', -1)] if sort == 'price_desc' else [('created_at', -1)]
    if sort == 'recommended':
        order = [('plan_rank', -1), ('created_at', -1)]
    total = await db.properties.count_documents(query)
    docs = await db.properties.find(query, {'_id': 0, 'contact_email': 0}).sort(order).skip((page-1)*limit).limit(limit).to_list(limit)
    return PropertyList(properties=[PropertyOut(**p) for p in docs], total=total, page=page, pages=math.ceil(total/limit))

@router.post('/properties', response_model=PropertyOut, status_code=201)
async def create_property(body: PropertyInput, user=Depends(current_user)):
    authorize(user, 'property.create')
    if body.country not in COUNTRIES:
        raise HTTPException(422, 'Please choose a supported country.')
    if body.category == 'Land' and not body.size:
        raise HTTPException(422, 'Please enter the land size.')
    doc = {**body.model_dump(), 'id': uid(), 'host_id': user['user_id'], 'host_name': user['name'], 'listing_plan': 'Free', 'plan_rank': 0, 'is_sample': False, 'created_at': now().isoformat()}
    await db.properties.insert_one(doc.copy())
    await db.hosts.update_one({'user_id': user['user_id']}, {'$setOnInsert': {'name': user['name'], 'email': user['email'], 'stripe_account_id': '', 'onboarding_status': 'not_started'}}, upsert=True)
    return PropertyOut(**doc)

@router.get('/properties/{property_id}', response_model=PropertyOut)
async def get_property(property_id: str):
    doc = await db.properties.find_one({'id': property_id, 'status': 'active'}, {'_id': 0, 'contact_email': 0})
    if not doc:
        raise HTTPException(404, 'Property not found or no longer available.')
    return PropertyOut(**doc)

@router.put('/properties/{property_id}', response_model=PropertyOut)
async def edit_property(property_id: str, body: PropertyInput, user=Depends(current_user)):
    doc = await owned_property(property_id, user, 'property.edit')
    if body.country not in COUNTRIES or (body.category == 'Land' and not body.size):
        raise HTTPException(422, 'Choose a valid country and include the land size where applicable.')
    await db.properties.update_one({'id': property_id, 'host_id': user['user_id']}, {'$set': body.model_dump()})
    return PropertyOut(**{**doc, **body.model_dump()})

@router.delete('/properties/{property_id}')
async def delete_property(property_id: str, user=Depends(current_user)):
    await owned_property(property_id, user, 'property.delete')
    if await db.bookings.count_documents({'property_id': property_id, 'payment_status': {'$in': ['paid','pending']}, 'check_out': {'$gte': now().date().isoformat()}}):
        raise HTTPException(409, 'This property has upcoming bookings. Pause the listing instead.')
    await db.properties.update_one({'id': property_id, 'host_id': user['user_id']}, {'$set': {'status': 'deleted'}})
    return {'message': 'Property deleted.'}

@router.get('/favorites', response_model=list[PropertyOut])
async def favorites(user=Depends(current_user)):
    docs = await db.favorites.find({'user_id': user['user_id']}, {'_id': 0}).to_list(1000)
    props = await db.properties.find({'id': {'$in': [d['property_id'] for d in docs]}, 'status': 'active'}, {'_id': 0, 'contact_email': 0}).to_list(1000)
    return [PropertyOut(**p) for p in props]

@router.put('/favorites/{property_id}')
async def save_favorite(property_id: str, user=Depends(current_user)):
    await get_property(property_id)
    await db.favorites.update_one({'user_id': user['user_id'], 'property_id': property_id}, {'$setOnInsert': {'created_at': now().isoformat()}}, upsert=True)
    return {'saved': True}

@router.delete('/favorites/{property_id}')
async def remove_favorite(property_id: str, user=Depends(current_user)):
    await db.favorites.delete_one({'user_id': user['user_id'], 'property_id': property_id})
    return {'saved': False}

class Inquiry(BaseModel):
    message: str = Field(min_length=10, max_length=3000)

@router.post('/properties/{property_id}/inquiries', status_code=201)
async def contact(property_id: str, body: Inquiry, user=Depends(current_user)):
    prop = await get_property(property_id)
    if prop.is_sample:
        raise HTTPException(409, 'Sample listings cannot receive inquiries.')
    if prop.host_id == user['user_id']:
        raise HTTPException(409, 'This is your own property.')
    await db.inquiries.insert_one({'id': uid(), 'property_id': property_id, 'property_title': prop.title, 'host_id': prop.host_id, 'customer_id': user['user_id'], 'customer_name': user['name'], 'customer_email': user['email'], 'message': body.message, 'created_at': now().isoformat()})
    return {'message': 'Your message was delivered to the owner’s inbox.'}