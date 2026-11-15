"""把无工作流的测试 Agent 改成演示友好的名字（仅改演示账号数据，可随时改回）。"""
import json
import sys
import urllib.request

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
BASE = 'http://127.0.0.1:8001/api/v1'
AGENT = '29dfb7a1-59ea-414a-99f5-67cbd75fc0c3'  # 原名 Aiiagent
NEW_NAME = '办公助手'
NEW_DESC = '把随手记的表格整理成图表与报表'

with urllib.request.urlopen(urllib.request.Request(
    BASE + '/auth/login',
    data=json.dumps({'email': 'smoke@test.com', 'password': 'Smoke@12345'}).encode(),
    headers={'Content-Type': 'application/json'}), timeout=15) as r:
    tok = json.loads(r.read())['token']

req = urllib.request.Request(
    BASE + f'/agents/{AGENT}',
    data=json.dumps({'name': NEW_NAME, 'description': NEW_DESC}).encode(),
    headers={'Authorization': f'Bearer {tok}', 'Content-Type': 'application/json'},
    method='PUT')
with urllib.request.urlopen(req, timeout=30) as r:
    d = json.loads(r.read())
print('改名后:', d.get('name'), '|', d.get('description'))
print('工作流节点数:', len((d.get('workflow_definition') or {}).get('nodes') or []))
