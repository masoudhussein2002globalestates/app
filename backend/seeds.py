import os
from core import db, now, uid

def img(photo):
    return f'https://images.unsplash.com/{photo}?auto=format&fit=crop&w=1200&q=85'

async def initialize():
    await db.users.create_index('email', unique=True)
    await db.users.create_index('user_id', unique=True)
    await db.user_sessions.create_index('token_hash', unique=True)
    await db.user_sessions.create_index('expires_at', expireAfterSeconds=0)
    await db.auth_limits.create_index('key', unique=True)
    await db.auth_limits.create_index('expires_at', expireAfterSeconds=0)
    await db.properties.create_index('id', unique=True)
    await db.properties.create_index([('status',1),('country',1),('category',1),('price',1)])
    await db.properties.create_index([('host_id',1),('created_at',-1)])
    await db.favorites.create_index([('user_id',1),('property_id',1)], unique=True)
    await db.availability.create_index([('property_id',1),('date',1)], unique=True)
    await db.availability.create_index('expires_at', expireAfterSeconds=0)
    await db.bookings.create_index('id', unique=True)
    await db.bookings.create_index([('host_id',1),('created_at',-1)])
    await db.bookings.create_index([('customer_id',1),('created_at',-1)])
    await db.payment_transactions.create_index('id', unique=True)
    await db.payment_transactions.create_index('session_id')
    await db.hosts.create_index('user_id', unique=True)
    await db.inquiries.create_index([('host_id',1),('created_at',-1)])
    await db.files.create_index('id', unique=True)
    # Reserve the real owner's identity for verified Google sign-in; never assign a default password.
    await db.users.update_one({'email': os.environ['OWNER_EMAIL']}, {'$setOnInsert': {'user_id': uid(), 'name': 'Masoud Hussein', 'picture': '', 'created_at': now().isoformat()}}, upsert=True)
    seed = [
        ('sample-diani','Palm House, Diani Beach','Vacation','Diani Beach','Kenya',18500,3,6,'Premium','photo-1596178067639-5c6e68aea6dc',''),
        ('sample-nairobi','The Westlands Residence','Rent','Nairobi','Kenya',65000,2,4,'Featured','photo-1666282167632-c613fbeb163c',''),
        ('sample-mara','A Day in the Maasai Mara','Outings','Narok','Kenya',8500,0,8,'Free','photo-1623745493581-2f7b3d0d2140',''),
        ('sample-kutus','Green Acres, Kirinyaga','Land','Kutus','Kenya',1800000,0,1,'Featured','photo-1747854805840-9be7d5e360e6','0.5 acres'),
        ('sample-bali','The Ubud Garden Villa','Vacation','Bali','Indonesia',24000,2,4,'Premium','photo-1692736933760-8a8a9b8c1b6f',''),
        ('sample-paris','An Apartment in Le Marais','Rent','Paris','France',180000,2,4,'Free','photo-1738168279272-c08d6dd22002',''),
        ('sample-serengeti','The Serengeti Golden Hour','Outings','Serengeti','Tanzania',12500,0,6,'Featured','photo-1535940360221-641a69c43bac',''),
        ('sample-zanzibar','Zanzibar Palm Retreat','Vacation','Zanzibar','Tanzania',22000,2,4,'Free','photo-1651108066220-f61c22fc281f',''),
    ]
    for i,(id,title,category,location,country,price,beds,guests,plan,photo,size) in enumerate(seed):
        description = f'{title} is an illustrative sample of the places you can discover on Global Estates. Located in {location}, {country}, this listing showcases our {category.lower()} collection. This is not an actual property offer: reservations and owner inquiries are disabled. Photos are illustrative and may not show the named location.'
        doc = {'id':id,'host_id':'sample-host','host_name':'Global Estates Collection','title':title,'category':category,'location':location,'country':country,'price':price,'bedrooms':beds,'guests':guests,'listing_plan':plan,'plan_rank':2 if plan=='Premium' else 1 if plan=='Featured' else 0,'images':[img(photo)],'amenities':['Scenic views','Outdoor space'] if category in ['Land','Outings'] else ['Wi-Fi','Kitchen','Free parking','Outdoor space'],'description':description,'size':size,'status':'active','is_sample':True,'created_at':f'2026-01-{20-i:02}T12:00:00+00:00'}
        await db.properties.update_one({'id':id},{'$setOnInsert':doc},upsert=True)