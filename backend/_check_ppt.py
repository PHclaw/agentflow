import json
import sys
import time
import urllib.request

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
BASE = 'http://127.0.0.1:8001/api/v1'
AGENT = '5496b56d-9548-4fe1-89b4-90941144c30c'  # PPT 生成助手

with urllib.request.urlopen(urllib.request.Request(
    BASE + '/auth/login',
    data=json.dumps({'email': 'smoke@test.com', 'password': 'Smoke@12345'}).encode(),
    headers={'Content-Type': 'application/json'}), timeout=10) as r:
    tok = json.loads(r.read())['token']

# 先看 pi 运行时是否就绪
req = urllib.request.Request(BASE + '/pi/status', headers={'Authorization': f'Bearer {tok}'})
print('pi status:', urllib.request.urlopen(req, timeout=15).read().decode())

payload = json.dumps({
    'message': '做一份 4 页的产品介绍 PPT，主题是 AgentFlow 零代码 AI Agent 平台',
    'skills': ['ppt-generation'],
    'new_session': True,
}).encode()
req = urllib.request.Request(
    BASE + f'/pi/{AGENT}/stream',
    data=payload,
    headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {tok}'},
)
t0 = time.time()
buf = b''
events = {}
try:
    with urllib.request.urlopen(req, timeout=600) as resp:
        while True:
            chunk = resp.read(2048)
            if not chunk:
                break
            buf += chunk
            if time.time() - t0 > 420:
                print('!! 超过 420s 主动断开')
                break
except Exception as e:
    print('请求异常:', type(e).__name__, e)

print(f'耗时 {time.time()-t0:.1f}s, 字节 {len(buf)}')
text = buf.decode('utf-8', 'replace')
for line in text.splitlines():
    if line.startswith('data: '):
        try:
            d = json.loads(line[6:])
            t = d.get('type') or d.get('event')
            events[t] = events.get(t, 0) + 1
        except Exception:
            pass
print('事件类型统计:', events)

# 打印最后一段可读内容
tail = text[-1500:]
print('--- 尾部 ---')
print(tail)
