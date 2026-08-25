import unittest
from app import app
from database import query_db, execute_db

class AdminEditResidentTest(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()

    def _login_as_admin(self):
        return self.client.post('/login', data={'username': 'admin', 'password': 'passwd'}, follow_redirects=True)

    def test_01_admin_members_page_contains_edit_resident_features(self):
        """Check that admin members roster contains inline edit resident buttons and modal fields."""
        login_resp = self._login_as_admin()
        self.assertEqual(login_resp.status_code, 200)

        resp = self.client.get('/admin/members')
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode('utf-8')
        self.assertIn('btn-edit-member', html)
        self.assertIn('edit_contact_name', html)
        self.assertIn('sync_receipts', html)
        self.assertIn('Edit Resident Details', html)

    def test_02_admin_can_update_resident_name_and_sync_receipts(self):
        """Admin can post updated resident name and sync to tbl_receipts."""
        self._login_as_admin()
        
        # Get current details for flat A/1-A
        orig = query_db("SELECT member_name FROM tbl_membership WHERE flat_no = 'A/1-A'", one=True)
        orig_name = orig['member_name']

        try:
            test_new_name = "Mr. Biswajit Manna / Mrs. Ananya Manna"
            resp = self.client.post('/admin/members/update', data={
                'flat_no': 'A/1-A',
                'member_name': test_new_name,
                'email': 'biswajit.test@example.com',
                'phone': '9830000000',
                'sync_receipts': '1'
            }, follow_redirects=True)
            self.assertEqual(resp.status_code, 200)

            # Verify in tbl_membership
            updated_m = query_db("SELECT member_name FROM tbl_membership WHERE flat_no = 'A/1-A'", one=True)
            self.assertEqual(updated_m['member_name'], test_new_name)

            # Verify in tbl_receipts
            receipts = query_db("SELECT member_name FROM tbl_receipts WHERE flat_no = 'A/1-A'")
            self.assertTrue(len(receipts) > 0)
            for r in receipts:
                self.assertEqual(r['member_name'], test_new_name)

        finally:
            # Restore original
            execute_db("UPDATE tbl_membership SET member_name = %s WHERE flat_no = 'A/1-A'", (orig_name,))
            execute_db("UPDATE tbl_receipts SET member_name = %s WHERE flat_no = 'A/1-A'", (orig_name,))

if __name__ == '__main__':
    unittest.main()
