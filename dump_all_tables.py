import pymysql

conn = pymysql.connect(
    host='localhost',
    port=3306,
    user='root',
    password='passwd',
    database='sddra_billing',
    charset='utf8mb4',
    cursorclass=pymysql.cursors.DictCursor
)

with conn.cursor() as cur:
    cur.execute("SHOW TABLES;")
    tables = [list(r.values())[0] for r in cur.fetchall()]
    print("ALL TABLES IN sddra_billing:", tables)
    
    for t in tables:
        cur.execute(f"SELECT COUNT(*) as cnt FROM `{t}`;")
        cnt = cur.fetchone()['cnt']
        print(f"\nTABLE: {t} (Total Rows: {cnt})")
        cur.execute(f"DESCRIBE `{t}`;")
        for col in cur.fetchall():
            print(f"   {col['Field']}: {col['Type']} (Null: {col['Null']}, Key: {col['Key']})")

conn.close()
