import json
import time
import urllib.request

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
no_wf = [a for a in agents if not (a.get('workflow_definition') or {}).get('nodes')]
for a in no_wf:
    aid = a['id']
    payload = json.dumps({'message': '用一句话介绍你自己', 'stream': True}).encode()
    r = urllib.request.Request(BASE + '/chat/' + aid, data=payload,
                               headers={'Content-Type': 'application/json',
                                        'Authorization': f'Bearer {tok}'})
    t0 = time.time()
    buf = b''
    try:
        with urllib.request.urlopen(r, timeout=120) as resp:
            while True:
                c = resp.read(1024)
                if not c:
                    break
                buf += c
                if time.time() - t0 > 90:
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
        print(f"[OK] {a['name']} ({aid}) | {time.time()-t0:.1f}s | {txt[:120]}")
    except Exception as e:
        print(f"[FAIL] {a['name']} ({aid}) | {e}")
