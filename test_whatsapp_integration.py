import unittest
from datetime import datetime
from app import app
from database import query_db
from whatsapp_service import (
    normalize_whatsapp_phone,
    build_whatsapp_url,
    format_receipt_whatsapp_message,
    format_dues_reminder_whatsapp_message,
    format_notice_whatsapp_message,
    send_whatsapp_message,
    get_whatsapp_committee_contacts
)

class TestWhatsAppIntegration(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True
        
    def test_phone_normalization(self):
        self.assertEqual(normalize_whatsapp_phone('+91-801-725-0621'), '918017250621')
        self.assertEqual(normalize_whatsapp_phone('09830012345'), '919830012345')
        self.assertEqual(normalize_whatsapp_phone('9830012345'), '919830012345')
        self.assertEqual(normalize_whatsapp_phone('919830012345'), '919830012345')
        self.assertEqual(normalize_whatsapp_phone('+91 98300 55443'), '919830055443')
        self.assertEqual(normalize_whatsapp_phone(''), '')
        print("[PASS] Phone number normalization tests passed.")

    def test_url_generator(self):
        url = build_whatsapp_url('9830012345', 'Hello World')
        self.assertTrue(url.startswith('https://wa.me/919830012345?text=Hello%20World'))
        
        broadcast_url = build_whatsapp_url('', 'Broadcast Notice')
        self.assertTrue(broadcast_url.startswith('https://api.whatsapp.com/send?text=Broadcast%20Notice'))
        print("[PASS] URL generation tests passed.")

    def test_receipt_template(self):
        receipt = {
            'receipt_no': 2202,
            'flat_no': 'A/4-C',
            'member_name': 'Swapnadeep Ganguly',
            'amount': 2250.00,
            'payment_date': '2026-08-15',
            'pymnt_mode': 'Online UPI',
            'remarks': "Aug'2026",
            'subscription_type': 'Monthly Subscription'
        }
        msg = format_receipt_whatsapp_message(receipt, base_url="http://localhost:5000")
        self.assertIn("SDERA_2202", msg)
        self.assertIn("Swapnadeep Ganguly", msg)
        self.assertIn("Flat A/4-C", msg)
        self.assertIn("2,250.00", msg)
        self.assertIn("http://localhost:5000/receipts/2202/pdf", msg)
        print("[PASS] Receipt template formatting tests passed.")

    def test_penalty_template(self):
        calc = {
            'flat_no': 'B/2-A',
            'member_name': 'Resident Name',
            'overdue_months': 3,
            'monthly_charge': 2100.0,
            'base_due': 6300.0,
            'penalty_amount': 600.0,
            'total_due': 6900.0,
            'as_of_full': 'August 31, 2026',
            'coverage_display': "May'2026"
        }
        msg = format_dues_reminder_whatsapp_message(calc, base_url="http://localhost:5000")
        self.assertIn("Flat B/2-A", msg)
        self.assertIn("3 Months", msg)
        self.assertIn("6,900.00", msg)
        self.assertIn("sddra.association@icici", msg)
        print("[PASS] Dues reminder template formatting tests passed.")

    def test_notice_template(self):
        notice = {
            'id': 1,
            'title': 'Emergency Water Shutdown',
            'content': 'Water supply suspended due to main line pipe repair from 2 PM to 5 PM today.',
            'category': 'WATER_SUPPLY',
            'priority': 'URGENT',
            'posted_by': 'Sanjoy Chakraborty',
            'posted_by_role': 'Caretaker',
            'created_at': '2026-08-20'
        }
        msg = format_notice_whatsapp_message(notice, base_url="http://localhost:5000")
        self.assertIn("URGENT ALERT", msg)
        self.assertIn("Emergency Water Shutdown", msg)
        self.assertIn("Sanjoy Chakraborty", msg)
        self.assertIn("/notices/1/view", msg)

        # Meeting Notice formatting: Category should be "Meeting" and date should be the meeting date
        meeting_notice = {
            'id': 2,
            'title': 'Notification: 18th Annual General Meeting (AGM 2026)',
            'content': '18th AGM of SDERA will be held at Community Hall.',
            'category': 'AGM_MEETING',
            'meeting_type': 'AGM',
            'meeting_date': '2026-09-14',
            'priority': 'HIGH',
            'posted_by': 'Dr. Asit Kumar Bera',
            'posted_by_role': 'President',
            'created_at': '2026-08-23'
        }
        msg_meeting = format_notice_whatsapp_message(meeting_notice, base_url="http://localhost:5000")
        self.assertIn("*Category:* Meeting | *Date:* 2026-09-14", msg_meeting)
        self.assertNotIn("Agm Meeting", msg_meeting)
        self.assertNotIn("AGM Meeting", msg_meeting)
        self.assertIn("*Meeting Type:* AGM", msg_meeting)
        print("[PASS] Notice template formatting tests passed.")

    def test_committee_contacts(self):
        contacts = get_whatsapp_committee_contacts()
        self.assertTrue(len(contacts) >= 4)
        c_map = {c['name']: c['clean_phone'] for c in contacts}
        self.assertEqual(c_map.get("Mr. Sanjoy Chakraborty"), "918017250621")
        self.assertEqual(c_map.get("Mr. Somenath Halder"), "919433375506")
        self.assertEqual(c_map.get("Dr. Asit Kumar Bera"), "916290847982")
        self.assertEqual(c_map.get("Mr. Swapnadeep Ganguly"), "919874802000")
        print("[PASS] Committee WhatsApp contacts test passed.")

    def test_helpdesk_privacy_for_unauthenticated_users(self):
        """Verify WhatsApp helpdesk widget and phone numbers are hidden from unauthenticated visitors."""
        # 1. Unauthenticated request to login/home screen
        resp_public = self.app.get('/login')
        self.assertEqual(resp_public.status_code, 200)
        self.assertNotIn(b'waFloatingWidget', resp_public.data)
        self.assertNotIn(b'wa-contacts-list', resp_public.data)
        self.assertNotIn(b'8017250621', resp_public.data)
        self.assertNotIn(b'9433375506', resp_public.data)
        self.assertNotIn(b'6290847982', resp_public.data)
        self.assertNotIn(b'9874802000', resp_public.data)

        # 2. Authenticated member session
        with self.app.session_transaction() as sess:
            sess['user'] = {
                'id': 10,
                'username': 'A/4-C',
                'name': 'Swapnadeep Ganguly',
                'role': 'resident',
                'is_admin': False,
                'flat_no': 'A/4-C'
            }
        resp_auth = self.app.get('/dashboard')
        self.assertEqual(resp_auth.status_code, 200)
        self.assertIn(b'waFloatingWidget', resp_auth.data)
        self.assertIn(b'wa-contacts-list', resp_auth.data)
        self.assertIn(b'918017250621', resp_auth.data)
        print("[PASS] Helpdesk privacy test passed: Hidden before login, visible after login.")

    def test_whatsapp_routes(self):
        with self.app.session_transaction() as sess:
            sess['user'] = {
                'id': 1,
                'username': 'admin',
                'name': 'Admin',
                'role': 'super_admin',
                'is_admin': True,
                'flat_no': 'Office'
            }

        # 1. Preview API for receipt
        res = self.app.get('/api/whatsapp/preview?type=receipt&id=2201')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertIn('SDERA_', data['message_text'])
        print("[PASS] Preview API (Receipt) returned 200 OK.")

        # 2. Preview API for penalty
        res = self.app.get('/api/whatsapp/preview?type=penalty&flat=A/1-B')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertIn('MAINTENANCE DUES', data['message_text'])
        print("[PASS] Preview API (Penalty) returned 200 OK.")

        # 3. Preview API for notice
        res = self.app.get('/api/whatsapp/preview?type=notice&id=1')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertIn('SOUTH DUMDUM ENCLAVE', data['message_text'])
        print("[PASS] Preview API (Notice) returned 200 OK.")

        # 4. Receipt WhatsApp Route (AJAX)
        res = self.app.post('/receipts/2201/whatsapp', json={'phone': '+91 98300 12345'})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertTrue('wa.me/919830012345' in data['direct_url'])
        print("[PASS] Receipt WhatsApp dispatch returned 200 OK.")

        # 5. Penalty WhatsApp Reminder Route (AJAX)
        res = self.app.post('/admin/penalties/whatsapp-reminder', json={'flat_no': 'A/1-B', 'phone': '9830012345'})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertTrue('wa.me/919830012345' in data['direct_url'])
        print("[PASS] Penalty WhatsApp reminder returned 200 OK.")

        # 6. Notice WhatsApp Broadcast Route (AJAX)
        res = self.app.post('/notices/1/whatsapp-broadcast', json={})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        print("[PASS] Notice WhatsApp broadcast returned 200 OK.")

        # 7. WhatsApp Logs in Database
        logs = query_db("SELECT * FROM tbl_whatsapp_logs ORDER BY id DESC LIMIT 10")
        self.assertTrue(len(logs) > 0)
        print(f"[PASS] Verified {len(logs)} audit entries stored in tbl_whatsapp_logs.")

if __name__ == '__main__':
    unittest.main()
