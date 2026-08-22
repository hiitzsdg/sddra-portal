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
        """Regular resident cannot access admin directory or master receipts ledger"""
        self.client.get('/login?demo=A/4-C', follow_redirects=True)
        
        resp = self.client.get('/admin/members', follow_redirects=True)
        self.assertIn(b'Access Denied', resp.data)
        
        resp2 = self.client.get('/admin/receipts', follow_redirects=True)
        self.assertIn(b'Access Denied', resp2.data)

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
        self.assertIn(b'Resident Roster', resp_members.data)
        self.assertIn(b'Flat A/1-A', resp_members.data)
        self.assertIn(b'Flat A/4-C', resp_members.data)

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
        execute_db("UPDATE tbl_membership SET password_hash = %s WHERE flat_no = 'A/4-C'", (default_h,))

        # 1. Login with current default password
        resp_login = self.client.post('/login', data={'username': 'A/4-C', 'password': 'sdera@123'}, follow_redirects=True)
        self.assertEqual(resp_login.status_code, 200)
        self.assertIn(b'Swapnadeep Ganguly', resp_login.data)
        
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
        resp_fail = self.client.post('/login', data={'username': 'A/4-C', 'password': 'sdera@123'}, follow_redirects=True)
        self.assertIn(b'Invalid credentials', resp_fail.data)
        
        # 5. Attempt login with new password -> should succeed
        resp_success = self.client.post('/login', data={'username': 'A/4-C', 'password': new_pwd}, follow_redirects=True)
        self.assertEqual(resp_success.status_code, 200)
        self.assertIn(b'Welcome', resp_success.data)
        
        # Cleanup: restore default password
        execute_db("UPDATE tbl_membership SET password_hash = %s WHERE flat_no = 'A/4-C'", (default_h,))

if __name__ == '__main__':
    unittest.main()

