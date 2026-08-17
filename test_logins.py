from app import app
from database import query_db

client = app.test_client()

# Fetch all flats from database
flats = query_db("SELECT flat_no, member_name FROM tbl_membership")

print(f"Testing login POST for {len(flats)} flats...")
errors = []

for f in flats:
    flat_no = f['flat_no']
    # Test standard flat_no
    resp = client.post('/login', data={'username': flat_no, 'password': 'sdera@123'}, follow_redirects=True)
    if resp.status_code != 200:
        errors.append((flat_no, resp.status_code, "Failed standard"))
    elif b'Internal Server Error' in resp.data:
        errors.append((flat_no, 500, "500 in body"))
        
    # Test variations (lowercase, dash instead of slash, etc.)
    for variant in [flat_no.lower(), flat_no.replace('/', '-'), flat_no.replace('/', ''), flat_no.upper()]:
        resp_v = client.post('/login', data={'username': variant, 'password': 'sdera@123'}, follow_redirects=True)
        if resp_v.status_code == 500 or b'Internal Server Error' in resp_v.data:
            errors.append((variant, 500, "500 on variant"))

# Test admin logins
for admin_u, pwd in [('admin', 'passwd'), ('treasurer', 'sdera@123'), ('president', 'sdera@123'), ('secretary', 'sdera@123'), ('caretaker', 'sdera@123')]:
    resp = client.post('/login', data={'username': admin_u, 'password': pwd}, follow_redirects=True)
    if resp.status_code != 200 or b'Internal Server Error' in resp.data:
        errors.append((admin_u, resp.status_code, "Admin login error"))

# Test invalid login / blank login
resp_bad = client.post('/login', data={'username': 'invalid_user_999', 'password': 'wrong_password'}, follow_redirects=True)
if resp_bad.status_code != 200 or b'Internal Server Error' in resp_bad.data:
    errors.append(('invalid_user', resp_bad.status_code, "Invalid user error"))

print("Errors found:", errors if errors else "NONE! All tested logins succeeded.")
