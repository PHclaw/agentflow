import sqlite3

c = sqlite3.connect('agentflow.db')
tables = [r[0] for r in c.execute("select name from sqlite_master where type='table'")]
llm_tables = [t for t in tables if 'llm' in t.lower() or 'model' in t.lower() or 'config' in t.lower()]
print('相关表:', llm_tables)
for t in llm_tables:
    try:
        cols = [d[1] for d in c.execute(f'pragma table_info({t})')]
        n = c.execute(f'select count(*) from {t}').fetchone()[0]
        print(f'\n--- {t} ({n} 行) cols={cols}')
        for r in c.execute(f'select * from {t} limit 5'):
            print('  ', r)
    except Exception as e:
        print(t, 'err', e)
