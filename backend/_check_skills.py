import json
import sys
import urllib.request

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
BASE = 'http://127.0.0.1:8001/api/v1'
with urllib.request.urlopen(urllib.request.Request(
    BASE + '/auth/login',
    data=json.dumps({'email': 'smoke@test.com', 'password': 'Smoke@12345'}).encode(),
    headers={'Content-Type': 'application/json'}), timeout=10) as r:
    tok = json.loads(r.read())['token']

req = urllib.request.Request(BASE + '/skills/plaza', headers={'Authorization': f'Bearer {tok}'})
data = json.loads(urllib.request.urlopen(req, timeout=15).read())
items = data if isinstance(data, list) else (data.get('items') or data.get('data') or [])
print('技能数:', len(items))
for s in items:
    print('  -', s.get('name'), '| slug=', s.get('slug'), '| id=', s.get('id'))
