import json
import os
import sys
import urllib.parse
import urllib.request

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
BASE = 'http://127.0.0.1:8001/api/v1'
AGENT = '5496b56d-9548-4fe1-89b4-90941144c30c'
OUT = os.path.join(os.environ['TEMP'], 'af-ppt-slides')

with urllib.request.urlopen(urllib.request.Request(
    BASE + '/auth/login',
    data=json.dumps({'email': 'smoke@test.com', 'password': 'Smoke@12345'}).encode(),
    headers={'Content-Type': 'application/json'}), timeout=10) as r:
    tok = json.loads(r.read())['token']

req = urllib.request.Request(BASE + f'/pi/{AGENT}/workspace', headers={'Authorization': f'Bearer {tok}'})
data = urllib.request.urlopen(req, timeout=20).read()
ws = json.loads(data)
items = ws if isinstance(ws, list) else (ws.get('files') or ws.get('items') or [])
print('工作区文件:')
for f in items:
    print('  ', f.get('name'), f.get('size'))

os.makedirs(OUT, exist_ok=True)
previews = [f for f in items if f.get('name', '').startswith('AgentFlow_网页版预览')]
previews.sort(key=lambda f: f['name'])
print('\n预览图数量:', len(previews))
saved = []
for f in previews:
    rel = f['url'].replace('/api/v1', '')
    url = BASE + urllib.parse.quote(rel, safe='/?=&')
    rq = urllib.request.Request(url, headers={'Authorization': f'Bearer {tok}'})
    with urllib.request.urlopen(rq, timeout=30) as resp:
        blob = resp.read()
    p = os.path.join(OUT, f['name'])
    with open(p, 'wb') as fh:
        fh.write(blob)
    saved.append(p)
    print('  已保存', p, len(blob), 'bytes')
print('\nOUTDIR=' + OUT)
