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
    print("--- DISTINCT PARTICULARS IN tbl_expenses ---")
    cur.execute("SELECT DISTINCT particulars, COUNT(*) as cnt FROM tbl_expenses GROUP BY particulars;")
    for r in cur.fetchall():
        print(" ", r)
        
    print("\n--- DISTINCT SPL_HEAD IN tbl_expenses ---")
    cur.execute("SELECT DISTINCT spl_head, COUNT(*) as cnt FROM tbl_expenses GROUP BY spl_head;")
    for r in cur.fetchall():
        print(" ", r)
        
    print("\n--- EXPENSE TOTALS BY YEAR/MONTH ---")
    cur.execute("SELECT DATE_FORMAT(voucher_date, '%Y-%m') as ym, SUM(amount) as total FROM tbl_expenses GROUP BY ym ORDER BY ym DESC;")
    for r in cur.fetchall():
        print(" ", r)

    print("\n--- RECEIPT TOTALS BY YEAR/MONTH ---")
    cur.execute("SELECT DATE_FORMAT(receipt_date, '%Y-%m') as ym, SUM(amount) as total, COUNT(*) as cnt FROM tbl_receipts GROUP BY ym ORDER BY ym DESC;")
    for r in cur.fetchall():
        print(" ", r)

conn.close()
