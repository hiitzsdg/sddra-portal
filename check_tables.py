import sqlite3

conn = sqlite3.connect('sddra.db')
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = [r[0] for r in cur.fetchall() if not r[0].startswith('sqlite_')]
for t in tables:
    cur.execute(f"SELECT COUNT(*) FROM {t};")
    cnt = cur.fetchone()[0]
    print(f"{t}: {cnt} rows")
conn.close()
