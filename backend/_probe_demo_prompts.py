"""批量探测：候选演示问题在各技能上的实际表现（intent / 耗时 / 产出 / 回复片段）。"""
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


def call(skill, text, timeout=180):
    req = urllib.request.Request(
        BASE + f'/skills/{skill}/call',
        data=json.dumps({'variables': {'input': text}}).encode(),
        headers={'Authorization': f'Bearer {TOK}', 'Content-Type': 'application/json'})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = json.loads(r.read())
    except Exception as e:
        body = ''
        try:
            body = e.read().decode('utf-8', 'replace')[:400]
        except Exception:
            pass
        return {'error': f'{type(e).__name__}: {e} | body={body}', 'cost': time.time() - t0}
    d['cost'] = time.time() - t0
    return d


CASES = [
    ('excel', '零售-柱状图', '月份  铅笔  钢笔  橡皮\n1月  10支  8支  5块\n2月  12支  9支  6块\n3月  15支  11支  9块\n\n请按月份画出销量的柱状图'),
    ('excel', '财务-折线A', '月份  营收\n1月  120万\n2月  158万\n3月  142万\n4月  186万\n\n请画出营收的折线图'),
    ('excel', '财务-折线B', '季度  营收  成本\nQ1  1200万  800万\nQ2  1580万  960万\nQ3  1420万  910万\nQ4  1860万  1120万\n\n按季度画出营收和成本的折线图'),
    ('excel', '运营-饼图', '渠道  访问量\n自然搜索  4200\n社交媒体  3100\n广告投放  2600\n直接访问  1500\n\n请画出各渠道占比的饼图'),
    ('excel', '物流-横向柱状图', '地区  单量\n华东  18600\n华南  14200\n华北  11800\n西南  7600\n\n请画出各地区单量的横向柱状图'),
    ('excel', 'HR-透视导出', '部门  职级  人数\n研发  初级  30\n研发  高级  18\n市场  初级  12\n市场  高级  8\n销售  初级  25\n销售  高级  15\n\n按部门汇总人数并导出 Excel'),
]

for skill, label, text in CASES:
    d = call(skill, text)
    print('=' * 70)
    if 'error' in d:
        print(f'[{skill}/{label}] 失败 ({d["cost"]:.1f}s): {d["error"]}')
        continue
    tt = d.get('toolTrace') or {}
    out = d.get('output')
    if isinstance(out, str):
        reply = out
    elif isinstance(out, dict):
        reply = out.get('reply') or out.get('content') or out.get('text') or json.dumps(out, ensure_ascii=False)
    else:
        reply = str(out or '')
    print(f'[{skill}/{label}] {d["cost"]:.1f}s  intent={tt.get("intent")} exit={tt.get("exitCode")}')
    print(f'  imageUrl={tt.get("imageUrl")}')
    print(f'  downloadUrl={tt.get("downloadUrl")} name={tt.get("downloadName")}')
    print(f'  note={str(tt.get("note"))[:200]}')
    print(f'  reply({len(reply)}字): {reply[:400]}')
