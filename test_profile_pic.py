import unittest
from app import app
from database import query_db, execute_db

class TestProfilePicture(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        self.client.get('/logout', follow_redirects=True)
        from database import SDERA_HASH
        execute_db("UPDATE tbl_membership SET password_hash = %s WHERE flat_no = 'A/4-C'", (SDERA_HASH,))
        execute_db("UPDATE tbl_admins SET password_hash = %s WHERE username = 'treasurer'", (SDERA_HASH,))

    def test_member_profile_pic_flow(self):
        # 1. Login as Flat A/4-C
        resp = self.client.post('/login', data={
            'username': 'A/4-C',
            'password': 'sdera@123'
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)

        # Sample test image base64
        sample_img = "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////wgALCAABAAEBAREA/8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABPxA="

        # 2. Update profile picture
        resp2 = self.client.post('/profile', data={
            'action': 'update_profile_pic',
            'profile_pic': sample_img
        }, follow_redirects=True)
        self.assertEqual(resp2.status_code, 200)
        self.assertIn(b'Profile picture updated successfully', resp2.data)

        # 3. Verify in database
        row = query_db("SELECT profile_pic FROM tbl_membership WHERE flat_no = 'A/4-C'", one=True)
        self.assertIsNotNone(row)
        self.assertEqual(row['profile_pic'], sample_img)

        # 4. Verify profile page displays the custom picture
        resp3 = self.client.get('/profile')
        self.assertEqual(resp3.status_code, 200)
        self.assertIn(b'data:image/jpeg;base64', resp3.data)
        self.assertIn(b'Remove', resp3.data)

        # 5. Remove profile picture
        resp4 = self.client.post('/profile', data={
            'action': 'update_profile_pic',
            'profile_pic': ''
        }, follow_redirects=True)
        self.assertEqual(resp4.status_code, 200)
        self.assertIn(b'Profile picture removed', resp4.data)

        # 6. Verify in database removal
        row_after = query_db("SELECT profile_pic FROM tbl_membership WHERE flat_no = 'A/4-C'", one=True)
        self.assertTrue(row_after['profile_pic'] is None or row_after['profile_pic'] == '')

    def test_admin_profile_pic_flow(self):
        # 1. Login as Admin
        resp = self.client.post('/login', data={
            'username': 'admin',
            'password': 'passwd'
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)

        sample_img = "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////wgALCAABAAEBAREA/8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABPxA="

        # 2. Update admin profile picture
        resp2 = self.client.post('/profile', data={
            'action': 'update_profile_pic',
            'profile_pic': sample_img
        }, follow_redirects=True)
        self.assertEqual(resp2.status_code, 200)
        self.assertIn(b'Profile picture updated successfully', resp2.data)

        # 3. Verify in database
        row = query_db("SELECT profile_pic FROM tbl_admins WHERE username = 'admin'", one=True)
        self.assertIsNotNone(row)
        self.assertEqual(row['profile_pic'], sample_img)

        # 4. Remove admin profile picture
        resp3 = self.client.post('/profile', data={
            'action': 'update_profile_pic',
            'profile_pic': ''
        }, follow_redirects=True)
        self.assertEqual(resp3.status_code, 200)
        self.assertIn(b'Profile picture removed', resp3.data)

if __name__ == '__main__':
    unittest.main()
