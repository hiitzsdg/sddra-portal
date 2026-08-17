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
    print("--- tbl_admins ---")
    cur.execute("SELECT * FROM tbl_admins;")
    for r in cur.fetchall():
        print(" ", r)
        
    print("\n--- tbl_membership (first 5) ---")
    cur.execute("SELECT * FROM tbl_membership LIMIT 5;")
    for r in cur.fetchall():
        print(" ", r)
        
    print("\n--- tbl_mbr_cntct (first 5) ---")
    cur.execute("SELECT * FROM tbl_mbr_cntct LIMIT 5;")
    for r in cur.fetchall():
        print(" ", r)
        
    print("\n--- tbl_expenses (first 5) ---")
    cur.execute("SELECT * FROM tbl_expenses LIMIT 5;")
    for r in cur.fetchall():
        print(" ", r)
        
    print("\n--- tbl_receipts (first 5) ---")
    cur.execute("SELECT * FROM tbl_receipts ORDER BY receipt_no DESC LIMIT 5;")
    for r in cur.fetchall():
        print(" ", r)

conn.close()
