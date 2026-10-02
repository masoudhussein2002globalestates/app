"""One-time idempotent sandbox provisioning; never logs credentials."""
import json
import os
import urllib.request
import urllib.error
from pathlib import Path
from dotenv import load_dotenv, set_key

load_dotenv(Path(__file__).parent / '.env')
req = urllib.request.Request(
    os.environ['INTEGRATION_PROXY_URL'] + '/stripe/sandboxes',
    data=json.dumps({'job_id': '25f33ad5-0b15-4052-b273-929dbfc42b83'}).encode(),
    headers={'Authorization': 'Bearer ' + os.environ['EMERGENT_LLM_KEY'], 'Content-Type': 'application/json'},
    method='POST')
try:
    with urllib.request.urlopen(req, timeout=60) as response:
        data = json.load(response)
except urllib.error.HTTPError as exc:
    print('PROVISIONING FAILED', exc.code, exc.read().decode())
    raise SystemExit(1)
for env, key in [('STRIPE_SECRET_KEY', 'sandbox_secret_key'), ('STRIPE_PUBLISHABLE_KEY', 'sandbox_publishable_key'), ('STRIPE_ACCOUNT_ID', 'sandbox_account_id'), ('STRIPE_WEBHOOK_SECRET', 'preview_webhook_secret')]:
    if data.get(key):
        set_key(str(Path(__file__).parent / '.env'), env, data[key])
set_key(str(Path(__file__).parent / '.env'), 'STRIPE_MODE', 'test')
print(json.dumps({'configured': True, 'onboarding_url': data.get('onboarding_url')}))