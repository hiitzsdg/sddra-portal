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
        self.assertIn(b"Notice Board", res.data)
        self.assertIn(b"SOUTH DUMDUM ENCLAVE", res.data)
        self.assertIn(b"Water Tank", res.data)

        # GET /notices/<id>/view standalone circular view
        notices = query_db("SELECT id FROM tbl_notices LIMIT 1")
        if notices:
            n_id = notices[0]['id']
            res_view = self.client.get(f'/notices/{n_id}/view')
            self.assertEqual(res_view.status_code, 200)
            self.assertIn(b"Regd. No. 08A", res_view.data)

        # GET /notices with category filter
        res_cat = self.client.get('/notices?category=WATER_SUPPLY')
        self.assertEqual(res_cat.status_code, 200)
        self.assertIn(b"Water", res_cat.data)

        # GET /dashboard should show Announcements widget
        res_dash = self.client.get('/dashboard')
        self.assertEqual(res_dash.status_code, 200)
        self.assertIn(b"Official Society Announcements", res_dash.data)
        print("[PASS] Test 2: Resident member can view notice board, letterhead circular, and announcements widget.")

    def test_03_admin_crud_notices(self):
        """Verify committee admin can create, pin, edit, broadcast, and delete notices."""
        with self.client.session_transaction() as sess:
            sess['user'] = {
                'id': 99,
                'username': 'secretary',
                'name': 'Somenath Halder',
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

    def test_04_calling_authority_selection(self):
        """Verify notice posting and editing with different calling authorities (Treasurer, President, Secretary, Caretaker, Custom)."""
        with self.client.session_transaction() as sess:
            sess['user'] = {
                'id': 99,
                'username': 'admin',
                'name': 'System Administrator',
                'role': 'super_admin',
                'is_admin': True
            }

        # 1. Post Notice as Treasurer (Mr. Swapnadeep Ganguly)
        res_treasurer = self.client.post('/notices/create', data={
            'title': 'FY 2026-27 Annual Budget Review Meeting',
            'content': 'All committee members are requested to attend the budget review meeting.',
            'category': 'FINANCIAL',
            'priority': 'HIGH',
            'caller_role': 'Treasurer',
            'is_pinned': '0',
            'do_broadcast': '0',
            'do_whatsapp': '0'
        }, follow_redirects=True)
        self.assertEqual(res_treasurer.status_code, 200)
        n_treasurer = query_db("SELECT * FROM tbl_notices WHERE title = %s", ('FY 2026-27 Annual Budget Review Meeting',), one=True)
        self.assertIsNotNone(n_treasurer)
        self.assertEqual(n_treasurer['posted_by'], 'Mr. Swapnadeep Ganguly')
        self.assertEqual(n_treasurer['posted_by_role'], 'Treasurer')

        # 2. Post Notice as President (Dr. Asit Kumar Bera)
        res_pres = self.client.post('/notices/create', data={
            'title': 'Emergency General Body Meeting (EGM)',
            'content': 'Meeting called to discuss lift modernisation tenders.',
            'category': 'AGM_MEETING',
            'priority': 'URGENT',
            'caller_role': 'President',
            'is_pinned': '1',
            'do_broadcast': '0',
            'do_whatsapp': '0'
        }, follow_redirects=True)
        self.assertEqual(res_pres.status_code, 200)
        n_pres = query_db("SELECT * FROM tbl_notices WHERE title = %s", ('Emergency General Body Meeting (EGM)',), one=True)
        self.assertIsNotNone(n_pres)
        self.assertEqual(n_pres['posted_by'], 'Dr. Asit Kumar Bera')
        self.assertEqual(n_pres['posted_by_role'], 'President')

        # 3. Post Notice as Caretaker (Mr. Sanjoy Chakraborty)
        res_care = self.client.post('/notices/create', data={
            'title': 'Deep Cleaning of Overhead Tanks',
            'content': 'Water supply suspended between 10 AM and 2 PM on Tuesday.',
            'category': 'WATER_SUPPLY',
            'priority': 'NORMAL',
            'caller_role': 'Caretaker',
            'is_pinned': '0',
            'do_broadcast': '0',
            'do_whatsapp': '0'
        }, follow_redirects=True)
        self.assertEqual(res_care.status_code, 200)
        n_care = query_db("SELECT * FROM tbl_notices WHERE title = %s", ('Deep Cleaning of Overhead Tanks',), one=True)
        self.assertIsNotNone(n_care)
        self.assertEqual(n_care['posted_by'], 'Mr. Sanjoy Chakraborty')
        self.assertEqual(n_care['posted_by_role'], 'Caretaker')

        # 4. Edit Notice to change calling authority to Secretary
        res_edit = self.client.post(f'/notices/{n_care["id"]}/edit', data={
            'title': 'Deep Cleaning of Overhead Tanks - Rescheduled',
            'content': 'Water supply suspended between 11 AM and 3 PM on Wednesday.',
            'category': 'WATER_SUPPLY',
            'priority': 'HIGH',
            'caller_role': 'Secretary',
            'status': 'ACTIVE'
        }, follow_redirects=True)
        self.assertEqual(res_edit.status_code, 200)
        n_updated = query_db("SELECT * FROM tbl_notices WHERE id = %s", (n_care['id'],), one=True)
        self.assertEqual(n_updated['posted_by'], 'Mr. Somenath Halder')
        self.assertEqual(n_updated['posted_by_role'], 'Secretary')

        # 5. Post Notice with Custom Signatory
        res_custom = self.client.post('/notices/create', data={
            'title': 'Durga Puja Cultural Program Auditions',
            'content': 'Children auditions will begin at Community Hall from 5 PM.',
            'category': 'EVENTS_FESTIVAL',
            'priority': 'NORMAL',
            'caller_role': 'Custom',
            'posted_by': 'Durga Puja Sub-Committee',
            'posted_by_role': 'Cultural Convenor',
            'is_pinned': '0',
            'do_broadcast': '0',
            'do_whatsapp': '0'
        }, follow_redirects=True)
        self.assertEqual(res_custom.status_code, 200)
        n_custom = query_db("SELECT * FROM tbl_notices WHERE title = %s", ('Durga Puja Cultural Program Auditions',), one=True)
        self.assertIsNotNone(n_custom)
        self.assertEqual(n_custom['posted_by'], 'Durga Puja Sub-Committee')
        self.assertEqual(n_custom['posted_by_role'], 'Cultural Convenor')
        print("[PASS] Test 4: Calling authority selection (Treasurer, President, Secretary, Caretaker, Custom) verified.")

    def test_05_meeting_type_subcategories(self):
        """Verify meeting type subcategory support (AGM, GB, SGB, Governing Body, Custom) in create, edit, filter, and broadcast."""
        with self.client.session_transaction() as sess:
            sess['user'] = {
                'id': 99,
                'username': 'secretary',
                'name': 'Somenath Halder',
                'role': 'secretary',
                'is_admin': True
            }

        # 1. Post Notice as Special General Body (SGB)
        res_sgb = self.client.post('/notices/create', data={
            'title': 'Special General Body Meeting for Solar Panel Installation',
            'content': 'Special meeting of all flat owners to discuss rooftop solar panel tenders and capital fund allocation.',
            'category': 'AGM_MEETING',
            'meeting_type': 'SGB',
            'priority': 'HIGH',
            'caller_role': 'Secretary',
            'is_pinned': '1',
            'do_broadcast': '0',
            'do_whatsapp': '0'
        }, follow_redirects=True)
        self.assertEqual(res_sgb.status_code, 200)
        n_sgb = query_db("SELECT * FROM tbl_notices WHERE title = %s", ('Special General Body Meeting for Solar Panel Installation',), one=True)
        self.assertIsNotNone(n_sgb)
        self.assertEqual(n_sgb['category'], 'AGM_MEETING')
        self.assertEqual(n_sgb['meeting_type'], 'SGB')

        # 2. Post Notice as Governing Body Meeting
        res_gov = self.client.post('/notices/create', data={
            'title': 'Q3 Governing Body & Executive Committee Review',
            'content': 'Quarterly review of security operations, CCTV upgrades, and outstanding maintenance dues.',
            'category': 'AGM_MEETING',
            'meeting_type': 'GOVERNING_BODY',
            'priority': 'NORMAL',
            'caller_role': 'President',
            'is_pinned': '0',
            'do_broadcast': '0',
            'do_whatsapp': '0'
        }, follow_redirects=True)
        self.assertEqual(res_gov.status_code, 200)
        n_gov = query_db("SELECT * FROM tbl_notices WHERE title = %s", ('Q3 Governing Body & Executive Committee Review',), one=True)
        self.assertIsNotNone(n_gov)
        self.assertEqual(n_gov['meeting_type'], 'GOVERNING_BODY')

        # 3. Post Notice with General Body (GB)
        res_gb = self.client.post('/notices/create', data={
            'title': 'Half-Yearly General Body (GB) Meeting',
            'content': 'All members are invited for the half-yearly GB progress report.',
            'category': 'AGM_MEETING',
            'meeting_type': 'GB',
            'priority': 'NORMAL',
            'caller_role': 'Secretary',
            'is_pinned': '0',
            'do_broadcast': '0',
            'do_whatsapp': '0'
        }, follow_redirects=True)
        self.assertEqual(res_gb.status_code, 200)
        n_gb = query_db("SELECT * FROM tbl_notices WHERE title = %s", ('Half-Yearly General Body (GB) Meeting',), one=True)
        self.assertIsNotNone(n_gb)
        self.assertEqual(n_gb['meeting_type'], 'GB')

        # 4. Post Notice with Custom Meeting Type
        res_custom_mt = self.client.post('/notices/create', data={
            'title': 'Elevator Modernisation Sub-Committee Meet',
            'content': 'Review technical specifications submitted by Kone and Otis.',
            'category': 'AGM_MEETING',
            'meeting_type': 'CUSTOM',
            'custom_meeting_type': 'Elevator Sub-Committee',
            'priority': 'NORMAL',
            'caller_role': 'Executive Committee',
            'is_pinned': '0',
            'do_broadcast': '0',
            'do_whatsapp': '0'
        }, follow_redirects=True)
        self.assertEqual(res_custom_mt.status_code, 200)
        n_custom_mt = query_db("SELECT * FROM tbl_notices WHERE title = %s", ('Elevator Modernisation Sub-Committee Meet',), one=True)
        self.assertIsNotNone(n_custom_mt)
        self.assertEqual(n_custom_mt['meeting_type'], 'Elevator Sub-Committee')

        # 5. Edit Notice to change meeting type from GB to EGM
        res_edit = self.client.post(f'/notices/{n_gb["id"]}/edit', data={
            'title': 'Emergency General Meeting (EGM) on Security Breach',
            'content': 'Urgent EGM called due to security perimeter inspection findings.',
            'category': 'AGM_MEETING',
            'meeting_type': 'EGM',
            'priority': 'URGENT',
            'status': 'ACTIVE'
        }, follow_redirects=True)
        self.assertEqual(res_edit.status_code, 200)
        n_updated = query_db("SELECT * FROM tbl_notices WHERE id = %s", (n_gb['id'],), one=True)
        self.assertEqual(n_updated['meeting_type'], 'EGM')
        self.assertEqual(n_updated['priority'], 'URGENT')

        # 6. Test Filtering by Meeting Type via GET /notices?category=AGM_MEETING&meeting_type=SGB
        res_filter_sgb = self.client.get('/notices?category=AGM_MEETING&meeting_type=SGB')
        self.assertEqual(res_filter_sgb.status_code, 200)
        self.assertIn(b"Special General Body Meeting for Solar Panel Installation", res_filter_sgb.data)

        # 7. Test standalone view page
        res_view = self.client.get(f'/notices/{n_sgb["id"]}/view')
        self.assertEqual(res_view.status_code, 200)
        self.assertIn(b"SGB", res_view.data)
        self.assertIn(b"Meeting", res_view.data)

        # 8. Test WhatsApp Preview API containing meeting type, Category: Meeting, and meeting date
        res_wa = self.client.get(f'/api/whatsapp/preview?type=notice&id={n_sgb["id"]}')
        self.assertEqual(res_wa.status_code, 200)
        wa_data = res_wa.get_json()
        self.assertTrue(wa_data['success'])
        self.assertIn("*Category:* Meeting", wa_data['message_text'])
        self.assertNotIn("Agm Meeting", wa_data['message_text'])
        self.assertIn("*Meeting Type:* SGB", wa_data['message_text'])

        print("[PASS] Test 5: Meeting type sub-categories (AGM, GB, SGB, Governing Body, EGM, Custom) and meeting dates in create, edit, filter, and broadcast verified.")

if __name__ == '__main__':
    unittest.main()
