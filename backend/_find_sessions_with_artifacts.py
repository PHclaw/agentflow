"""自动定位含产物（artifact）附件的会话。

接口结构（已确认）：
  GET /chat/{agent_id}/sessions          -> [ {id, title, updated_at, ...}, ... ]
  GET /chat/{agent_id}/history?session_id=<id>
        -> [ {id, role, content, timestamp, files?}, ... ]
           其中 assistant 消息可能带有 files: [ {name, ...}, ... ]
"""
import json
import sys
import urllib.request

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE = 'http://127.0.0.1:8001/api/v1'
EMAIL = 'smoke@test.com'
PASSWORD = 'Smoke@12345'


def post(path, payload):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(payload).encode(),
        headers={'Content-Type': 'application/json'},
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def get(path, tok):
    req = urllib.request.Request(BASE + path, headers={'Authorization': f'Bearer {tok}'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def unwrap(data, *keys):
    if isinstance(data, list):
        return data
    for k in keys:
        if isinstance(data.get(k), list):
            return data[k]
    return []


def main():
    tok = post('/auth/login', {'email': EMAIL, 'password': PASSWORD})['token']

    agents = unwrap(get('/agents', tok), 'items', 'agents')
    if not agents:
        print('未找到任何 Agent')
        return

    found = []
    for agent in agents:
        aid = agent.get('id')
        if not aid:
            continue
        sessions = unwrap(get(f'/chat/{aid}/sessions', tok), 'items', 'sessions')
        for s in sessions:
            sid = s.get('id') or s.get('session_id')
            if not sid:
                continue
            msgs = unwrap(get(f'/chat/{aid}/history?session_id={sid}', tok), 'messages', 'items')
            files = []
            for m in msgs:
                for f in (m.get('files') or []):
                    name = f.get('name') or f.get('filename')
                    if name:
                        files.append(name)
            if files:
                found.append({
                    'agent_id': aid,
                    'session_id': sid,
                    'title': s.get('title') or '',
                    'updated_at': s.get('updated_at') or s.get('created_at'),
                    'files': files,
                })

    print(f'共扫描 Agent {len(agents)} 个，含产物的会话 {len(found)} 个\n')
    for item in found:
        print(f"[{item['session_id']}] {item['title']}")
        print(f"  agent={item['agent_id']}  time={item['updated_at']}")
        print(f"  产物 {len(item['files'])} 个:")
        for n in item['files']:
            print(f'    - {n}')
        print()

    print('JSON:')
    print(json.dumps(found, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
