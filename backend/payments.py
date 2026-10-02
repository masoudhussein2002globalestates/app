import os
import stripe
from decimal import Decimal, ROUND_HALF_UP
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.concurrency import run_in_threadpool
from pymongo.errors import DuplicateKeyError
from core import db, now, uid, owned_property
from auth import current_user
from models import CheckoutInput, BookingInput

router = APIRouter(prefix='/api', tags=['Payments'])
stripe.api_key = os.environ.get('STRIPE_SECRET_KEY')
stripe.max_network_retries = 1

def configured():
    return bool(os.environ.get('STRIPE_SECRET_KEY'))

def require_stripe():
    if not configured():
        raise HTTPException(503, 'Online payments are unavailable: Stripe account setup is not supported for the platform’s current country. No payment has been taken.')

def origin(request):
    # Preserve the public host forwarded by the platform ingress after publication.
    from urllib.parse import urlsplit
    host = request.headers.get('x-forwarded-host')
    if host and urlsplit('https://' + host).netloc == host and '/' not in host:
        return 'https://' + host
    return os.environ['FRONTEND_ORIGIN'].rstrip('/')

def rounded(value):
    return float(Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))

async def quote(body, user=None):
    prop = await db.properties.find_one({'id': body.property_id, 'status': 'active'}, {'_id': 0})
    if not prop:
        raise HTTPException(404, 'Property not found.')
    if prop.get('is_sample'):
        raise HTTPException(409, 'This is a sample listing and cannot be booked.')
    if prop['category'] == 'Land':
        raise HTTPException(422, 'Land uses an inquiry flow, not online checkout.')
    if user and prop['host_id'] == user['user_id']:
        raise HTTPException(409, 'You cannot book your own property.')
    if not body.check_in or not body.check_out or body.check_in < now().date() or body.check_out <= body.check_in:
        raise HTTPException(422, 'Choose a check-in date today or later and a later check-out date.')
    days = (body.check_out - body.check_in).days
    if days > 366 or body.check_in > now().date() + timedelta(days=730):
        raise HTTPException(422, 'Bookings must be within two years and at most 366 days long.')
    if body.guests > prop['guests']:
        raise HTTPException(422, f"This property allows up to {prop['guests']} guests.")
    units = ((days + 29)//30) if prop['category'] == 'Rent' else days * body.guests if prop['category'] == 'Outings' else days
    amount = rounded(prop['price'] * units)
    rate = 0.1 if prop['category'] in ['Vacation', 'Outings'] else float(os.environ['RENTAL_PLATFORM_FEE'])
    fee = rounded(amount * rate)
    await db.availability.delete_many({'property_id': prop['id'], 'expires_at': {'$lte': now()}})
    conflict = await db.availability.find_one({'property_id': prop['id'], 'date': {'$gte': body.check_in.isoformat(), '$lt': body.check_out.isoformat()}}, {'_id': 0})
    if conflict:
        raise HTTPException(409, 'These dates are unavailable. Please choose different dates.')
    return prop, {'amount': amount, 'platform_fee': fee, 'host_payout': rounded(amount-fee), 'nights': days, 'units': units, 'currency': 'KES'}

@router.post('/bookings/quote')
async def booking_quote(body: BookingInput):
    _, result = await quote(body)
    return result

async def release_booking(booking_id, status):
    await db.bookings.update_one({'id': booking_id, 'payment_status': {'$ne': 'paid'}}, {'$set': {'payment_status': status, 'payout_status': 'not_due'}})
    await db.availability.delete_many({'booking_id': booking_id, 'expires_at': {'$exists': True}})

@router.post('/checkout')
async def checkout(body: CheckoutInput, request: Request, user=Depends(current_user)):
    require_stripe()
    transaction_id = uid()
    booking_id = None
    if body.plan:
        prop = await owned_property(body.property_id, user, 'property.plan')
        if prop.get('is_sample'):
            raise HTTPException(409, 'Sample listings cannot be promoted.')
        amount = 500.0 if body.plan == 'Featured' else 2000.0
        title = f"Global Estates {body.plan} placement — {prop['title']}"
    else:
        prop, totals = await quote(body, user)
        amount, title, booking_id = totals['amount'], prop['title'], uid()
        dates = [(body.check_in + timedelta(days=i)).isoformat() for i in range(totals['nights'])]
        holds = [{'property_id': prop['id'], 'date': d, 'booking_id': booking_id, 'expires_at': now() + timedelta(minutes=35)} for d in dates]
        try:
            await db.availability.insert_many(holds, ordered=True)
        except DuplicateKeyError:
            await db.availability.delete_many({'booking_id': booking_id})
            raise HTTPException(409, 'These dates have just been reserved. Please try other dates.')
        await db.bookings.insert_one({'id': booking_id, 'property_id': prop['id'], 'property_title': prop['title'], 'host_id': prop['host_id'], 'customer_id': user['user_id'], 'customer_name': user['name'], 'customer_email': user['email'], 'check_in': body.check_in.isoformat(), 'check_out': body.check_out.isoformat(), 'guests': body.guests, **totals, 'payment_status': 'pending', 'payout_status': 'not_due', 'stripe_session_id': '', 'payment_intent_id': '', 'transfer_id': '', 'created_at': now().isoformat()})
    transaction = {'id': transaction_id, 'user_id': user['user_id'], 'property_id': prop['id'], 'booking_id': booking_id, 'plan': body.plan, 'amount': amount, 'currency': 'kes', 'payment_status': 'pending', 'status': 'initiated', 'session_id': '', 'created_at': now().isoformat()}
    await db.payment_transactions.insert_one(transaction.copy())
    try:
        session = await run_in_threadpool(stripe.checkout.Session.create,
            mode='payment', customer_email=user['email'],
            line_items=[{'price_data': {'currency': 'kes', 'unit_amount': round(amount*100), 'product_data': {'name': title}}, 'quantity': 1}],
            success_url=origin(request) + '/payment/success?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=origin(request) + '/payment/cancel?transaction_id=' + transaction_id,
            automatic_tax={'enabled': True}, billing_address_collection='required',
            expires_at=int((now()+timedelta(minutes=30)).timestamp()),
            metadata={'transaction_id': transaction_id}, idempotency_key=transaction_id)
    except stripe.StripeError:
        if booking_id:
            await release_booking(booking_id, 'failed')
        await db.payment_transactions.update_one({'id': transaction_id}, {'$set': {'payment_status': 'failed', 'status': 'failed'}})
        raise HTTPException(502, 'Payment could not be started. No payment has been taken. Please try again.')
    await db.payment_transactions.update_one({'id': transaction_id}, {'$set': {'session_id': session.id}})
    if booking_id:
        await db.bookings.update_one({'id': booking_id}, {'$set': {'stripe_session_id': session.id}})
    return {'checkout_url': session.url, 'session_id': session.id}

async def reconcile(session):
    record = await db.payment_transactions.find_one({'session_id': session['id']}, {'_id': 0})
    if not record:
        return
    if session.get('payment_status') == 'paid':
        # Idempotent fulfilment is safe to retry after partial database failures.
        if record.get('booking_id'):
            await db.availability.update_many({'booking_id': record['booking_id']}, {'$unset': {'expires_at': ''}})
            await db.bookings.update_one({'id': record['booking_id']}, {'$set': {'payment_status': 'paid', 'payment_intent_id': session.get('payment_intent', ''), 'payout_status': 'pending'}})
        elif record.get('plan'):
            await db.properties.update_one({'id': record['property_id'], 'host_id': record['user_id']}, {'$set': {'listing_plan': record['plan'], 'plan_rank': 2 if record['plan'] == 'Premium' else 1}})
        await db.payment_transactions.update_one({'id': record['id']}, {'$set': {'payment_status': 'paid', 'status': 'completed', 'payment_intent_id': session.get('payment_intent', '')}})
    elif session.get('status') == 'expired' and record['payment_status'] != 'paid':
        if record.get('booking_id'):
            await release_booking(record['booking_id'], 'expired')
        await db.payment_transactions.update_one({'id': record['id']}, {'$set': {'payment_status': 'expired', 'status': 'expired'}})

@router.get('/checkout/status')
async def checkout_status(session_id: str):
    require_stripe()
    record = await db.payment_transactions.find_one({'session_id': session_id}, {'_id': 0})
    if not record:
        raise HTTPException(404, 'Payment not found.')
    try:
        session = await run_in_threadpool(stripe.checkout.Session.retrieve, session_id)
        await reconcile(session)
    except stripe.StripeError:
        raise HTTPException(502, 'Unable to verify payment right now. Please try again.')
    fresh = await db.payment_transactions.find_one({'id': record['id']}, {'_id': 0})
    return {'session_id': session_id, 'status': fresh['status'], 'payment_status': fresh['payment_status']}

@router.post('/checkout/cancel/{transaction_id}')
async def cancel_checkout(transaction_id: str, user=Depends(current_user)):
    require_stripe()
    record = await db.payment_transactions.find_one({'id': transaction_id, 'user_id': user['user_id']}, {'_id': 0})
    if not record:
        raise HTTPException(404, 'Transaction not found.')
    try:
        session = await run_in_threadpool(stripe.checkout.Session.retrieve, record['session_id'])
        if session.status == 'open':
            session = await run_in_threadpool(stripe.checkout.Session.expire, session.id)
        await reconcile(session)
    except stripe.StripeError:
        raise HTTPException(502, 'Unable to cancel the payment. Please check your booking status.')
    return {'message': 'Payment status updated.'}

@router.post('/stripe/webhook')
async def webhook(request: Request):
    secret = os.environ.get('STRIPE_WEBHOOK_SECRET')
    if not secret:
        raise HTTPException(503, 'Webhook is not configured.')
    try:
        event = stripe.Webhook.construct_event(await request.body(), request.headers.get('stripe-signature', ''), secret)
    except (ValueError, stripe.SignatureVerificationError):
        raise HTTPException(400, 'Invalid webhook signature.')
    kind, obj = event['type'], event['data']['object']
    if kind in ['checkout.session.completed', 'checkout.session.async_payment_succeeded', 'checkout.session.expired']:
        await reconcile(obj)
    elif kind == 'checkout.session.async_payment_failed':
        record = await db.payment_transactions.find_one({'session_id': obj['id']}, {'_id': 0})
        if record and record.get('booking_id'):
            await release_booking(record['booking_id'], 'failed')
    elif kind == 'charge.refunded':
        await db.payment_transactions.update_many({'payment_intent_id': obj.get('payment_intent')}, {'$set': {'payment_status': 'refunded'}})
        await db.bookings.update_many({'payment_intent_id': obj.get('payment_intent')}, {'$set': {'payment_status': 'refunded', 'payout_status': 'review_required'}})
    return {'received': True}