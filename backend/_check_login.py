import json
import urllib.request

BASE = 'http://127.0.0.1:8001/api/v1'


def post(path, payload, token=None):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(payload).encode(),
        headers={'Content-Type': 'application/json', **({'Authorization': f'Bearer {token}'} if token else {})},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:300]
    except Exception as e:
        return 0, str(e)


def get(path, token):
    req = urllib.request.Request(BASE + path, headers={'Authorization': f'Bearer {token}'})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:300]


st, body = post('/auth/login', {'email': 'smoke@test.com', 'password': 'Smoke@12345'})
print('login:', st, 'keys=', list(body) if isinstance(body, dict) else body)
if st != 200:
    raise SystemExit(1)
tok = body['token']
st, agents = get('/agents', tok)
if isinstance(agents, dict):
    agents = agents.get('items') or agents.get('data') or []
print('agents:', st, 'count=', len(agents))
for a in agents[:6]:
    print('  -', a.get('id'), a.get('name'), '| 引擎:', a.get('engine'), '| 模型:', a.get('model'))
st, kb = get('/knowledge-bases', tok)
if isinstance(kb, dict):
    kb = kb.get('items') or kb.get('data') or []
print('knowledge-bases:', st, 'count=', len(kb))
