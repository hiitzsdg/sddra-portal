import sys
import unittest
from app import app
from database import init_db, query_db, execute_db

class TestDigitalNoticeBoard(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
        init_db()

    def test_01_notices_table_and_seed_data(self):
        """Verify tbl_notices table exists and is populated with seed notices."""
        notices = query_db("SELECT * FROM tbl_notices ORDER BY id ASC")
        self.assertIsNotNone(notices)
        self.assertGreaterEqual(len(notices), 5)
        
        # Verify seed notice categories and titles
        titles = [n['title'] for n in notices]
        self.assertTrue(any("Water Tank" in t for t in titles))
        self.assertTrue(any("AGM" in t for t in titles))
        self.assertTrue(any("Lift" in t for t in titles))
        print(f"[PASS] Test 1: {len(notices)} notices successfully initialized in database.")

    def test_02_member_view_notices(self):
        """Verify regular member can access Notice Board and filter categories."""
        with self.client.session_transaction() as sess:
            sess['user'] = {
                'id': 1,
                'username': 'A/1-A',
                'name': 'Sourav Ganguly',
                'flat_no': 'A/1-A',
                'role': 'MEMBER',
                'is_admin': False
            }
        
        # GET /notices
        res = self.client.get('/notices')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Digital Notice Board", res.data)
        self.assertIn(b"Water Tank", res.data)

        # GET /notices with category filter
        res_cat = self.client.get('/notices?category=WATER_SUPPLY')
        self.assertEqual(res_cat.status_code, 200)
        self.assertIn(b"Water", res_cat.data)

        # GET /dashboard should show Announcements widget
        res_dash = self.client.get('/dashboard')
        self.assertEqual(res_dash.status_code, 200)
        self.assertIn(b"Official Society Announcements", res_dash.data)
        print("[PASS] Test 2: Resident member can view notice board and announcements widget.")

    def test_03_admin_crud_notices(self):
        """Verify committee admin can create, pin, edit, broadcast, and delete notices."""
        with self.client.session_transaction() as sess:
            sess['user'] = {
                'id': 99,
                'username': 'secretary',
                'name': 'Debasish Roy',
                'flat_no': 'B-202',
                'role': 'secretary',
                'is_admin': True
            }
        
        # 1. Create a new notice
        res_create = self.client.post('/notices/create', data={
            'title': 'Automated Test Notice: Generator Maintenance',
            'content': 'Diesel generator trial run on Saturday 4 PM.',
            'category': 'MAINTENANCE',
            'priority': 'HIGH',
            'is_pinned': '1',
            'do_broadcast': '0'
        }, follow_redirects=True)
        self.assertEqual(res_create.status_code, 200)
        self.assertIn(b"Automated Test Notice", res_create.data)

        # Query newly created notice
        created = query_db("SELECT * FROM tbl_notices WHERE title LIKE %s", ('%Automated Test Notice%',), one=True)
        self.assertIsNotNone(created)
        notice_id = created['id']
        self.assertEqual(created['is_pinned'], 1)
        self.assertEqual(created['priority'], 'HIGH')

        # 2. Toggle pin
        res_pin = self.client.post(f'/notices/{notice_id}/toggle-pin', follow_redirects=True)
        self.assertEqual(res_pin.status_code, 200)
        unpinned = query_db("SELECT is_pinned FROM tbl_notices WHERE id = %s", (notice_id,), one=True)
        self.assertEqual(unpinned['is_pinned'], 0)

        # 3. Edit notice
        res_edit = self.client.post(f'/notices/{notice_id}/edit', data={
            'title': 'Automated Test Notice: Updated Generator Schedule',
            'content': 'Diesel generator trial run shifted to Sunday 11 AM.',
            'category': 'MAINTENANCE',
            'priority': 'URGENT',
            'status': 'ACTIVE',
            'is_pinned': '1'
        }, follow_redirects=True)
        self.assertEqual(res_edit.status_code, 200)
        updated = query_db("SELECT * FROM tbl_notices WHERE id = %s", (notice_id,), one=True)
        self.assertEqual(updated['title'], 'Automated Test Notice: Updated Generator Schedule')
        self.assertEqual(updated['priority'], 'URGENT')

        # 4. Broadcast email simulation
        res_bcast = self.client.post(f'/notices/{notice_id}/broadcast', follow_redirects=True)
        self.assertEqual(res_bcast.status_code, 200)

        # 5. Delete notice
        res_del = self.client.post(f'/notices/{notice_id}/delete', follow_redirects=True)
        self.assertEqual(res_del.status_code, 200)
        deleted = query_db("SELECT * FROM tbl_notices WHERE id = %s", (notice_id,), one=True)
        self.assertIsNone(deleted)
        print("[PASS] Test 3: Admin full CRUD, pin toggle, email broadcast, and delete verified.")

if __name__ == '__main__':
    unittest.main()
