import pymysql

try:
    conn = pymysql.connect(
        host='localhost',
        port=3306,
        user='root',
        password='passwd',
        database='sddra_billing',
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )
    print("SUCCESS: Connected to sddra_billing database!")
    with conn.cursor() as cur:
        cur.execute("SHOW TABLES;")
        tables = cur.fetchall()
        print("TABLES in sddra_billing:", tables)
        
        for t_dict in tables:
            t_name = list(t_dict.values())[0]
            print(f"\n================ TABLE: {t_name} ================")
            cur.execute(f"DESCRIBE `{t_name}`;")
            cols = cur.fetchall()
            for c in cols:
                print("  ", c)
            
            cur.execute(f"SELECT * FROM `{t_name}` LIMIT 5;")
            rows = cur.fetchall()
            print(f"  --- Sample Data ({len(rows)} rows) ---")
            for r in rows:
                print("   ", r)
    conn.close()
except Exception as e:
    print("Connection error:", e)
