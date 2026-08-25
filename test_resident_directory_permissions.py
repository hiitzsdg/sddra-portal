import unittest
from app import app
from database import query_db

class TestResidentDirectoryPermissions(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()

    def test_resident_member_view_access_and_privacy_controls(self):
        """Verify normal resident members have read-only view access with financial and action controls hidden."""
        # 1. Log in as regular resident member (Flat A/4-C)
        self.client.get('/logout', follow_redirects=True)
        login_resp = self.client.post('/login', data={'username': 'A/4-C', 'password': 'sdera@123'}, follow_redirects=True)
        self.assertEqual(login_resp.status_code, 200)

        # 2. Access resident directory
        resp = self.client.get('/admin/members')
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode('utf-8')

        # Check that directory data IS rendered
        self.assertIn('Resident Directory &amp; Flat Roster', html)
        self.assertIn('Flat A/4-C', html)
        self.assertIn('Flat B/1-B', html)
        self.assertIn('Swapnadeep Ganguly', html)
        self.assertIn('Khokhon Routh', html)

        # Check that Financial Totals and Receipts are HIDDEN for members
        self.assertNotIn('<th>Total Paid</th>', html)
        self.assertNotIn('<th>Receipts (Click to View)</th>', html)
        self.assertNotIn('btn-view-member-receipts', html)
        self.assertNotIn('memberReceiptsModal', html)

        # Check that Edit and Reset Password options are HIDDEN for members
        self.assertNotIn('btn-edit-member', html)
        self.assertNotIn('btn-edit-contact', html)
        self.assertNotIn('btn-reset-pwd', html)
        self.assertNotIn('editContactModal', html)

        # Check that Direct WhatsApp Chat button is HIDDEN for members
        self.assertNotIn('btn-whatsapp', html)
        self.assertNotIn('Chat with', html)

        # 3. Direct unauthorized POST attempt to update resident contact info by member must fail
        post_resp = self.client.post('/admin/members/update', data={
            'flat_no': 'A/1-A',
            'member_name': 'Hacker Name',
            'email': 'hacker@example.com'
        }, follow_redirects=True)
        # Should redirect to dashboard / denied and member name unchanged
        m = query_db("SELECT member_name FROM tbl_membership WHERE flat_no = 'A/1-A'", one=True)
        self.assertNotEqual(m['member_name'], 'Hacker Name')
        print("Resident member directory read-only access and privacy restrictions verified successfully.")

    def test_admin_full_management_access(self):
        """Verify administrators retain full management features on resident directory."""
        # 1. Log in as Admin (Treasurer)
        self.client.get('/logout', follow_redirects=True)
        login_resp = self.client.post('/login', data={'username': 'treasurer', 'password': 'sdera@123'}, follow_redirects=True)
        self.assertEqual(login_resp.status_code, 200)

        # 2. Access resident directory
        resp = self.client.get('/admin/members')
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode('utf-8')

        # Check that admin sees Total Paid and Receipts
        self.assertIn('<th>Total Paid</th>', html)
        self.assertIn('<th>Receipts (Click to View)</th>', html)
        self.assertIn('memberReceiptsModal', html)

        # Check that admin sees Edit, Reset Password, and WhatsApp buttons
        self.assertIn('btn-edit-member', html)
        self.assertIn('btn-reset-pwd', html)
        self.assertIn('btn-whatsapp', html)
        self.assertIn('editContactModal', html)

        print("Admin full management features verified successfully.")

if __name__ == '__main__':
    unittest.main()
