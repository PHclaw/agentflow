"""录制后复盘：Agent 名额、办公助手最新会话的产物、PPT 到底出没出来。"""
import json
import sys
import urllib.request

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
BASE = 'http://127.0.0.1:8001/api/v1'
DEMO_AGENT = '29dfb7a1-59ea-414a-99f5-67cbd75fc0c3'

with urllib.request.urlopen(urllib.request.Request(
    BASE + '/auth/login',
    data=json.dumps({'email': 'smoke@test.com', 'password': 'Smoke@12345'}).encode(),
    headers={'Content-Type': 'application/json'}), timeout=15) as r:
    TOK = json.loads(r.read())['token']


def get(path, timeout=40):
    rq = urllib.request.Request(BASE + path, headers={'Authorization': f'Bearer {TOK}'})
    with urllib.request.urlopen(rq, timeout=timeout) as r:
        return json.loads(r.read())


agents = get('/agents')
items = agents if isinstance(agents, list) else (agents.get('items') or agents.get('agents') or [])
print('Agent 数 =', len(items), '（上限 20）')
print('最新 3 个：')
for a in sorted(items, key=lambda x: x.get('updated_at') or '', reverse=True)[:3]:
    print('  -', a.get('name'), '|', a.get('id'), '|', a.get('updated_at'))

sess = get(f'/chat/{DEMO_AGENT}/sessions')
si = sess if isinstance(sess, list) else (sess.get('items') or sess.get('sessions') or [])
si.sort(key=lambda s: s.get('updated_at') or '', reverse=True)
print('\n办公助手会话数 =', len(si))
for s in si[:3]:
    print('  -', s.get('id'), s.get('updated_at'), (s.get('title') or '')[:40])

if si:
    sid = si[0].get('id')
    hist = get(f'/chat/{DEMO_AGENT}/history?session_id={sid}')
    msgs = hist if isinstance(hist, list) else (hist.get('messages') or hist.get('items') or [])
    print(f'\n最新会话 {sid} 消息数 =', len(msgs))
    for m in msgs[-3:]:
        print('  role=', m.get('role'), '| files=', [f.get('name') for f in (m.get('files') or [])])
        print('    content 尾部:', (m.get('content') or '')[-300:])
