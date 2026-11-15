"""腾一个 Agent 名额，并验证「套模板建 Agent → 直接对话」这条链路能不能跑通。"""
import json
import sys
import urllib.request

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
BASE = 'http://127.0.0.1:8001/api/v1'
DROP = '161fee8b-23cc-4ce3-a17b-b664acf21621'   # 未命名工作流，0 会话，最可弃
TEMPLATE = 'c631c391-b05a-4d3f-b0d5-d88f6b9cd841'  # HR 助手 模板

with urllib.request.urlopen(urllib.request.Request(
    BASE + '/auth/login',
    data=json.dumps({'email': 'smoke@test.com', 'password': 'Smoke@12345'}).encode(),
    headers={'Content-Type': 'application/json'}), timeout=15) as r:
    TOK = json.loads(r.read())['token']


def req(method, path, payload=None, timeout=300):
    h = {'Authorization': f'Bearer {TOK}'}
    data = None
    if payload is not None:
        data = json.dumps(payload).encode()
        h['Content-Type'] = 'application/json'
    rq = urllib.request.Request(BASE + path, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(rq, timeout=timeout) as r:
            return r.status, json.loads(r.read() or b'{}')
    except Exception as e:
        body = ''
        try:
            body = e.read().decode('utf-8', 'replace')[:300]
        except Exception:
            pass
        return getattr(e, 'code', 'ERR'), {'_err': f'{type(e).__name__}: {e}', '_body': body}


print('=== 删除废弃 Agent 腾名额 ===')
st, d = req('DELETE', f'/agents/{DROP}')
print('删除状态:', st, '|', json.dumps(d, ensure_ascii=False)[:150])

print('\n=== 套模板建 Agent ===')
st, tpl = req('GET', f'/templates/{TEMPLATE}')
print('模板:', tpl.get('name'), '| 工作流节点数=', len((tpl.get('workflow_definition') or {}).get('nodes') or []))

st, new = req('POST', '/agents', {
    'name': 'HR 助手',
    'description': tpl.get('description') or '假期政策、薪资咨询',
    'llm_config': {'provider': 'openai', 'model': '', 'temperature': 0.7, 'max_tokens': 2000},
    'system_prompt': '你是 HR 助手，回答员工关于假期、薪资、福利的问题。',
    'workflow_definition': tpl.get('workflow_definition') or {'nodes': [], 'edges': [], 'entry': 'start'},
})
print('创建状态:', st, '| id=', new.get('id'), '| name=', new.get('name'))
if st >= 400:
    print('失败:', json.dumps(new, ensure_ascii=False)[:300])
    raise SystemExit(1)

AID = new['id']
print('\n=== 新 Agent 直接对话（工作流链路） ===')
st, chat = req('POST', f'/chat/{AID}',
               {'message': '年假有几天？怎么申请？', 'stream': False, 'new_session': True}, 300)
print('状态:', st)
print('回复:', json.dumps(chat, ensure_ascii=False)[:600])

print('\n=== 空工作流 Agent 对话（PiAgent 链路） ===')
st, new2 = req('POST', '/agents', {
    'name': '演示助手',
    'description': '零代码演示用',
    'llm_config': {'provider': 'openai', 'model': '', 'temperature': 0.7, 'max_tokens': 2000},
    'workflow_definition': {'nodes': [], 'edges': [], 'entry': 'start'},
})
print('创建状态:', st, '| id=', new2.get('id'))
