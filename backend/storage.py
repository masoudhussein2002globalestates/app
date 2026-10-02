import os
import io
import httpx
from PIL import Image, UnidentifiedImageError
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Response
from core import db, uid, now
from auth import current_user

router = APIRouter(prefix='/api', tags=['Images'])
storage_key = None

def storage_url():
    return os.environ['INTEGRATION_PROXY_URL'].rstrip('/') + '/objstore/api/v1/storage'

async def key(force=False):
    global storage_key
    if not storage_key or force:
        async with httpx.AsyncClient(timeout=30) as client:
            result = await client.post(storage_url()+'/init', json={'emergent_key': os.environ['EMERGENT_LLM_KEY']})
            result.raise_for_status()
            storage_key = result.json()['storage_key']
    return storage_key

async def storage_request(method, path, **kwargs):
    extra_headers = kwargs.pop('headers', {})
    async with httpx.AsyncClient(timeout=90) as client:
        result = await client.request(method, storage_url()+'/objects/'+path, headers={'X-Storage-Key': await key(), **extra_headers}, **kwargs)
        if result.status_code == 404:
            result = await client.request(method, storage_url()+'/objects/'+path, headers={'X-Storage-Key': await key(force=True), **extra_headers}, **kwargs)
        result.raise_for_status()
        return result

@router.post('/upload')
async def upload(file: UploadFile = File(...), user=Depends(current_user)):
    data = await file.read(10*1024*1024+1)
    if len(data) > 10*1024*1024:
        raise HTTPException(413, 'Images must be under 10 MB.')
    try:
        image = Image.open(io.BytesIO(data))
        if image.format not in ['JPEG','PNG','WEBP'] or image.width*image.height > 40000000:
            raise ValueError()
        image.verify()
        ext = {'JPEG':'jpg','PNG':'png','WEBP':'webp'}[image.format]
    except (UnidentifiedImageError, ValueError, OSError, Image.DecompressionBombError):
        raise HTTPException(422, 'Please upload a valid JPEG, PNG, or WebP image.')
    media_id = uid()
    content_type = 'image/jpeg' if ext == 'jpg' else 'image/'+ext
    try:
        result = await storage_request('PUT', f'global-estates/uploads/{user["user_id"]}/{media_id}.{ext}', content=data, headers={'Content-Type': content_type})
    except (httpx.HTTPError, KeyError):
        raise HTTPException(503, 'Image upload is unavailable. Please try again or add an HTTPS image URL.')
    await db.files.insert_one({'id': media_id, 'user_id': user['user_id'], 'storage_path': result.json()['path'], 'original_filename': file.filename, 'content_type': content_type, 'size': len(data), 'is_deleted': False, 'created_at': now().isoformat()})
    return {'url': '/api/media/'+media_id, 'id': media_id}

@router.get('/media/{media_id}')
async def media(media_id: str):
    record = await db.files.find_one({'id': media_id, 'is_deleted': False}, {'_id': 0})
    if not record:
        raise HTTPException(404, 'Image not found.')
    try:
        result = await storage_request('GET', record['storage_path'])
    except (httpx.HTTPError, KeyError):
        raise HTTPException(503, 'Unable to load this image.')
    return Response(result.content, media_type=record['content_type'], headers={'Cache-Control':'public, max-age=86400', 'X-Content-Type-Options': 'nosniff'})