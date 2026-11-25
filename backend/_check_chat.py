import json
import time
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

# 挑一个无工作流、名字像客服的 agent 做测试
candidates = [a for a in agents if not (a.get('workflow_definition') or {}).get('nodes')]
print('无工作流 agent 数:', len(candidates))
target = next((a for a in candidates if '客服' in (a.get('name') or '')), candidates[0])
print('测试目标:', target['id'], target['name'])

payload = json.dumps({
    'message': '你好，请用一句话介绍你自己',
    'stream': True,
}).encode()
req = urllib.request.Request(
    BASE + '/chat/' + target['id'],
    data=payload,
    headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {tok}'},
)
t0 = time.time()
first = None
buf = b''
with urllib.request.urlopen(req, timeout=180) as r:
    print('HTTP', r.status)
    while True:
        chunk = r.read(1024)
        if not chunk:
            break
        if first is None and chunk.strip():
            first = time.time() - t0
        buf += chunk
        if time.time() - t0 > 120:
            print('超过 120s，主动断开')
            break
elapsed = time.time() - t0
text = buf.decode('utf-8', 'replace')
print(f'首字节: {first:.1f}s' if first else '无首字节')
print(f'总耗时: {elapsed:.1f}s, 原始长度: {len(text)}')
# 提取 SSE data 内容
parts = []
for line in text.splitlines():
    if line.startswith('data: '):
        try:
            d = json.loads(line[6:])
            if d.get('type') in ('content', 'delta') and d.get('content'):
                parts.append(d['content'])
        except Exception:
            pass
joined = ''.join(parts)
print('拼出正文长度:', len(joined))
print('正文前 300 字:', joined[:300])
