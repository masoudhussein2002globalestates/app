import os
import uuid
import logging
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from fastapi import HTTPException

load_dotenv(Path(__file__).parent / '.env')
MONGO_URL = os.environ.get('MONGO_URL') or os.environ.get('MONGODB_URL') or 'mongodb://localhost:27017'
DB_NAME = os.environ.get('DB_NAME') or 'global_estates'
client = AsyncIOMotorClient(MONGO_URL, serverSelectionTimeoutMS=5000)
db = client[DB_NAME]
log = logging.getLogger('global-estates')

COUNTRIES = ['Kenya','Uganda','Tanzania','Rwanda','Nigeria','Ghana','South Africa','Ethiopia','United States','United Kingdom','Canada','Australia','United Arab Emirates','Saudi Arabia','Qatar','India','China','France','Germany','Italy','Spain','United Arab Emirates']

PROPERTY_CATEGORIES = ['Rent','Vacation','Outings','Land','Buy Property']


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
