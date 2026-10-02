import stripe
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool
from core import db, now, authorize, owned_property
from auth import current_user
from models import DashboardOut, PropertyOut, BookingOut, InquiryOut
from payments import require_stripe, origin

router = APIRouter(prefix='/api', tags=['Owner'])

@router.get('/owner/dashboard', response_model=DashboardOut)
async def dashboard(user=Depends(current_user)):
    props = await db.properties.find({'host_id': user['user_id'], 'status': {'$ne': 'deleted'}}, {'_id': 0, 'contact_email': 0}).sort('created_at', -1).to_list(1000)
    bookings = await db.bookings.find({'host_id': user['user_id']}, {'_id': 0}).sort('created_at', -1).to_list(1000)
    inquiries = await db.inquiries.find({'host_id': user['user_id']}, {'_id': 0}).sort('created_at', -1).to_list(1000)
    host = await db.hosts.find_one({'user_id': user['user_id']}, {'_id': 0}) or {}
    paid = [b for b in bookings if b['payment_status'] == 'paid']
    return DashboardOut(properties=[PropertyOut(**p) for p in props], bookings=[BookingOut(**b) for b in bookings], inquiries=[InquiryOut(**i) for i in inquiries], revenue=round(sum(b['amount'] for b in paid),2), earnings=round(sum(b['host_payout'] for b in paid),2), pending_payouts=round(sum(b['host_payout'] for b in paid if b['payout_status'] == 'pending'),2), transferred=round(sum(b['host_payout'] for b in paid if b['payout_status'] == 'transferred'),2), payout_onboarding=host.get('onboarding_status','not_started'))

@router.get('/owner/properties/{property_id}')
async def owner_property(property_id: str, user=Depends(current_user)):
    doc = await owned_property(property_id, user, 'property.edit')
    return {**PropertyOut(**doc).model_dump(), 'contact_email': doc['contact_email']}

@router.get('/bookings', response_model=list[BookingOut])
async def my_bookings(user=Depends(current_user)):
    docs = await db.bookings.find({'customer_id': user['user_id']}, {'_id': 0}).sort('created_at',-1).to_list(1000)
    return [BookingOut(**d) for d in docs]

class OnboardingInput(BaseModel):
    country: str = Field(min_length=2, max_length=2)

@router.post('/owner/onboarding')
async def onboarding(body: OnboardingInput, request: Request, user=Depends(current_user)):
    require_stripe()
    host = await db.hosts.find_one({'user_id': user['user_id']}, {'_id': 0}) or {}
    try:
        account_id = host.get('stripe_account_id')
        if not account_id:
            account = await run_in_threadpool(stripe.Account.create, type='express', country=body.country.upper(), email=user['email'], capabilities={'transfers': {'requested': True}}, idempotency_key='host-'+user['user_id'])
            account_id = account.id
            await db.hosts.update_one({'user_id': user['user_id']}, {'$set': {'stripe_account_id': account_id, 'onboarding_status': 'pending', 'name': user['name'], 'email': user['email']}}, upsert=True)
        link = await run_in_threadpool(stripe.AccountLink.create, account=account_id, refresh_url=origin(request)+'/dashboard?tab=payouts', return_url=origin(request)+'/dashboard?tab=payouts&onboarding=returned', type='account_onboarding')
        return {'url': link.url}
    except stripe.StripeError as exc:
        raise HTTPException(502, 'Payout onboarding could not be started. Confirm that Stripe Connect supports your country and try again.') from exc

@router.post('/owner/payout/{booking_id}')
async def payout(booking_id: str, user=Depends(current_user)):
    require_stripe()
    booking = await db.bookings.find_one({'id': booking_id, 'host_id': user['user_id']}, {'_id': 0})
    if not booking:
        raise HTTPException(404, 'Booking not found.')
    authorize(user, 'booking.payout', booking)
    if booking['payout_status'] == 'transferred':
        return {'status': 'transferred', 'transfer_id': booking['transfer_id']}
    if booking['payment_status'] != 'paid' or booking['payout_status'] != 'pending' or booking['check_out'] > now().date().isoformat():
        raise HTTPException(409, 'Payouts are available after a paid stay has ended.')
    host = await db.hosts.find_one({'user_id': user['user_id']}, {'_id': 0})
    if not host or not host.get('stripe_account_id'):
        raise HTTPException(409, 'Complete payout onboarding first.')
    try:
        account = await run_in_threadpool(stripe.Account.retrieve, host['stripe_account_id'])
        if not account.payouts_enabled or account.capabilities.get('transfers') != 'active':
            raise HTTPException(409, 'Your payout account is not ready. Complete Stripe verification first.')
        await db.hosts.update_one({'user_id': user['user_id']}, {'$set': {'onboarding_status': 'complete'}})
        intent = await run_in_threadpool(stripe.PaymentIntent.retrieve, booking['payment_intent_id'])
        transfer = await run_in_threadpool(stripe.Transfer.create, amount=round(booking['host_payout']*100), currency='kes', destination=account.id, source_transaction=intent.latest_charge, metadata={'booking_id': booking_id}, idempotency_key='payout-'+booking_id)
    except stripe.StripeError:
        raise HTTPException(502, 'Transfer could not be confirmed. No payout success has been recorded.')
    await db.bookings.update_one({'id': booking_id, 'host_id': user['user_id']}, {'$set': {'payout_status': 'transferred', 'transfer_id': transfer.id}})
    return {'status': 'transferred', 'transfer_id': transfer.id, 'message': 'Transferred to your Stripe account. Bank payout timing is managed by Stripe.'}