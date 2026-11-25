import json
import sys
import urllib.request

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
BASE = 'http://127.0.0.1:8001/api/v1'
AGENT = '5496b56d-9548-4fe1-89b4-90941144c30c'

with urllib.request.urlopen(urllib.request.Request(
    BASE + '/auth/login',
    data=json.dumps({'email': 'smoke@test.com', 'password': 'Smoke@12345'}).encode(),
    headers={'Content-Type': 'application/json'}), timeout=10) as r:
    tok = json.loads(r.read())['token']


def get(p):
    req = urllib.request.Request(BASE + p, headers={'Authorization': f'Bearer {tok}'})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


sessions = get(f'/chat/{AGENT}/sessions')
items = sessions if isinstance(sessions, list) else (sessions.get('items') or sessions.get('sessions') or [])
print('会话数:', len(items))
for s in items[:5]:
    sid = s.get('id') or s.get('session_id')
    print('  -', sid, s.get('updated_at') or s.get('created_at'), s.get('title') or '')

if items:
    sid = items[0].get('id') or items[0].get('session_id')
    hist = get(f'/chat/{AGENT}/history?session_id={sid}')
    msgs = hist if isinstance(hist, list) else (hist.get('messages') or hist.get('items') or [])
    print('\n最新会话', sid, '消息数:', len(msgs))
    for m in msgs[-3:]:
        print('  role=', m.get('role'), '| keys=', sorted(m.keys()))
        if m.get('files'):
            print('     files=', [f.get('name') for f in m['files']])
