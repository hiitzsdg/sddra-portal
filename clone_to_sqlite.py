import sqlite3
import pymysql
import os

mysql_conn = pymysql.connect(
    host='localhost',
    port=3306,
    user='root',
    password='passwd',
    database='sddra_billing',
    charset='utf8mb4',
    cursorclass=pymysql.cursors.DictCursor
)

sqlite_path = os.path.join(os.path.dirname(__file__), 'sddra.db')
if os.path.exists(sqlite_path):
    os.remove(sqlite_path)

sqlite_conn = sqlite3.connect(sqlite_path)
sqlite_cur = sqlite_conn.cursor()

# Create SQLite tables matching MySQL
sqlite_cur.executescript("""
CREATE TABLE IF NOT EXISTS tbl_membership (
    id INTEGER PRIMARY KEY,
    flat_no TEXT NOT NULL,
    member_name TEXT NOT NULL,
    RvsdFlatSize REAL,
    car_parking_space TEXT,
    cps_owner INTEGER,
    tws_owner INTEGER,
    tws_count INTEGER,
    flat_charges REAL,
    common_expenses REAL,
    cps_charges REAL,
    tws_charges REAL,
    capital_fund REAL,
    monthly_charge REAL,
    password_hash TEXT
);

CREATE TABLE IF NOT EXISTS tbl_mbr_cntct (
    flat_no TEXT PRIMARY KEY,
    mobile_num_1 TEXT,
    mobile_num_2 TEXT,
    email_1 TEXT,
    email_2 TEXT
);

CREATE TABLE IF NOT EXISTS tbl_receipts (
    receipt_no INTEGER PRIMARY KEY,
    flat_no TEXT,
    member_name TEXT,
    amount REAL,
    pymnt_mode TEXT,
    subscription_type TEXT,
    remarks TEXT,
    payment_date TEXT,
    receipt_date TEXT,
    coverage_start TEXT,
    coverage_end TEXT
);

CREATE TABLE IF NOT EXISTS tbl_expenses (
    voucher_no INTEGER PRIMARY KEY,
    voucher_date TEXT,
    expense_description TEXT,
    particulars TEXT,
    spl_head TEXT,
    payment_by TEXT,
    amount REAL,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS tbl_admins (
    admin_id INTEGER PRIMARY KEY,
    username TEXT UNIQUE,
    password_hash TEXT,
    created_at TEXT,
    role TEXT
);

CREATE TABLE IF NOT EXISTS tbl_email_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    receipt_no INTEGER,
    flat_no TEXT,
    recipient_email TEXT,
    status TEXT,
    status_message TEXT,
    sent_at TEXT
);
""")

with mysql_conn.cursor() as cur:
    # 1. tbl_membership
    cur.execute("SELECT * FROM tbl_membership;")
    rows = cur.fetchall()
    for r in rows:
        sqlite_cur.execute("""
            INSERT INTO tbl_membership (id, flat_no, member_name, RvsdFlatSize, car_parking_space, cps_owner, tws_owner, tws_count, flat_charges, common_expenses, cps_charges, tws_charges, capital_fund, monthly_charge, password_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (r['id'], r['flat_no'], r['member_name'], r['RvsdFlatSize'], r['car_parking_space'], r['cps_owner'], r['tws_owner'], r['tws_count'], r['flat_charges'], r['common_expenses'], r['cps_charges'], r['tws_charges'], r['capital_fund'], r['monthly_charge'], r['password_hash']))
    print(f"Copied {len(rows)} members to sddra.db")

    # 2. tbl_mbr_cntct
    cur.execute("SELECT * FROM tbl_mbr_cntct;")
    rows = cur.fetchall()
    for r in rows:
        sqlite_cur.execute("""
            INSERT INTO tbl_mbr_cntct (flat_no, mobile_num_1, mobile_num_2, email_1, email_2)
            VALUES (?, ?, ?, ?, ?)
        """, (r['flat_no'], r['mobile_num_1'], r['mobile_num_2'], r['email_1'], r['email_2']))
    print(f"Copied {len(rows)} contacts to sddra.db")

    # 3. tbl_receipts
    cur.execute("SELECT * FROM tbl_receipts;")
    rows = cur.fetchall()
    for r in rows:
        sqlite_cur.execute("""
            INSERT INTO tbl_receipts (receipt_no, flat_no, member_name, amount, pymnt_mode, subscription_type, remarks, payment_date, receipt_date, coverage_start, coverage_end)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (r['receipt_no'], r['flat_no'], r['member_name'], float(r['amount'] or 0), r['pymnt_mode'], r['subscription_type'], r['remarks'], str(r['payment_date']), str(r['receipt_date']), str(r['coverage_start']), str(r['coverage_end'])))
    print(f"Copied {len(rows)} receipts to sddra.db")

    # 4. tbl_expenses
    cur.execute("SELECT * FROM tbl_expenses;")
    rows = cur.fetchall()
    for r in rows:
        sqlite_cur.execute("""
            INSERT INTO tbl_expenses (voucher_no, voucher_date, expense_description, particulars, spl_head, payment_by, amount, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (r['voucher_no'], str(r['voucher_date']), r['expense_description'], r['particulars'], r['spl_head'], r['payment_by'], float(r['amount'] or 0), str(r['created_at'])))
    print(f"Copied {len(rows)} expenses to sddra.db")

    # 5. tbl_admins
    cur.execute("SELECT * FROM tbl_admins;")
    rows = cur.fetchall()
    for r in rows:
        sqlite_cur.execute("""
            INSERT INTO tbl_admins (admin_id, username, password_hash, created_at, role)
            VALUES (?, ?, ?, ?, ?)
        """, (r['admin_id'], r['username'], r['password_hash'], str(r['created_at']), r['role']))
    print(f"Copied {len(rows)} admins to sddra.db")

sqlite_conn.commit()
sqlite_conn.close()
mysql_conn.close()
print("Cloning complete! sddra.db now has all actual data ready for Vercel.")
