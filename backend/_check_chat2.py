import json
import time
import urllib.request

BASE = 'http://127.0.0.1:8001/api/v1'
with urllib.request.urlopen(urllib.request.Request(
    BASE + '/auth/login',
    data=json.dumps({'email': 'smoke@test.com', 'password': 'Smoke@12345'}).encode(),
    headers={'Content-Type': 'application/json'}), timeout=10) as r:
    tok = json.loads(r.read())['token']

payload = json.dumps({'message': '你好，请用一句话介绍你自己', 'stream': True}).encode()
req = urllib.request.Request(
    BASE + '/chat/29dfb7a1-59ea-414a-99f5-67cbd75fc0c3',
    data=payload,
    headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {tok}'},
)
t0 = time.time()
buf = b''
with urllib.request.urlopen(req, timeout=180) as r:
    while True:
        chunk = r.read(1024)
        if not chunk:
            break
        buf += chunk
        if time.time() - t0 > 60:
            break
print(f'耗时 {time.time()-t0:.1f}s, 长度 {len(buf)}')
print('--- 原始内容 ---')
print(buf.decode('utf-8', 'replace'))
