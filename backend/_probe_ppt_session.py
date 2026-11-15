"""看 PPT 那次会话最终有没有产出。"""
import json
import sys
import urllib.request

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
BASE = 'http://127.0.0.1:8001/api/v1'
AGENT = '29dfb7a1-59ea-414a-99f5-67cbd75fc0c3'
SESSION = '357c6064-7fac-4e6a-928a-e6c4fe7372a8'

with urllib.request.urlopen(urllib.request.Request(
    BASE + '/auth/login',
    data=json.dumps({'email': 'smoke@test.com', 'password': 'Smoke@12345'}).encode(),
    headers={'Content-Type': 'application/json'}), timeout=15) as r:
    TOK = json.loads(r.read())['token']


def get(path, timeout=60):
    rq = urllib.request.Request(BASE + path, headers={'Authorization': f'Bearer {TOK}'})
    with urllib.request.urlopen(rq, timeout=timeout) as r:
        return json.loads(r.read())


hist = get(f'/chat/{AGENT}/history?session_id={SESSION}')
msgs = hist if isinstance(hist, list) else (hist.get('messages') or hist.get('items') or [])
print('消息数 =', len(msgs))
for m in msgs:
    print('---', m.get('role'), '|', m.get('timestamp'))
    print('    files =', [f.get('name') for f in (m.get('files') or [])])
    c = (m.get('content') or '')
    print('    content 尾部:', c[-400:])
