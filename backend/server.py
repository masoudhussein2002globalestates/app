import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware
from pymongo.errors import PyMongoError
from pydantic import BaseModel, Field
from datetime import datetime
from core import db, client, now, uid, COUNTRIES
from seeds import initialize
from auth import router as auth_router
from catalog import router as catalog_router
from owners import router as owner_router
from payments import router as payments_router, configured
from storage import router as storage_router

logging.basicConfig(level=logging.INFO)

@asynccontextmanager
async def lifespan(app):
    try:
        await initialize()
    except PyMongoError:
        logging.exception('Database initialization failed')
    yield
    client.close()

app = FastAPI(title='Global Estates', lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=[os.environ['FRONTEND_ORIGIN']], allow_credentials=True, allow_methods=['GET','POST','PUT','PATCH','DELETE','OPTIONS'], allow_headers=['Content-Type','Authorization'])

@app.middleware('http')
async def security_headers(request: Request, call_next):
    if request.method not in ['GET','HEAD','OPTIONS'] and request.url.path != '/api/stripe/webhook':
        request_origin = request.headers.get('origin')
        allowed_origin = os.environ['FRONTEND_ORIGIN'].rstrip('/')
        forwarded_host = request.headers.get('x-forwarded-host', request.headers.get('host', ''))
        request_same_origin = f'https://{forwarded_host}'.rstrip('/')
        # The managed ingress rewrites Origin to its routed Host while preserving
        # the public hostname in X-Forwarded-Host. Both are this app, not wildcards.
        routed_origin = f'https://{request.headers.get("host", "")}'.rstrip('/')
        allowed = {allowed_origin.lower(), request_same_origin.lower(), routed_origin.lower()}
        if request_origin and request_origin.rstrip('/').lower() not in allowed:
            return JSONResponse({'detail':'Request origin not permitted.'}, status_code=403)
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    return response

@app.exception_handler(PyMongoError)
async def database_error(request, exc):
    logging.error('Database request failed: %s', type(exc).__name__)
    return JSONResponse({'detail':'The database is temporarily unavailable. Please try again.'}, status_code=503)

@app.get('/api/health')
async def health():
    connected = False
    try:
        await db.command('ping')
        connected = True
    except PyMongoError:
        pass
    return JSONResponse({'status':'ok' if connected else 'degraded','database':'MongoDB','database_connected':connected,'mongodb_configured':bool(os.environ.get('MONGO_URL')),'postgresql_configured':False,'stripe_configured':configured(),'stripe_mode':os.environ.get('STRIPE_MODE','unavailable'),'platform_fee':0.1,'rental_platform_fee':float(os.environ['RENTAL_PLATFORM_FEE'])}, status_code=200 if connected else 503)

@app.get('/api/meta')
async def meta():
    return {'countries':COUNTRIES,'categories':['Rent','Vacation','Outings','Land'],'stripe_configured':configured(),'stripe_mode':os.environ.get('STRIPE_MODE','unavailable'),'rental_platform_fee':float(os.environ['RENTAL_PLATFORM_FEE']),'vacation_outing_platform_fee':0.1,'currency':'KES'}

@app.get('/api/')
async def root():
    return {'message':'Global Estates API'}

class StatusCheckCreate(BaseModel):
    client_name: str = Field(min_length=1,max_length=100)
class StatusCheck(StatusCheckCreate):
    id: str
    timestamp: datetime

@app.post('/api/status', response_model=StatusCheck)
async def create_status_check(body: StatusCheckCreate):
    doc = {'client_name':body.client_name,'id':uid(),'timestamp':now().isoformat()}
    await db.status_checks.insert_one(doc.copy())
    return StatusCheck(**doc)

@app.get('/api/status', response_model=list[StatusCheck])
async def status_checks():
    docs = await db.status_checks.find({}, {'_id':0}).to_list(1000)
    return [StatusCheck(**doc) for doc in docs]

for router in [auth_router, catalog_router, owner_router, payments_router, storage_router]:
    app.include_router(router)