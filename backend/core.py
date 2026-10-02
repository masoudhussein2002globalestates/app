import os
import uuid
import logging
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from fastapi import HTTPException

load_dotenv(Path(__file__).parent / '.env')
client = AsyncIOMotorClient(os.environ['MONGO_URL'], serverSelectionTimeoutMS=5000)
db = client[os.environ['DB_NAME']]
log = logging.getLogger('global-estates')

def now():
    return datetime.now(timezone.utc)

def uid():
    return uuid.uuid4().hex

def authorize(user, action, resource=None):
    allowed = {'property.create', 'property.edit', 'property.delete', 'property.plan', 'booking.payout', 'booking.view', 'inquiry.view'}
    permitted = bool(user and action in allowed)
    if resource is not None:
        permitted = permitted and resource.get('host_id') == user['user_id']
    log.info('authorization user=%s action=%s allowed=%s', user.get('user_id') if user else None, action, permitted)
    if not permitted:
        raise HTTPException(404 if resource is not None else 403, 'Record not found' if resource is not None else 'Permission denied')

async def owned_property(property_id, user, action):
    doc = await db.properties.find_one({'id': property_id, 'host_id': user['user_id'], 'status': {'$ne': 'deleted'}}, {'_id': 0})
    if not doc:
        raise HTTPException(404, 'Property not found')
    authorize(user, action, doc)
    return doc

COUNTRIES = ['Kenya','Uganda','Tanzania','Rwanda','Nigeria','Ghana','South Africa','United States','United Kingdom','Canada','Australia','United Arab Emirates','Germany','France','Italy','Spain','India','Argentina','Austria','Belgium','Botswana','Brazil','Cameroon','Chile','China','Colombia','Costa Rica','Croatia','Cyprus','Czechia','Denmark','Egypt','Ethiopia','Finland','Greece','Hungary','Indonesia','Ireland','Israel','Jamaica','Japan','Jordan','Malaysia','Maldives','Malta','Mauritius','Mexico','Morocco','Mozambique','Namibia','Nepal','Netherlands','New Zealand','Norway','Oman','Pakistan','Peru','Philippines','Poland','Portugal','Qatar','Saudi Arabia','Senegal','Seychelles','Singapore','South Korea','Sri Lanka','Sweden','Switzerland','Thailand','Tunisia','Turkey','Vietnam','Zambia','Zimbabwe']