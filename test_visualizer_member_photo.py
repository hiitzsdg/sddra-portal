import unittest
from app import app
from database import query_db, execute_db

class TestVisualizerMemberPhoto(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()

    def test_member_photo_reflected_in_admin_visualizer(self):
        """Verify that when a member updates their photo, it is displayed in the Society Wing & Floor Visualizer on the admin dashboard."""
        # 1. Login as Member (Flat A/4-C)
        login_resp = self.client.post('/login', data={
            'username': 'A/4-C',
            'password': 'sdera@123'
        }, follow_redirects=True)
        self.assertEqual(login_resp.status_code, 200)

        sample_pic = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

        # 2. Member updates profile picture on /profile
        update_resp = self.client.post('/profile', data={
            'action': 'update_profile_pic',
            'profile_pic': sample_pic
        }, follow_redirects=True)
        self.assertEqual(update_resp.status_code, 200)
        self.assertIn(b'Profile picture updated successfully', update_resp.data)

        # 3. Verify in database
        db_member = query_db("SELECT profile_pic FROM tbl_membership WHERE flat_no = 'A/4-C'", one=True)
        self.assertIsNotNone(db_member)
        self.assertEqual(db_member['profile_pic'], sample_pic)

        # 4. Member logs out and Admin logs in (treasurer)
        self.client.get('/logout', follow_redirects=True)
        admin_login = self.client.post('/login', data={
            'username': 'treasurer',
            'password': 'sdera@123'
        }, follow_redirects=True)
        self.assertEqual(admin_login.status_code, 200)

        # 5. Admin visits /dashboard (where Society Wing & Floor Visualizer is rendered)
        dash_resp = self.client.get('/dashboard')
        self.assertEqual(dash_resp.status_code, 200)

        dash_html = dash_resp.data.decode('utf-8')
        
        # Verify Visualizer Header
        self.assertIn('Society Wing &amp; Floor Visualizer', dash_html)
        
        # Verify Flat A/4-C unit button has data-photo set with the updated photo
        self.assertIn('data-flat="A/4-C"', dash_html)
        self.assertIn(sample_pic, dash_html)
        
        # Verify unit-avatar-thumb image is rendered for Flat A/4-C
        self.assertIn('class="unit-avatar-thumb"', dash_html)
        
        # Verify visualizer modal has avatar elements
        self.assertIn('id="visModalAvatarImg"', dash_html)
        self.assertIn('id="visModalAvatarFallback"', dash_html)

        # 6. Admin checks Resident Directory (/admin/members)
        members_resp = self.client.get('/admin/members')
        self.assertEqual(members_resp.status_code, 200)
        members_html = members_resp.data.decode('utf-8')
        self.assertIn(sample_pic, members_html)

        # 7. Member removes photo and verify fallback in admin visualizer
        self.client.get('/logout', follow_redirects=True)
        self.client.post('/login', data={
            'username': 'A/4-C',
            'password': 'sdera@123'
        }, follow_redirects=True)
        
        remove_resp = self.client.post('/profile', data={
            'action': 'update_profile_pic',
            'profile_pic': ''
        }, follow_redirects=True)
        self.assertEqual(remove_resp.status_code, 200)

        # Admin logs back in and checks dashboard
        self.client.get('/logout', follow_redirects=True)
        self.client.post('/login', data={
            'username': 'treasurer',
            'password': 'sdera@123'
        }, follow_redirects=True)

        dash_resp_after = self.client.get('/dashboard')
        dash_html_after = dash_resp_after.data.decode('utf-8')
        
        # Flat A/4-C should now have empty data-photo or fallback placeholder
        self.assertIn('data-flat="A/4-C"', dash_html_after)
        self.assertNotIn(sample_pic, dash_html_after)

if __name__ == '__main__':
    unittest.main()
