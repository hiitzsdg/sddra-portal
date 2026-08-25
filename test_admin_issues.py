import unittest
from app import app
from database import query_db, execute_db

class TestAdminIssues(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()

    def test_01_admin_access_and_nav_link(self):
        # 1. Login as Admin
        resp = self.client.post('/login', data={'username': 'admin', 'password': 'passwd'}, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)

        # 2. Check Admin Issues Page
        resp_issues = self.client.get('/admin/issues')
        self.assertEqual(resp_issues.status_code, 200)
        self.assertIn(b'Resident Grievances', resp_issues.data)
        self.assertIn(b'Log Maintenance Issue', resp_issues.data)
        self.assertIn(b'Raised Issues', resp_issues.data)

        # 3. Check Navbar has Raised Issues link
        self.assertIn(b'/admin/issues', resp_issues.data)

    def test_02_resident_blocked_from_admin_issues(self):
        # Login as regular non-officer resident
        resp = self.client.post('/login', data={'username': 'A/1-B', 'password': 'sdera@123'}, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)

        # Attempt to access /admin/issues
        resp_issues = self.client.get('/admin/issues', follow_redirects=True)
        self.assertEqual(resp_issues.status_code, 200)
        self.assertIn(b'Access Denied', resp_issues.data)

    def test_02b_dedicated_officer_login_has_admin_access(self):
        # Login as dedicated Treasurer username
        resp = self.client.post('/login', data={'username': 'treasurer', 'password': 'sdera@123'}, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)

        # Access /admin/issues should succeed for Treasurer admin login
        resp_issues = self.client.get('/admin/issues')
        self.assertEqual(resp_issues.status_code, 200)
        self.assertIn(b'Resident Grievances', resp_issues.data)

    def test_03_resident_can_create_ticket_api(self):
        # Login as resident
        self.client.post('/login', data={'username': 'A/1-B', 'password': 'sdera@123'}, follow_redirects=True)

        resp = self.client.post('/api/helpdesk/create', json={
            'category': 'Plumbing',
            'description': 'Main kitchen tap valve washer leaking water continuously.',
            'priority': 'Urgent'
        })
        self.assertEqual(resp.status_code, 200)
        json_data = resp.get_json()
        self.assertTrue(json_data['success'])
        tkt_no = json_data['ticket_number']

        # Verify in database
        row = query_db("SELECT * FROM tbl_helpdesk_tickets WHERE ticket_number = %s", (tkt_no,), one=True)
        self.assertIsNotNone(row)
        self.assertEqual(row['flat_no'], 'A/1-B')
        self.assertEqual(row['category'], 'Plumbing')
        self.assertEqual(row['status'], 'OPEN')

        # Check that it appears on Resident Dashboard
        resp_dash = self.client.get('/dashboard')
        self.assertEqual(resp_dash.status_code, 200)
        self.assertIn(tkt_no.encode(), resp_dash.data)

    def test_04_admin_can_update_status_and_assign(self):
        # Login as admin
        self.client.post('/login', data={'username': 'admin', 'password': 'passwd'}, follow_redirects=True)

        # Get existing ticket
        tkt = query_db("SELECT * FROM tbl_helpdesk_tickets LIMIT 1", one=True)
        self.assertIsNotNone(tkt)
        tkt_id = tkt['id']

        resp = self.client.post('/admin/issues', data={
            'action': 'update_status',
            'ticket_id': tkt_id,
            'status': 'RESOLVED',
            'assigned_to': 'Caretaker Mr. Sanjoy Chakraborty',
            'admin_notes': 'Work completed and verified with resident.'
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'status updated to RESOLVED', resp.data)

        # Verify in database
        updated_tkt = query_db("SELECT * FROM tbl_helpdesk_tickets WHERE id = %s", (tkt_id,), one=True)
        self.assertEqual(updated_tkt['status'], 'RESOLVED')
        self.assertEqual(updated_tkt['admin_notes'], 'Work completed and verified with resident.')

    def test_05_admin_can_log_and_delete_ticket(self):
        # Login as admin
        self.client.post('/login', data={'username': 'admin', 'password': 'passwd'}, follow_redirects=True)

        # Create ticket
        resp = self.client.post('/admin/issues', data={
            'action': 'create_ticket',
            'flat_no': 'B/1-A',
            'resident_name': 'Dr. Guru Prasad Mandal',
            'category': 'Electrical',
            'title': 'Staircase Light Bulb Replacement',
            'description': '2nd floor staircase tube light burnt out.',
            'priority': 'Normal',
            'assigned_to': 'Electrician'
        }, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'logged successfully', resp.data)

        # Find created ticket
        created = query_db("SELECT * FROM tbl_helpdesk_tickets WHERE flat_no = 'B/1-A' AND title = 'Staircase Light Bulb Replacement'", one=True)
        self.assertIsNotNone(created)
        tkt_id = created['id']

        # Delete ticket
        resp_del = self.client.post('/admin/issues', data={
            'action': 'delete_ticket',
            'ticket_id': tkt_id
        }, follow_redirects=True)
        self.assertEqual(resp_del.status_code, 200)
        self.assertIn(b'deleted from register', resp_del.data)

        # Verify deletion
        deleted = query_db("SELECT * FROM tbl_helpdesk_tickets WHERE id = %s", (tkt_id,), one=True)
        self.assertIsNone(deleted)

if __name__ == '__main__':
    unittest.main()
