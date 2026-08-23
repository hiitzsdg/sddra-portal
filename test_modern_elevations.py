import unittest
import json
from app import app
from database import init_db

class TestModernWebElevations(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        self.client = app.test_client()
        app.config['TESTING'] = True

    def test_01_command_palette_api(self):
        """Verify /api/command-palette-data returns indexed navigation, actions, residents, and notices."""
        # 1. Resident perspective
        self.client.get('/login?demo=A/4-C', follow_redirects=True)
        resp = self.client.get('/api/command-palette-data')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn('navigation', data)
        self.assertIn('actions', data)
        self.assertIn('residents', data)
        self.assertIn('notices', data)
        self.assertTrue(len(data['navigation']) >= 4)
        self.assertTrue(len(data['residents']) >= 40)
        
        # Verify UPI quick pay action present for resident
        actions_ids = [a['id'] for a in data['actions']]
        self.assertIn('act-pay', actions_ids)

        # 2. Admin perspective
        self.client.get('/logout', follow_redirects=True)
        self.client.post('/login', data={'username': 'treasurer', 'password': 'sdera@123'}, follow_redirects=True)
        admin_resp = self.client.get('/api/command-palette-data')
        self.assertEqual(admin_resp.status_code, 200)
        admin_data = admin_resp.get_json()
        admin_nav_ids = [n['id'] for n in admin_data['navigation']]
        self.assertIn('nav-members', admin_nav_ids)
        self.assertIn('nav-receipts', admin_nav_ids)
        self.assertIn('nav-penalties', admin_nav_ids)

    def test_02_admin_building_matrix_dashboard(self):
        """Verify admin dashboard renders the interactive 2D building matrix visualizer."""
        self.client.post('/login', data={'username': 'treasurer', 'password': 'sdera@123'}, follow_redirects=True)
        resp = self.client.get('/dashboard')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Society Wing &amp; Floor Visualizer', resp.data)
        self.assertIn(b'Block A', resp.data)
        self.assertIn(b'Block B', resp.data)
        self.assertIn(b'Block C', resp.data)
        self.assertIn(b'matrix-popover', resp.data)
        self.assertIn(b'unit-cell-btn', resp.data)
        self.assertIn(b'flatVisualizerModal', resp.data)
        self.assertIn(b'visModalLedgerLink', resp.data)
        self.assertIn(b'visModalReceiptsLink', resp.data)

    def test_03_resident_upi_and_helpdesk_dashboard(self):
        """Verify resident dashboard renders UPI hero card and helpdesk ticketing stepper."""
        self.client.get('/login?demo=A/4-C', follow_redirects=True)
        resp = self.client.get('/dashboard')
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Instant Maintenance Payment', resp.data)
        self.assertIn(b'sdera.maintenance@icici', resp.data)
        self.assertIn(b'upiQrCanvas', resp.data)
        self.assertIn(b'Society Helpdesk &amp; Maintenance Requests', resp.data)
        self.assertIn(b'status-stepper-container', resp.data)
        self.assertIn(b'helpdeskModal', resp.data)
        self.assertIn(b'upiPaymentModal', resp.data)

    def test_04_command_palette_markup_in_base(self):
        """Verify command palette trigger and modal markup are embedded in base.html."""
        self.client.get('/login?demo=A/4-C', follow_redirects=True)
        resp = self.client.get('/dashboard')
        self.assertIn(b'openCommandPaletteBtn', resp.data)
        self.assertIn(b'commandPaletteModal', resp.data)
        self.assertIn(b'commandPaletteInput', resp.data)
        self.assertIn(b'globalToastContainer', resp.data)

if __name__ == '__main__':
    unittest.main()
