import unittest
import json
import re
from app import app
from database import query_db

class TestLoginDropdown(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()

    def test_login_page_renders_dropdowns_and_blocks(self):
        resp = self.client.get('/login')
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode('utf-8')

        # Check for block dropdown and flat dropdown elements
        self.assertIn('id="blockSelect"', html)
        self.assertIn('id="flatSelect"', html)
        self.assertIn('id="residentInfoCard"', html)
        self.assertIn('tabDropdownMode', html)
        self.assertIn('tabManualMode', html)
        
        # Check that Block options are rendered
        self.assertIn('Block A', html)
        self.assertIn('Block B', html)
        self.assertIn('Block C', html)

        # Check that JSON payload containing blocks and units is present
        self.assertIn('const societyBlocks =', html)
        match = re.search(r'const societyBlocks\s*=\s*(\{.*?\});', html, re.DOTALL)
        self.assertTrue(match, "societyBlocks JSON not found in page script")
        blocks_data = json.loads(match.group(1))
        
        self.assertIn('A', blocks_data)
        self.assertIn('B', blocks_data)
        self.assertIn('C', blocks_data)
        
        # Verify Block A units
        block_a_flats = [u['flat_no'] for u in blocks_data['A']]
        self.assertIn('A/4-C', block_a_flats)
        self.assertIn('A/1-A', block_a_flats)
        self.assertIn('A/Gr-B', block_a_flats)
        
        # Verify Block B units
        block_b_flats = [u['flat_no'] for u in blocks_data['B']]
        self.assertIn('B/1-B', block_b_flats)
        self.assertIn('B/Gr', block_b_flats)
        
        # Verify Block C units
        block_c_flats = [u['flat_no'] for u in blocks_data['C']]
        self.assertIn('C/1-A', block_c_flats)
        self.assertIn('C/4-C', block_c_flats)
        self.assertIn('C/Gr', block_c_flats)
        
        print("Login page dropdown rendering verified successfully.")

    def test_login_authentications(self):
        # Resident login for Block A
        resp = self.client.post('/login', data={'username': 'A/4-C', 'password': 'sdera@123'}, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Swapnadeep Ganguly', resp.data)

        # Resident login for Block B
        resp2 = self.client.post('/login', data={'username': 'B/1-B', 'password': 'sdera@123'}, follow_redirects=True)
        self.assertEqual(resp2.status_code, 200)

        # Resident login for Block C
        resp3 = self.client.post('/login', data={'username': 'C/1-A', 'password': 'sdera@123'}, follow_redirects=True)
        self.assertEqual(resp3.status_code, 200)

        # Admin login
        resp_admin = self.client.post('/login', data={'username': 'treasurer', 'password': 'sdera@123'}, follow_redirects=True)
        self.assertEqual(resp_admin.status_code, 200)

        print("All dropdown and admin authentication tests passed.")

if __name__ == '__main__':
    unittest.main()
