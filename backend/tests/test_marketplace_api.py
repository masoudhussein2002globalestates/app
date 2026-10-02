import io
import os
import uuid
from datetime import date, timedelta

import pytest
import requests
from dotenv import load_dotenv
from PIL import Image

# Auth + properties + dashboard + payments + media regression coverage.
load_dotenv('/app/frontend/.env')
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL')

if not BASE_URL:
    raise RuntimeError('REACT_APP_BACKEND_URL is required for external API testing')


def api(path: str) -> str:
    return f"{BASE_URL.rstrip('/')}/api{path}"


def new_user_payload(prefix: str):
    token = uuid.uuid4().hex[:10]
    return {
        'name': f'TEST {prefix} {token}',
        'email': f'test-{prefix}-{token}@example.com',
        'password': 'TestPass123!'
    }


def origin_headers():
    """Build ingress-style origin headers for browser-equivalent auth requests."""
    host = BASE_URL.replace('https://', '').replace('http://', '').split('/')[0]
    return {
        'Origin': BASE_URL.rstrip('/'),
        'Host': host,
        'X-Forwarded-Host': host,
    }


def make_property(category: str, title_suffix: str):
    common = {
        'title': f'TEST {category} Listing {title_suffix}',
        'category': category,
        'location': 'Nairobi',
        'country': 'Kenya',
        'description': 'This is a TEST listing description long enough for validation in marketplace flows.',
        'amenities': ['Wi-Fi', 'Parking'],
        'images': ['https://images.unsplash.com/photo-1596178067639-5c6e68aea6dc?auto=format&fit=crop&w=1200&q=80'],
        'contact_email': f'contact-{title_suffix}@example.com',
        'status': 'active',
    }
    if category == 'Rent':
        return {**common, 'price': 30000, 'bedrooms': 2, 'guests': 3, 'size': ''}
    if category == 'Vacation':
        return {**common, 'price': 20000, 'bedrooms': 2, 'guests': 4, 'size': ''}
    if category == 'Outings':
        return {**common, 'price': 4000, 'bedrooms': 0, 'guests': 8, 'size': ''}
    return {**common, 'price': 1500000, 'bedrooms': 0, 'guests': 1, 'size': '0.5 acres'}


@pytest.fixture(scope='session')
def anon():
    s = requests.Session()
    s.headers.update({'Content-Type': 'application/json'})
    return s


@pytest.fixture(scope='session')
def owner(anon):
    payload = new_user_payload('owner')
    response = anon.post(api('/auth/register'), json=payload, timeout=30)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data['email'] == payload['email']
    return {'session': anon, 'user': data, 'payload': payload}


@pytest.fixture(scope='session')
def customer():
    s = requests.Session()
    s.headers.update({'Content-Type': 'application/json'})
    payload = new_user_payload('customer')
    response = s.post(api('/auth/register'), json=payload, timeout=30)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data['email'] == payload['email']
    return {'session': s, 'user': data, 'payload': payload}


@pytest.fixture(scope='session')
def properties(owner):
    session = owner['session']
    created = {}
    suffix = uuid.uuid4().hex[:8]
    for category in ['Rent', 'Vacation', 'Outings', 'Land']:
        body = make_property(category, suffix)
        response = session.post(api('/properties'), json=body, timeout=30)
        assert response.status_code == 201, response.text
        data = response.json()
        assert data['category'] == category
        created[category] = data
    yield created
    for item in created.values():
        session.delete(api(f"/properties/{item['id']}"), timeout=30)


def test_health_and_meta():
    health = requests.get(api('/health'), timeout=30)
    assert health.status_code == 200
    body = health.json()
    assert body['database'] == 'MongoDB'
    assert body['database_connected'] is True
    assert body['postgresql_configured'] is False

    meta = requests.get(api('/meta'), timeout=30)
    assert meta.status_code == 200
    meta_data = meta.json()
    assert 'Kenya' in meta_data['countries']
    assert set(meta_data['categories']) == {'Rent', 'Vacation', 'Outings', 'Land'}


def test_google_invalid_exchange_rejected():
    response = requests.post(api('/auth/session'), json={'session_id': 'invalid-session-id'}, timeout=30)
    assert response.status_code in [401, 503]
    assert 'detail' in response.json()


def test_register_with_valid_origin_header_allowed():
    payload = new_user_payload('origin')
    response = requests.post(api('/auth/register'), json=payload, headers=origin_headers(), timeout=30)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data['email'] == payload['email']
    assert 'user_id' in data and isinstance(data['user_id'], str)


def test_invalid_login_rejected(owner):
    bad = owner['session'].post(api('/auth/login'), json={'email': owner['payload']['email'], 'password': 'WrongPass123!', 'name': ''}, timeout=30)
    assert bad.status_code == 401
    assert 'incorrect' in bad.json()['detail'].lower()


def test_auth_me_and_logout(owner):
    me = owner['session'].get(api('/auth/me'), timeout=30)
    assert me.status_code == 200
    assert me.json()['email'] == owner['payload']['email']

    out = owner['session'].post(api('/auth/logout'), timeout=30)
    assert out.status_code == 200

    me_after = owner['session'].get(api('/auth/me'), timeout=30)
    assert me_after.status_code == 401

    relogin = owner['session'].post(api('/auth/login'), json=owner['payload'], timeout=30)
    assert relogin.status_code == 200
    assert relogin.json()['email'] == owner['payload']['email']


def test_anonymous_create_denied():
    response = requests.post(api('/properties'), json=make_property('Rent', 'anon'), timeout=30)
    assert response.status_code == 401


def test_properties_public_filters_sort_and_no_contact_email(properties):
    base = requests.get(api('/properties'), timeout=30)
    assert base.status_code == 200
    base_data = base.json()
    assert isinstance(base_data['properties'], list)

    filtered = requests.get(api('/properties'), params={'location': 'Nairobi', 'country': 'Kenya', 'category': 'Rent', 'minPrice': 1000, 'maxPrice': 1000000, 'bedrooms': 1, 'guests': 1, 'sort': 'price_asc', 'page': 1, 'limit': 12}, timeout=30)
    assert filtered.status_code == 200
    f = filtered.json()
    assert f['page'] == 1
    assert f['pages'] >= 1
    assert all(p['category'] == 'Rent' for p in f['properties'])
    assert all('contact_email' not in p for p in f['properties'])

    detail = requests.get(api(f"/properties/{properties['Rent']['id']}"), timeout=30)
    assert detail.status_code == 200
    assert 'contact_email' not in detail.json()


def test_owner_restricted_access_for_second_user(customer, properties):
    session = customer['session']
    pid = properties['Vacation']['id']

    get_owner = session.get(api(f'/owner/properties/{pid}'), timeout=30)
    assert get_owner.status_code == 404

    edit = session.put(api(f'/properties/{pid}'), json=make_property('Vacation', 'forbidden'), timeout=30)
    assert edit.status_code == 404

    delete = session.delete(api(f'/properties/{pid}'), timeout=30)
    assert delete.status_code == 404


def test_dashboard_scope_and_zero_revenue(owner):
    response = owner['session'].get(api('/owner/dashboard'), timeout=30)
    assert response.status_code == 200
    data = response.json()
    assert all(p['host_id'] == owner['user']['user_id'] for p in data['properties'])
    assert data['revenue'] == 0
    assert data['earnings'] == 0
    assert data['pending_payouts'] == 0


def test_favorites_persist_across_reload(customer, properties):
    session = customer['session']
    pid = properties['Outings']['id']
    save = session.put(api(f'/favorites/{pid}'), timeout=30)
    assert save.status_code == 200
    assert save.json()['saved'] is True

    get1 = session.get(api('/favorites'), timeout=30)
    assert get1.status_code == 200
    assert any(p['id'] == pid for p in get1.json())

    get2 = session.get(api('/favorites'), timeout=30)
    assert get2.status_code == 200
    assert any(p['id'] == pid for p in get2.json())

    remove = session.delete(api(f'/favorites/{pid}'), timeout=30)
    assert remove.status_code == 200
    assert remove.json()['saved'] is False


def test_inquiry_delivery_and_sample_block(customer, owner, properties):
    session = customer['session']
    real_id = properties['Rent']['id']

    inquiry = session.post(api(f'/properties/{real_id}/inquiries'), json={'message': 'Hello host, I am interested and would like to schedule a visit soon.'}, timeout=30)
    assert inquiry.status_code == 201

    sample = session.post(api('/properties/sample-diani/inquiries'), json={'message': 'Can I reserve this sample listing for next week?'}, timeout=30)
    assert sample.status_code == 409

    inbox = owner['session'].get(api('/owner/dashboard'), timeout=30)
    assert inbox.status_code == 200
    inquiries = inbox.json()['inquiries']
    hit = [i for i in inquiries if i['property_id'] == real_id]
    assert len(hit) >= 1
    assert hit[0]['customer_email'] == customer['payload']['email']


def test_booking_quote_validation_and_fees(properties):
    start = date.today() + timedelta(days=5)

    sample_quote = requests.post(api('/bookings/quote'), json={'property_id': 'sample-diani', 'check_in': start.isoformat(), 'check_out': (start + timedelta(days=2)).isoformat(), 'guests': 2}, timeout=30)
    assert sample_quote.status_code == 409

    land_quote = requests.post(api('/bookings/quote'), json={'property_id': properties['Land']['id'], 'check_in': start.isoformat(), 'check_out': (start + timedelta(days=2)).isoformat(), 'guests': 1}, timeout=30)
    assert land_quote.status_code == 422

    bad_dates = requests.post(api('/bookings/quote'), json={'property_id': properties['Vacation']['id'], 'check_in': (date.today() - timedelta(days=1)).isoformat(), 'check_out': start.isoformat(), 'guests': 2}, timeout=30)
    assert bad_dates.status_code == 422

    reversed_dates = requests.post(api('/bookings/quote'), json={'property_id': properties['Vacation']['id'], 'check_in': start.isoformat(), 'check_out': start.isoformat(), 'guests': 2}, timeout=30)
    assert reversed_dates.status_code == 422

    too_many = requests.post(api('/bookings/quote'), json={'property_id': properties['Vacation']['id'], 'check_in': start.isoformat(), 'check_out': (start + timedelta(days=2)).isoformat(), 'guests': 99}, timeout=30)
    assert too_many.status_code == 422

    vacation_quote = requests.post(api('/bookings/quote'), json={'property_id': properties['Vacation']['id'], 'check_in': start.isoformat(), 'check_out': (start + timedelta(days=2)).isoformat(), 'guests': 2}, timeout=30)
    assert vacation_quote.status_code == 200
    vac = vacation_quote.json()
    assert vac['amount'] == 40000.0
    assert vac['platform_fee'] == 4000.0

    outing_quote = requests.post(api('/bookings/quote'), json={'property_id': properties['Outings']['id'], 'check_in': start.isoformat(), 'check_out': (start + timedelta(days=3)).isoformat(), 'guests': 2}, timeout=30)
    assert outing_quote.status_code == 200
    out = outing_quote.json()
    assert out['units'] == 6
    assert out['amount'] == 24000.0
    assert out['platform_fee'] == 2400.0

    rent_quote = requests.post(api('/bookings/quote'), json={'property_id': properties['Rent']['id'], 'check_in': start.isoformat(), 'check_out': (start + timedelta(days=31)).isoformat(), 'guests': 2}, timeout=30)
    assert rent_quote.status_code == 200
    rent = rent_quote.json()
    assert rent['units'] == 2
    assert rent['amount'] == 60000.0
    assert rent['platform_fee'] == 0.0


def test_unconfigured_payment_endpoints_fail_safely(owner, properties):
    start = date.today() + timedelta(days=10)
    checkout = owner['session'].post(api('/checkout'), json={'property_id': properties['Vacation']['id'], 'check_in': start.isoformat(), 'check_out': (start + timedelta(days=2)).isoformat(), 'guests': 2}, timeout=30)
    assert checkout.status_code == 503

    payout = owner['session'].post(api('/owner/payout/nonexistent-booking-id'), timeout=30)
    assert payout.status_code == 503

    webhook = requests.post(api('/stripe/webhook'), data=b'{}', timeout=30)
    assert webhook.status_code == 503


def test_media_upload_and_retrieve(owner):
    owner['session'].headers.pop('Content-Type', None)
    image = Image.new('RGB', (32, 32), color='green')
    stream = io.BytesIO()
    image.save(stream, format='PNG')
    stream.seek(0)

    upload = owner['session'].post(api('/upload'), files={'file': ('test.png', stream.getvalue(), 'image/png')}, timeout=60)
    assert upload.status_code == 200, upload.text
    data = upload.json()
    assert data['url'].startswith('/api/media/')

    media_id = data['id']
    get_media = requests.get(api(f'/media/{media_id}'), timeout=60)
    assert get_media.status_code == 200
    assert get_media.headers['content-type'].startswith('image/')
    assert len(get_media.content) > 0


def test_media_upload_invalid_file_rejected(owner):
    owner['session'].headers.pop('Content-Type', None)
    bad = owner['session'].post(api('/upload'), files={'file': ('bad.txt', b'not-an-image', 'text/plain')}, timeout=60)
    assert bad.status_code == 422
    detail = bad.json()['detail']
    assert ('valid jpeg' in detail.lower()) if isinstance(detail, str) else True
