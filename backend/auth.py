import secrets
import hashlib
import bcrypt
import httpx
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field, EmailStr
from pymongo.errors import DuplicateKeyError
from core import db, now, uid
from models import UserOut

router = APIRouter(prefix='/api/auth', tags=['Authentication'])

class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    name: str = Field(default='', max_length=100)

class GoogleSession(BaseModel):
    session_id: str = Field(min_length=5, max_length=2000)

def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()

async def current_user(request: Request):
    token = request.cookies.get('session_token') or request.headers.get('Authorization', '').removeprefix('Bearer ')
    session = await db.user_sessions.find_one({'token_hash': digest(token), 'expires_at': {'$gt': now()}}, {'_id': 0}) if token else None
    user = await db.users.find_one({'user_id': session['user_id']}, {'_id': 0, 'password_hash': 0}) if session else None
    if not user:
        raise HTTPException(401, 'Please sign in to continue.')
    return user

async def create_session(user, response):
    token = secrets.token_urlsafe(40)
    await db.user_sessions.insert_one({'token_hash': digest(token), 'user_id': user['user_id'], 'expires_at': now() + timedelta(days=7)})
    response.set_cookie('session_token', token, max_age=604800, httponly=True, secure=True, samesite='none', path='/')
    return UserOut(**user)

async def throttle(request):
    key = (request.client.host if request.client else 'unknown') + ':' + now().strftime('%Y%m%d%H%M')
    counter = await db.auth_limits.find_one_and_update({'key': key}, {'$inc': {'count': 1}, '$setOnInsert': {'expires_at': now() + timedelta(minutes=2)}}, upsert=True, return_document=True)
    if counter['count'] > 30:
        raise HTTPException(429, 'Too many sign-in attempts. Please wait a minute.')

@router.post('/register', response_model=UserOut)
async def register(body: Credentials, request: Request, response: Response):
    await throttle(request)
    if len(body.name.strip()) < 2:
        raise HTTPException(422, 'Please enter your full name.')
    if len(body.password.encode()) > 72:
        raise HTTPException(422, 'Password is too long.')
    user = {'user_id': uid(), 'email': str(body.email).lower(), 'name': body.name.strip(), 'picture': '', 'password_hash': bcrypt.hashpw(body.password.encode(), bcrypt.gensalt()).decode(), 'created_at': now().isoformat()}
    try:
        await db.users.insert_one(user.copy())
    except DuplicateKeyError:
        raise HTTPException(409, 'An account already exists. Sign in or continue with Google.')
    return await create_session(user, response)

@router.post('/login', response_model=UserOut)
async def login(body: Credentials, request: Request, response: Response):
    await throttle(request)
    user = await db.users.find_one({'email': str(body.email).lower()}, {'_id': 0})
    if not user or not user.get('password_hash') or len(body.password.encode()) > 72 or not bcrypt.checkpw(body.password.encode(), user['password_hash'].encode()):
        raise HTTPException(401, 'Email or password is incorrect. Google accounts can continue with Google.')
    return await create_session(user, response)

@router.post('/session', response_model=UserOut)
async def google_session(body: GoogleSession, response: Response, request: Request):
    await throttle(request)
    async with httpx.AsyncClient(timeout=20) as client:
        try:
            result = await client.get('https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data', headers={'X-Session-ID': body.session_id})
        except httpx.HTTPError:
            raise HTTPException(503, 'Google sign-in is unavailable. Please try again.')
    if result.status_code != 200:
        raise HTTPException(401, 'Google session expired. Please sign in again.')
    data = result.json()
    email = data['email'].lower()
    user = await db.users.find_one({'email': email}, {'_id': 0})
    if not user:
        user = {'user_id': uid(), 'email': email, 'name': data['name'], 'picture': data.get('picture', ''), 'created_at': now().isoformat()}
        try:
            await db.users.insert_one(user.copy())
        except DuplicateKeyError:
            user = await db.users.find_one({'email': email}, {'_id': 0})
    await db.users.update_one({'user_id': user['user_id']}, {'$set': {'google_verified': True}})
    return await create_session(user, response)

@router.get('/me', response_model=UserOut)
async def me(user=Depends(current_user)):
    return UserOut(**user)

@router.post('/logout')
async def logout(request: Request, response: Response):
    token = request.cookies.get('session_token', '')
    await db.user_sessions.delete_one({'token_hash': digest(token)})
    response.delete_cookie('session_token', path='/', secure=True, samesite='none')
    return {'message': 'Signed out'}