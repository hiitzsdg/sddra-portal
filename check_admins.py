import pymysql
import bcrypt
from werkzeug.security import generate_password_hash, check_password_hash

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
    # Check tbl_admins
    cur.execute("SELECT * FROM tbl_admins;")
    admins = cur.fetchall()
    print("Admins in tbl_admins:")
    for a in admins:
        print(" ", a)
        
    # Check if we can verify passwords
    for a in admins:
        h = a['password_hash']
        for test_p in ['admin', 'treasurer', 'passwd', 'password', 'sdera@123', 'sddra@123', '123456', 'root']:
            try:
                if bcrypt.checkpw(test_p.encode('utf-8'), h.encode('utf-8')):
                    print(f" MATCH FOUND! Admin '{a['username']}' password is: '{test_p}'")
            except Exception:
                pass

conn.close()
