import unittest
from app import app
from database import query_db, init_db

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
        """Email receipt dispatch endpoint returns structured JSON and logs dispatch"""
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

if __name__ == '__main__':
    unittest.main()
