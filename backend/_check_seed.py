import sqlite3

c = sqlite3.connect('agentflow.db')
print('--- users ---')
for r in c.execute("select id, email, is_active from users"):
    print(r)
for t in ('agents', 'conversations', 'skills', 'knowledge_bases', 'documents'):
    try:
        n = c.execute(f"select count(*) from {t}").fetchone()[0]
        print(f'{t}: {n}')
    except Exception as e:
        print(f'{t}: n/a ({e})')
