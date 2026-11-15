"""探测：技能直连接口 + 可用 Agent 清单。只读/调用，不改仓库。"""
import json
import sys
import urllib.request

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
BASE = 'http://127.0.0.1:8001/api/v1'


def login():
    req = urllib.request.Request(
        BASE + '/auth/login',
        data=json.dumps({'email': 'smoke@test.com', 'password': 'Smoke@12345'}).encode(),
        headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())['token']


def get(path, tok):
    req = urllib.request.Request(BASE + path, headers={'Authorization': f'Bearer {tok}'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def post(path, tok, payload, timeout=120):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(payload).encode(),
        headers={'Authorization': f'Bearer {tok}', 'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


tok = login()

agents = get('/agents', tok)
items = agents if isinstance(agents, list) else (agents.get('items') or agents.get('agents') or [])
print('=== Agent 共', len(items), '个 ===')
for a in items:
    print('  -', a.get('name'), '| id=', a.get('id'))

TABLE = (
    '月份  铅笔  钢笔  橡皮\n'
    '1月   10支  8支   5块\n'
    '2月   12支  9支   6块\n'
    '3月   15支  11支  9块\n'
    '4月   9支   7支   4块\n'
    '\n请按月份画出销量的柱状图'
)
print('\n=== 调用 POST /skills/excel/call （出图意图） ===')
try:
    res = post('/skills/excel/call', tok, {'variables': {'input': TABLE}}, timeout=180)
    tt = res.get('toolTrace') or {}
    print('顶层键:', sorted(res.keys()))
    print('intent=', tt.get('intent'), '| exitCode=', tt.get('exitCode'))
    print('imageUrl=', tt.get('imageUrl'))
    print('downloadUrl=', tt.get('downloadUrl'), '| name=', tt.get('downloadName'))
    print('reply 片段:', (res.get('reply') or res.get('content') or '')[:300])
except Exception as e:
    body = getattr(e, 'read', lambda: b'')()
    print('调用失败:', e, body[:500] if body else '')
