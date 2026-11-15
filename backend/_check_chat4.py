import json
import sys
import time
import urllib.request

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE = 'http://127.0.0.1:8001/api/v1'
with urllib.request.urlopen(urllib.request.Request(
    BASE + '/auth/login',
    data=json.dumps({'email': 'smoke@test.com', 'password': 'Smoke@12345'}).encode(),
    headers={'Content-Type': 'application/json'}), timeout=10) as r:
    tok = json.loads(r.read())['token']

req = urllib.request.Request(BASE + '/agents', headers={'Authorization': f'Bearer {tok}'})
agents = json.loads(urllib.request.urlopen(req, timeout=15).read())
if isinstance(agents, dict):
    agents = agents.get('items') or agents.get('data') or []
wf = [a for a in agents if (a.get('workflow_definition') or {}).get('nodes')]
print('带工作流 agent 数:', len(wf))
for a in wf[:4]:
    n = len((a.get('workflow_definition') or {}).get('nodes') or [])
    print(f"  - {a['name']} | 节点数 {n} | {a['id']}")

aid = wf[0]['id']
payload = json.dumps({'message': 'hello', 'stream': True}).encode()
r = urllib.request.Request(BASE + '/chat/' + aid, data=payload,
                           headers={'Content-Type': 'application/json',
                                    'Authorization': f'Bearer {tok}'})
t0 = time.time()
buf = b''
try:
    with urllib.request.urlopen(r, timeout=150) as resp:
        while True:
            c = resp.read(1024)
            if not c:
                break
            buf += c
            if time.time() - t0 > 120:
                print('!! 超时 120s 主动断开')
                break
    txt = ''
    for line in buf.decode('utf-8', 'replace').splitlines():
        if line.startswith('data: '):
            try:
                d = json.loads(line[6:])
                if d.get('type') == 'chunk':
                    txt += d.get('content', '')
            except Exception:
                pass
    print(f"[OK] 工作流 agent {wf[0]['name']} | {time.time()-t0:.1f}s | {txt[:200]}")
except Exception as e:
    print(f"[FAIL] {type(e).__name__}: {e}")
