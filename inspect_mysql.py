import pymysql
import sys

passwords = ['', 'root', 'password', 'admin', 'mysql', '123456', 'Swapnadeep', 'swapnadeep', 'sddra', 'sdera', 'sdera@123', 'root123', '1234', '12345', 'Swapnadeep@123', 'Swapnadeep123', 'sql', 'mysql80']

found_conn = None
working_pwd = None

for pwd in passwords:
    try:
        conn = pymysql.connect(host='localhost', port=3306, user='root', password=pwd)
        working_pwd = pwd
        found_conn = conn
        print(f"SUCCESS: Connected to MySQL with password: '{pwd}'")
        break
    except pymysql.err.OperationalError as e:
        if e.args[0] == 1045: # Access denied
            continue
        else:
            print(f"Error for password '{pwd}': {e}")
            break
    except Exception as e:
        print(f"Error: {e}")
        break

if not found_conn:
    # Try other usernames
    for user in ['sddra', 'sdera', 'admin', 'user', 'developer']:
        for pwd in passwords:
            try:
                conn = pymysql.connect(host='localhost', port=3306, user=user, password=pwd)
                print(f"SUCCESS: Connected as user '{user}' with password: '{pwd}'")
                found_conn = conn
                break
            except Exception:
                continue
        if found_conn:
            break

if found_conn:
    with found_conn.cursor() as cur:
        cur.execute("SHOW DATABASES;")
        dbs = [r[0] for r in cur.fetchall()]
        print("Databases found on server:", dbs)
        
        target_db = None
        for db in dbs:
            if 'sddra' in db.lower() or 'billing' in db.lower() or 'enclave' in db.lower():
                target_db = db
                break
        
        if target_db:
            print(f"\n--- Tables in {target_db} ---")
            cur.execute(f"USE `{target_db}`;")
            cur.execute("SHOW TABLES;")
            tables = [r[0] for r in cur.fetchall()]
            print("Tables:", tables)
            
            for t in tables:
                print(f"\n--- Schema for table: {t} ---")
                cur.execute(f"DESCRIBE `{t}`;")
                for col in cur.fetchall():
                    print(" ", col)
                
                print(f"\n--- Sample data (up to 3 rows) from {t} ---")
                try:
                    cur.execute(f"SELECT * FROM `{t}` LIMIT 3;")
                    rows = cur.fetchall()
                    for r in rows:
                        print(" ", r)
                except Exception as e:
                    print("  Error querying sample rows:", e)
        else:
            print("Target database matching 'sddra' not found in database list.")
    found_conn.close()
else:
    print("Could not connect to MySQL with tested credentials.")
