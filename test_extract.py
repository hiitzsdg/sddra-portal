import os
import sqlite3
import pymysql
from config import Config

def test_sync():
    sq_conn = sqlite3.connect('sddra.db')
    sq_conn.row_factory = sqlite3.Row
    sq_cur = sq_conn.cursor()
    
    tables = [
        'tbl_membership',
        'tbl_mbr_cntct',
        'tbl_receipts',
        'tbl_expenses',
        'tbl_admins',
        'tbl_notices'
    ]
    
    print("Testing extraction from sddra.db:")
    for tbl in tables:
        sq_cur.execute(f"SELECT * FROM {tbl}")
        rows = sq_cur.fetchall()
        if rows:
            cols = rows[0].keys()
            print(f"{tbl}: {len(rows)} rows, columns: {list(cols)}")
    sq_conn.close()

if __name__ == '__main__':
    test_sync()
