"""列出测试账号下的 Agent，并标注是否配置了工作流（有工作流会压制技能）。"""
import json
import sys
import urllib.request

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
BASE = 'http://127.0.0.1:8001/api/v1'

with urllib.request.urlopen(urllib.request.Request(
    BASE + '/auth/login',
    data=json.dumps({'email': 'smoke@test.com', 'password': 'Smoke@12345'}).encode(),
    headers={'Content-Type': 'application/json'}), timeout=15) as r:
    tok = json.loads(r.read())['token']

req = urllib.request.Request(BASE + '/agents', headers={'Authorization': f'Bearer {tok}'})
with urllib.request.urlopen(req, timeout=30) as r:
    agents = json.loads(r.read())

items = agents if isinstance(agents, list) else (agents.get('items') or agents.get('agents') or [])
print('Agent 总数:', len(items))
print()


def detail(aid):
    rq = urllib.request.Request(BASE + f'/agents/{aid}', headers={'Authorization': f'Bearer {tok}'})
    with urllib.request.urlopen(rq, timeout=30) as r:
        return json.loads(r.read())


clean = []
for a in items:
    aid = a.get('id')
    try:
        d = detail(aid)
    except Exception as e:
        print('  详情失败', a.get('name'), e)
        continue
    wf = d.get('workflow_definition')
    nodes = (wf or {}).get('nodes') or []
    has = len(nodes) > 0
    if not has:
        clean.append((a.get('name'), aid))
    print(f"{'[工作流]' if has else '[空    ]'} {a.get('name')}  id={aid}  "
          f"wfKind={d.get('workflow_kind') or (wf or {}).get('kind') if isinstance(wf, dict) else None}")

print('\n=== 无工作流（可用于技能演示）===')
for name, aid in clean:
    print('  -', name, '| id=', aid)
