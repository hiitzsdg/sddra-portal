from app import app
from database import query_db

client = app.test_client()

# 1. Login as treasurer
r1 = client.post('/login', data={'username': 'treasurer', 'password': 'sdera@123'}, follow_redirects=True)
print('Treasurer login status:', r1.status_code)

# 2. Get latest voucher
v = query_db('SELECT * FROM tbl_expenses ORDER BY voucher_no DESC LIMIT 1', one=True)
v_no = v['voucher_no']
print(f'Testing edit on Voucher #{v_no}: original desc = "{v["expense_description"]}"')

# 3. Edit voucher
r2 = client.post(f'/admin/expenses/{v_no}/edit', data={
    'voucher_date': '2026-08-20',
    'expense_description': 'Updated Security Guard Monthly Payroll',
    'particulars': 'Service Charges',
    'spl_head': 'Security',
    'payment_by': 'Online',
    'amount': '19500.00'
}, follow_redirects=True)
print('Edit status code:', r2.status_code)
print('Flash success message in response:', b'updated successfully' in r2.data)

# 4. Verify in db
v_after = query_db('SELECT * FROM tbl_expenses WHERE voucher_no = %s', (v_no,), one=True)
print('Updated Voucher from DB:', v_after)
