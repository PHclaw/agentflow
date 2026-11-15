"""showcase 前置验证：建 Agent / 模板分类 / PPT 生成技能。"""
import json
import sys
import urllib.request

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
BASE = 'http://127.0.0.1:8001/api/v1'

with urllib.request.urlopen(urllib.request.Request(
    BASE + '/auth/login',
    data=json.dumps({'email': 'smoke@test.com', 'password': 'Smoke@12345'}).encode(),
    headers={'Content-Type': 'application/json'}), timeout=15) as r:
    TOK = json.loads(r.read())['token']


def req(method, path, payload=None, timeout=200):
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


print('=== 模板分类 ===')
st, tpls = req('GET', '/templates')
items = tpls if isinstance(tpls, list) else (tpls.get('items') or tpls.get('templates') or [])
print('模板数:', len(items))
for t in items[:12]:
    print(f"  - {t.get('name')} | cat={t.get('category')} | id={t.get('id')}")

print('\n=== 建 Agent（验证名额） ===')
st, new = req('POST', '/agents', {
    'name': '演示-周报助手',
    'description': '把一周的工作记录整理成周报',
    'llm_config': {'provider': 'openai', 'model': '', 'temperature': 0.7, 'max_tokens': 2000},
    'system_prompt': '你是周报助手，负责把零散的工作记录整理成结构化周报。',
    'workflow_definition': {'nodes': [], 'edges': [], 'entry': 'start'},
})
print('状态:', st, '| id=', new.get('id'), '| name=', new.get('name'))
if st >= 400:
    print('失败:', json.dumps(new, ensure_ascii=False)[:300])
else:
    AGENT_ID = new.get('id')
    print('\n=== 新 Agent 对话（内置链路） ===')
    st, chat = req('POST', f'/chat/{AGENT_ID}',
                   {'message': '你好，请用一句话介绍你能做什么', 'stream': False, 'new_session': True}, 240)
    print('状态:', st)
    print('回复:', json.dumps(chat, ensure_ascii=False)[:500])

print('\n=== PPT 生成技能（ppt-generation，非 ppt-master） ===')
st, res = req('POST', '/skills/ppt-generation/call', {
    'variables': {'input': '做一份 3 页的产品介绍 PPT，主题：AgentFlow 零代码 AI Agent 平台'}
}, 400)
print('状态:', st)
tt = res.get('toolTrace') or {}
out = res.get('output')
reply = out if isinstance(out, str) else json.dumps(out, ensure_ascii=False)
print('intent=', tt.get('intent'), '| exit=', tt.get('exitCode'), '| imageUrl=', tt.get('imageUrl'))
print('downloadUrl=', tt.get('downloadUrl'), '| name=', tt.get('downloadName'))
print('note=', str(tt.get('note'))[:300])
print('reply:', reply[:400])
