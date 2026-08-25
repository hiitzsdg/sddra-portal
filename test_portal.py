import unittest
from app import app
from database import query_db, execute_db, init_db

class TestSDDRABillingPortal(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        self.client = app.test_client()
        app.config['TESTING'] = True

    def test_01_public_redirect(self):
        """Unauthenticated user visiting / is redirected to /login"""
        resp = self.client.get('/', follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/login', resp.headers['Location'])

    def test_02_resident_login_and_dashboard(self):
        """Resident login works and shows only own flat details and receipts"""
        resp = self.client.get('/login?demo=A/4-C', follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Swapnadeep Ganguly', resp.data)
        self.assertIn(b'A/4-C', resp.data)
        self.assertIn(b'My Flat Maintenance Receipts', resp.data)

    def test_03_resident_rbac_restrictions(self):
        """Regular resident can view directory in read-only mode, but cannot edit members or access admin receipts ledger"""
        self.client.get('/login?demo=A/4-C', follow_redirects=True)
        
        # Resident has read-only view access to directory
        resp = self.client.get('/admin/members', follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Resident Directory', resp.data)
        self.assertNotIn(b'<th>Total Paid</th>', resp.data)
        
        # Resident cannot access master receipts ledger
        resp2 = self.client.get('/admin/receipts', follow_redirects=True)
        self.assertIn(b'Access Denied', resp2.data)

        # Resident cannot post member updates
        resp3 = self.client.post('/admin/members/update', data={'flat_no': 'A/1-A', 'member_name': 'Hacker'}, follow_redirects=True)
        self.assertIn(b'Access Denied', resp3.data)

    def test_04_resident_cannot_view_others_receipt(self):
        """Regular resident cannot view another resident's receipt"""
        other_receipt = query_db("SELECT receipt_no FROM tbl_receipts WHERE flat_no = 'A/1-A' LIMIT 1", one=True)
        self.assertIsNotNone(other_receipt)
        
        self.client.get('/login?demo=A/4-C', follow_redirects=True)
        
        resp = self.client.get(f'/receipts/{other_receipt["receipt_no"]}', follow_redirects=True)
        self.assertIn(b'Access Denied', resp.data)

    def test_05_admin_login_and_access(self):
        """Treasurer / Admin has full administrative access to all 44 flats and 190 receipts after password authentication"""
        resp = self.client.post('/login', data={'username': 'treasurer', 'password': 'sdera@123'}, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Executive Management Console', resp.data)
        
        resp_members = self.client.get('/admin/members')
        self.assertEqual(resp_members.status_code, 200)
        self.assertIn(b'Resident Directory', resp_members.data)
        self.assertIn(b'Flat A/1-A', resp_members.data)
        self.assertIn(b'Flat A/4-C', resp_members.data)
        self.assertIn(b'<th>Total Paid</th>', resp_members.data)

        resp_rcpt = self.client.get('/admin/receipts')
        self.assertEqual(resp_rcpt.status_code, 200)
        self.assertIn(b'Receipts Ledger', resp_rcpt.data)

    def test_06_expenses_transparency_and_charts(self):
        """All members can view actual 81 expense vouchers and chart API"""
        self.client.get('/login?demo=A/4-C', follow_redirects=True)
        
        resp = self.client.get('/expenses')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Association Expenditure', resp.data)
        self.assertIn(b'Service Charges', resp.data)
        
        chart_resp = self.client.get('/api/expenses/chart-data')
        self.assertEqual(chart_resp.status_code, 200)
        json_data = chart_resp.get_json()
        self.assertIn('categories', json_data)
        self.assertIn('monthly', json_data)
        self.assertTrue(len(json_data['categories']) > 0)

    def test_07_email_receipt_dispatch(self):
        """Email receipt dispatch endpoint returns structured JSON and logs dispatch with PDF attachment"""
        self.client.get('/login?demo=A/4-C', follow_redirects=True)
        
        my_receipt = query_db("SELECT receipt_no FROM tbl_receipts WHERE flat_no = 'A/4-C' LIMIT 1", one=True)
        self.assertIsNotNone(my_receipt)
        
        resp = self.client.post(
            f'/receipts/{my_receipt["receipt_no"]}/email',
            headers={'X-Requested-With': 'XMLHttpRequest'}
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data['success'])
        self.assertIn('emailed', data['message'].lower())
        self.assertTrue(data.get('attachment', '').endswith('.pdf'), f"Expected PDF attachment, got: {data.get('attachment')}")

    def test_08_pdf_receipt_download(self):
        """Resident can directly view/download own official PDF receipt with application/pdf Content-Type"""
        self.client.get('/login?demo=A/4-C', follow_redirects=True)
        
        my_receipt = query_db("SELECT receipt_no FROM tbl_receipts WHERE flat_no = 'A/4-C' LIMIT 1", one=True)
        self.assertIsNotNone(my_receipt)
        
        # Test inline viewing
        resp = self.client.get(f'/receipts/{my_receipt["receipt_no"]}/pdf')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content_type, 'application/pdf')
        self.assertTrue(resp.data.startswith(b'%PDF-'), "Response data is not a valid PDF file")
        self.assertIn('filename=', resp.headers.get('Content-Disposition', ''))
        
        # Test direct attachment download
        resp_dl = self.client.get(f'/receipts/{my_receipt["receipt_no"]}/pdf?download=1')
        self.assertEqual(resp_dl.status_code, 200)
        self.assertEqual(resp_dl.content_type, 'application/pdf')
        self.assertIn('attachment', resp_dl.headers.get('Content-Disposition', ''))

    def test_09_resident_cannot_download_others_pdf(self):
        """Resident cannot download another flat's PDF receipt"""
        other_receipt = query_db("SELECT receipt_no FROM tbl_receipts WHERE flat_no = 'A/1-A' LIMIT 1", one=True)
        self.assertIsNotNone(other_receipt)
        
        self.client.get('/login?demo=A/4-C', follow_redirects=True)
        
        resp = self.client.get(f'/receipts/{other_receipt["receipt_no"]}/pdf', follow_redirects=True)
        self.assertIn(b'Access Denied', resp.data)

    def test_10_member_email_update_persistence_and_dispatch(self):
        """Updating email in member profile persists to tbl_mbr_cntct and routes receipt dispatch to new email"""
        # 1. Login as resident of A/4-C
        self.client.get('/login?demo=A/4-C', follow_redirects=True)
        
        test_new_email = "test.updated.sddra@example.com"
        test_new_phone = "+91 98765 43210"
        
        # 2. Update contact details via /profile
        resp = self.client.post('/profile', data={
            'action': 'update_info',
            'email': test_new_email,
            'phone': test_new_phone
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'updated successfully', resp.data)
        
        # 3. Verify in database table tbl_mbr_cntct
        cntct = query_db("SELECT * FROM tbl_mbr_cntct WHERE flat_no = 'A/4-C'", one=True)
        self.assertIsNotNone(cntct)
        self.assertEqual(cntct['email_1'], test_new_email)
        self.assertEqual(cntct['mobile_num_1'], test_new_phone)
        
        # 4. Verify receipt dispatch automatically sends to newly updated email
        my_receipt = query_db("SELECT receipt_no FROM tbl_receipts WHERE flat_no = 'A/4-C' LIMIT 1", one=True)
        self.assertIsNotNone(my_receipt)
        
        disp_resp = self.client.post(
            f'/receipts/{my_receipt["receipt_no"]}/email',
            headers={'X-Requested-With': 'XMLHttpRequest'}
        )
        self.assertEqual(disp_resp.status_code, 200)
        disp_data = disp_resp.get_json()
        self.assertTrue(disp_data['success'])
        self.assertIn(test_new_email, disp_data['message'])
        
        # Cleanup: restore original contact info
        execute_db("UPDATE tbl_mbr_cntct SET email_1 = 'hiswapnadeep@gmail.com', mobile_num_1 = '987-480-2000' WHERE flat_no = 'A/4-C'")

    def test_11_member_password_update_and_relogin(self):
        """Updating password in member profile persists to database and allows login with new password"""
        # Ensure flat A/4-C has standard default password before test
        from database import hash_password
        default_h = hash_password('sdera@123')
        execute_db("UPDATE tbl_membership SET password_hash = %s WHERE flat_no = 'A/1-B'", (default_h,))

        # 1. Login with current default password
        resp_login = self.client.post('/login', data={'username': 'A/1-B', 'password': 'sdera@123'}, follow_redirects=True)
        self.assertEqual(resp_login.status_code, 200)
        self.assertIn(b'Kripa Ghosal', resp_login.data)
        
        # 2. Update password in profile
        new_pwd = "newpassword2026"
        resp_change = self.client.post('/profile', data={
            'action': 'change_password',
            'current_password': 'sdera@123',
            'new_password': new_pwd,
            'confirm_password': new_pwd
        }, follow_redirects=True)
        self.assertEqual(resp_change.status_code, 200)
        self.assertIn(b'updated successfully', resp_change.data)
        
        # 3. Logout
        self.client.get('/logout', follow_redirects=True)
        
        # 4. Attempt login with old password -> should fail
        resp_fail = self.client.post('/login', data={'username': 'A/1-B', 'password': 'sdera@123'}, follow_redirects=True)
        self.assertIn(b'Invalid credentials', resp_fail.data)
        
        # 5. Attempt login with new password -> should succeed
        resp_success = self.client.post('/login', data={'username': 'A/1-B', 'password': new_pwd}, follow_redirects=True)
        self.assertEqual(resp_success.status_code, 200)
        self.assertIn(b'Welcome', resp_success.data)
        
        # Cleanup: restore default password
        execute_db("UPDATE tbl_membership SET password_hash = %s WHERE flat_no = 'A/1-B'", (default_h,))
        execute_db("UPDATE tbl_admins SET password_hash = %s WHERE username = 'treasurer'", (default_h,))

    def test_12_tariff_dashboard_rbac_restrictions(self):
        """Verify that /admin/billing-rates is accessible to executive admins (treasurer, admin) and restricted from ordinary residents."""
        # 1. Anonymous access -> redirect to login
        self.client.get('/logout', follow_redirects=True)
        resp_anon = self.client.get('/admin/billing-rates', follow_redirects=True)
        self.assertIn(b'Please log in', resp_anon.data)

        # 2. General resident access (A/1-A) -> Access denied
        self.client.get('/logout', follow_redirects=True)
        self.client.post('/login', data={'username': 'A/1-A', 'password': 'sdera@123'}, follow_redirects=True)
        resp_res = self.client.get('/admin/billing-rates', follow_redirects=True)
        self.assertIn(b'Access Denied', resp_res.data)

        # 3. Committee Treasurer (treasurer) -> Access granted
        self.client.get('/logout', follow_redirects=True)
        self.client.post('/login', data={'username': 'treasurer', 'password': 'sdera@123'}, follow_redirects=True)
        resp_tres = self.client.get('/admin/billing-rates', follow_redirects=True)
        self.assertEqual(resp_tres.status_code, 200)
        self.assertIn(b'Maintenance Tariff &amp; Billing Rates Console', resp_tres.data)

        # 4. Billing Administrator (admin) -> Access granted
        self.client.get('/logout', follow_redirects=True)
        self.client.post('/login', data={'username': 'admin', 'password': 'passwd'}, follow_redirects=True)
        resp_admin = self.client.get('/admin/billing-rates', follow_redirects=True)
        self.assertEqual(resp_admin.status_code, 200)
        self.assertIn(b'Maintenance Tariff &amp; Billing Rates Console', resp_admin.data)
        self.assertIn(b'Official Society Maintenance Formula', resp_admin.data)

    def test_13_global_tariff_rate_update(self):
        """Verify applying global tariff rates recalculates and persists maintenance charges across all units."""
        self.client.get('/logout', follow_redirects=True)
        self.client.post('/login', data={'username': 'admin', 'password': 'passwd'}, follow_redirects=True)

        # Apply new temporary rate scale
        resp = self.client.post('/admin/billing-rates', data={
            'action': 'apply_global_rates',
            'flat_charges': '1.60',
            'capital_fund': '0.25',
            'common_expenses': '180.0',
            'cps_charges': '175.0',
            'tws_charges': '160.0'
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Tariff Rate Scale applied', resp.data)

        # Check Flat A/1-A (960 sq.ft., cps_owner=1, tws_owner=0)
        # Expected: Round10((960 * 1.60) + (960 * 0.25) + 180 + 175 + 0)
        # = Round10(1536 + 240 + 180 + 175) = Round10(2131) = 2130
        member_a1a = query_db("SELECT * FROM tbl_membership WHERE flat_no = 'A/1-A'", one=True)
        self.assertAlmostEqual(float(member_a1a['flat_charges']), 1.60, places=2)
        self.assertAlmostEqual(float(member_a1a['capital_fund']), 0.25, places=2)
        self.assertAlmostEqual(float(member_a1a['common_expenses']), 180.0, places=2)
        self.assertAlmostEqual(float(member_a1a['cps_charges']), 175.0, places=2)
        self.assertEqual(int(member_a1a['monthly_charge']), 2130)

        # Restore default rates
        self.client.post('/admin/billing-rates', data={
            'action': 'apply_global_rates',
            'flat_charges': '1.55',
            'capital_fund': '0.21',
            'common_expenses': '170.0',
            'cps_charges': '160.0',
            'tws_charges': '150.0'
        }, follow_redirects=True)
        
        member_restored = query_db("SELECT * FROM tbl_membership WHERE flat_no = 'A/1-A'", one=True)
        self.assertEqual(int(member_restored['monthly_charge']), 2020)

    def test_14_individual_unit_tariff_update(self):
        """Verify fine-tuning individual unit tariff parameters via POST /admin/billing-rates/unit/<id>."""
        self.client.get('/logout', follow_redirects=True)
        self.client.post('/login', data={'username': 'admin', 'password': 'passwd'}, follow_redirects=True)
        
        member = query_db("SELECT * FROM tbl_membership WHERE flat_no = 'A/4-C'", one=True)
        orig_sq_ft = member['RvsdFlatSize']
        orig_cps_owner = member['cps_owner']
        orig_tws_count = member['tws_count']

        # Update Unit Tariff for A/4-C
        resp = self.client.post(f"/admin/billing-rates/unit/{member['id']}", data={
            'sq_feet': str(orig_sq_ft),
            'flat_charges': '1.55',
            'capital_fund': '0.21',
            'common_expenses': '170.0',
            'cps_owner': '1',
            'car_parking_space': '120',
            'cps_charges': '160.0',
            'tws_owner': '1',
            'tws_count': '2',
            'tws_charges': '300.0'
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Unit tariff updated successfully', resp.data)

        # A/4-C: 925 sq.ft., flat_chg=1.55, cap_fund=0.21, comm=170, cps=160, tws=300
        # Expected: Round10((925*1.55) + (925*0.21) + 170 + 160 + 300) = Round10(1433.75 + 194.25 + 170 + 160 + 300) = Round10(2258) = 2260
        updated_member = query_db("SELECT * FROM tbl_membership WHERE flat_no = 'A/4-C'", one=True)
        self.assertEqual(int(updated_member['monthly_charge']), 2260)

        # Restore original A/4-C parameters (1 TWS, 150 tws_charges -> 2110)
        self.client.post(f"/admin/billing-rates/unit/{member['id']}", data={
            'sq_feet': str(orig_sq_ft),
            'flat_charges': '1.55',
            'capital_fund': '0.21',
            'common_expenses': '170.0',
            'cps_owner': str(orig_cps_owner),
            'car_parking_space': '120',
            'cps_charges': '160.0',
            'tws_owner': '1',
            'tws_count': str(orig_tws_count),
            'tws_charges': '150.0'
        }, follow_redirects=True)
        restored = query_db("SELECT * FROM tbl_membership WHERE flat_no = 'A/4-C'", one=True)
        self.assertEqual(int(restored['monthly_charge']), 2110)

if __name__ == '__main__':
    unittest.main()

