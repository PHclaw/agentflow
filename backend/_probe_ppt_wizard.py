"""跑通 PPT 生成技能的三轮向导，打印每轮完整回复，确认能否产出 pptx。"""
import json
import sys
import time
import urllib.request

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
BASE = 'http://127.0.0.1:8001/api/v1'

with urllib.request.urlopen(urllib.request.Request(
    BASE + '/auth/login',
    data=json.dumps({'email': 'smoke@test.com', 'password': 'Smoke@12345'}).encode(),
    headers={'Content-Type': 'application/json'}), timeout=15) as r:
    TOK = json.loads(r.read())['token']


def call(skill, text, sid, timeout=600):
    rq = urllib.request.Request(
        BASE + f'/skills/{skill}/call',
        data=json.dumps({'variables': {'input': text}, 'session_id': sid}).encode(),
        headers={'Authorization': f'Bearer {TOK}', 'Content-Type': 'application/json'})
    t0 = time.time()
    with urllib.request.urlopen(rq, timeout=timeout) as r:
        d = json.loads(r.read())
    d['cost'] = time.time() - t0
    return d


SID = 'probe-ppt-wizard-2'
turns = [
    '做一份 3 页的产品介绍 PPT，主题：AgentFlow 零代码 AI Agent 平台',
    '1b 2a 3a 4b',
    '1a',
]
for i, t in enumerate(turns, 1):
    d = call('ppt-generation', t, SID)
    tt = d.get('toolTrace') or {}
    out = d.get('output')
    reply = out if isinstance(out, str) else json.dumps(out, ensure_ascii=False)
    print(f'===== 第 {i} 轮  {d["cost"]:.1f}s  HTTP-ok =====')
    print('intent=', tt.get('intent'), '| exit=', tt.get('exitCode'))
    print('imageUrl=', tt.get('imageUrl'))
    print('downloadUrl=', tt.get('downloadUrl'), '| name=', tt.get('downloadName'))
    print('downloadUrls=', tt.get('downloadUrls'))
    print('note=', str(tt.get('note'))[:400])
    print('--- 完整回复 ---')
    print(reply)
    print()
