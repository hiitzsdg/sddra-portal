import sqlite3
import json

conn = sqlite3.connect('sddra.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()

def dump_table(tbl):
    cur.execute(f"SELECT * FROM {tbl}")
    rows = cur.fetchall()
    return [dict(r) for r in rows]

membership = dump_table('tbl_membership')
contacts = dump_table('tbl_mbr_cntct')
receipts = dump_table('tbl_receipts')
expenses = dump_table('tbl_expenses')
admins = dump_table('tbl_admins')
notices = dump_table('tbl_notices')

conn.close()

with open('seed_data.py', 'w', encoding='utf-8') as f:
    f.write('"""Embedded dataset for instant cloud database provisioning with zero file dependencies."""\n\n')
    f.write(f'SEED_MEMBERSHIP = {repr(membership)}\n\n')
    f.write(f'SEED_CONTACTS = {repr(contacts)}\n\n')
    f.write(f'SEED_RECEIPTS = {repr(receipts)}\n\n')
    f.write(f'SEED_EXPENSES = {repr(expenses)}\n\n')
    f.write(f'SEED_ADMINS = {repr(admins)}\n\n')
    f.write(f'SEED_NOTICES = {repr(notices)}\n')

print(f"Generated seed_data.py: {len(membership)} members, {len(contacts)} contacts, {len(receipts)} receipts, {len(expenses)} expenses.")
