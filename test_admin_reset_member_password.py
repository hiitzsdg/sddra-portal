import unittest
from app import app
from database import query_db, execute_db, hash_password, verify_password

class TestAdminResetMemberPassword(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()

    def test_01_access_control_unauthenticated_and_resident(self):
        # 1. Unauthenticated request to reset password endpoint
        resp = self.client.post('/admin/members/reset-password', data={'flat_no': 'A/1-B'})
        self.assertIn(resp.status_code, [302, 401, 403])

        # 2. Resident login attempting to access reset password endpoint
        self.client.post('/login', data={'username': 'A/1-B', 'password': 'sdera@123'}, follow_redirects=True)
        resp_res = self.client.post('/admin/members/reset-password', data={'flat_no': 'A/1-B'}, follow_redirects=True)
        self.assertIn(b'Access Denied', resp_res.data)

    def test_02_admin_reset_to_default_password(self):
        # Login as Admin
        self.client.post('/login', data={'username': 'admin', 'password': 'passwd'}, follow_redirects=True)

        # Set a temporary different password first for B/1-B
        temp_hash = hash_password('TemporaryOldPwd#999')
        execute_db("UPDATE tbl_membership SET password_hash = %s WHERE flat_no = 'B/1-B'", (temp_hash,))

        # Test AJAX POST to reset to default
        resp = self.client.post(
            '/admin/members/reset-password',
            data={'flat_no': 'B/1-B', 'reset_mode': 'default'},
            headers={'X-Requested-With': 'XMLHttpRequest'}
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['flat_no'], 'B/1-B')
        self.assertEqual(data['new_password'], 'sdera@123')
        self.assertIn('sdera@123', data['message'])
        self.assertIn('wa.me', data['whatsapp_url'])

        # Verify password in DB
        member = query_db("SELECT password_hash FROM tbl_membership WHERE flat_no = 'B/1-B'", one=True)
        self.assertTrue(verify_password('sdera@123', member['password_hash']))

        # Test Resident can log in with new password
        self.client.get('/logout', follow_redirects=True)
        resp_login = self.client.post('/login', data={'username': 'B/1-B', 'password': 'sdera@123'}, follow_redirects=True)
        self.assertEqual(resp_login.status_code, 200)
        self.assertIn(b'B/1-B', resp_login.data)
        self.assertIn(b'Dashboard', resp_login.data)

    def test_03_admin_reset_to_custom_password(self):
        # Login as Admin
        self.client.post('/login', data={'username': 'admin', 'password': 'passwd'}, follow_redirects=True)

        custom_pwd = 'ResidentSecret#2026'
        resp = self.client.post(
            '/admin/members/reset-password',
            data={'flat_no': 'A/3-A', 'reset_mode': 'custom', 'custom_password': custom_pwd},
            headers={'X-Requested-With': 'XMLHttpRequest'}
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['new_password'], custom_pwd)

        # Verify DB
        member = query_db("SELECT password_hash FROM tbl_membership WHERE flat_no = 'A/3-A'", one=True)
        self.assertTrue(verify_password(custom_pwd, member['password_hash']))

        # Test Resident Login with custom password
        self.client.get('/logout', follow_redirects=True)
        resp_login = self.client.post('/login', data={'username': 'A/3-A', 'password': custom_pwd}, follow_redirects=True)
        self.assertEqual(resp_login.status_code, 200)
        self.assertIn(b'A/3-A', resp_login.data)

        # Reset back to default for test hygiene
        execute_db("UPDATE tbl_membership SET password_hash = %s WHERE flat_no = 'A/3-A'", (hash_password('sdera@123'),))

    def test_04_activity_log_and_ui_markup(self):
        # Login as Admin
        self.client.post('/login', data={'username': 'admin', 'password': 'passwd'}, follow_redirects=True)

        # Verify activity log
        log_entry = query_db("SELECT * FROM tbl_activity_logs WHERE action_type = 'PASSWORD_RESET' ORDER BY id DESC LIMIT 1", one=True)
        self.assertIsNotNone(log_entry)
        self.assertIn('PASSWORD_RESET', log_entry['action_type'])

        # Verify Admin Members page contains reset password elements
        resp_members = self.client.get('/admin/members')
        self.assertEqual(resp_members.status_code, 200)
        self.assertIn(b'btn-reset-pwd', resp_members.data)
        self.assertIn(b'adminResetPasswordModal', resp_members.data)
        self.assertIn(b'Reset Portal Password', resp_members.data)

if __name__ == '__main__':
    unittest.main()
