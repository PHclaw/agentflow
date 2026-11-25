import json
import sqlite3
import urllib.request

BASE = 'http://127.0.0.1:8001/api/v1'
with urllib.request.urlopen(urllib.request.Request(
    BASE + '/auth/login',
    data=json.dumps({'email': 'smoke@test.com', 'password': 'Smoke@12345'}).encode(),
    headers={'Content-Type': 'application/json'}), timeout=10) as r:
    tok = json.loads(r.read())['token']


def get(path):
    req = urllib.request.Request(BASE + path, headers={'Authorization': f'Bearer {tok}'})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


agents = get('/agents')
if isinstance(agents, dict):
    agents = agents.get('items') or agents.get('data') or []
a = agents[0]
print('=== agent 全字段 ===')
print(json.dumps(a, ensure_ascii=False, indent=2)[:2500])
