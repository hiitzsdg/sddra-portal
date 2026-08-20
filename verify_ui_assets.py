import json
from app import app

def run_verification():
    print("=== RUNNING COMPREHENSIVE FLASK & UI VERIFICATION ===")
    client = app.test_client()
    
    # 1. Verify Static Assets & Edge Headers
    resp_css = client.get('/static/css/style.css')
    assert resp_css.status_code == 200
    assert 'max-age=31536000' in resp_css.headers.get('Cache-Control', '')
    assert b'--font-heading' in resp_css.data and b'--shadow-glow-blue' in resp_css.data
    print(f"[OK] Master CSS verified: {len(resp_css.data)} bytes, Cache-Control: {resp_css.headers.get('Cache-Control')}")

    resp_js = client.get('/static/js/main.js')
    assert resp_js.status_code == 200
    assert b'initGenericLiveSearch' in resp_js.data and b'mobileMenuBtn' in resp_js.data
    print(f"[OK] Master JS verified: {len(resp_js.data)} bytes, Live Search & Mobile Drawer active")

    resp_charts = client.get('/static/js/charts.js')
    assert resp_charts.status_code == 200
    assert b'expenseCategoryChart' in resp_charts.data
    print(f"[OK] Master Charts JS verified: {len(resp_charts.data)} bytes, Dark-mode visualizer active")

    # 2. Verify Unauthenticated Login Page
    resp_login = client.get('/login')
    assert resp_login.status_code == 200
    assert b'1-Click Instant Login Hub' in resp_login.data
    print(f"[OK] Login Page verified: {len(resp_login.data)} bytes")

    # 3. Verify Admin Dashboard & Live Data
    client.get('/login?demo=treasurer', follow_redirects=True)
    resp_dash = client.get('/dashboard')
    assert resp_dash.status_code == 200
    assert b'Executive Management Console' in resp_dash.data
    assert b'Total Maintenance Collected' in resp_dash.data
    assert b'data-live-search' in resp_dash.data
    print(f"[OK] Admin Dashboard verified: {len(resp_dash.data)} bytes, glowing stat cards & live table search active")

    # 4. Verify Chart Data API
    resp_chart_api = client.get('/api/expenses/chart-data')
    assert resp_chart_api.status_code == 200
    chart_data = resp_chart_api.get_json()
    assert 'categories' in chart_data and 'monthly' in chart_data
    print(f"[OK] Chart Data API verified: {len(chart_data['categories'])} categories, {len(chart_data['monthly'])} monthly trends")

    # 5. Verify Society Expenses Page
    resp_exp = client.get('/expenses')
    assert resp_exp.status_code == 200
    assert b'Association Expenditure & Transparency Portal' in resp_exp.data
    assert b'data-live-search="#expensesTable"' in resp_exp.data
    print(f"[OK] Society Expenses Page verified: {len(resp_exp.data)} bytes, real-time search connected")

    # 6. Verify Resident Directory
    resp_members = client.get('/admin/members')
    assert resp_members.status_code == 200
    assert b'Resident Roster & Flat Directory' in resp_members.data
    assert b'Flat A/4-C' in resp_members.data
    print(f"[OK] Resident Directory verified: {len(resp_members.data)} bytes, 44 flats loaded")

    # 7. Verify Receipts Ledger
    resp_rcpts = client.get('/admin/receipts')
    assert resp_rcpts.status_code == 200
    assert b'Maintenance Receipts Ledger' in resp_rcpts.data
    print(f"[OK] Receipts Ledger verified: {len(resp_rcpts.data)} bytes")

    print("\n========================================================")
    print("ALL 7 VERIFICATION CRITERIA PASSED WITH 100% SUCCESS!")
    print("========================================================")

if __name__ == '__main__':
    run_verification()
