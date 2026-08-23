import unittest
from datetime import datetime, timezone, timedelta
from app import app, get_ist_now, log_activity, format_audit_dt_filter, format_audit_date_filter, format_audit_time_filter, time_ago_filter
from database import query_db

class TestAuditTimestamps(unittest.TestCase):
    def setUp(self):
        self.app = app
        self.client = self.app.test_client()
        self.app.config['TESTING'] = True

    def test_01_ist_timezone_offset(self):
        """Verify get_ist_now() returns IST (+05:30) datetime."""
        now_ist = get_ist_now()
        tz_offset = now_ist.utcoffset()
        self.assertEqual(tz_offset, timedelta(hours=5, minutes=30))
        
        # Verify strftime formatting works cleanly
        now_str = now_ist.strftime('%Y-%m-%d %H:%M:%S')
        self.assertEqual(len(now_str), 19)

    def test_02_template_filters(self):
        """Verify custom Jinja datetime & relative time filters."""
        test_dt = datetime(2026, 8, 23, 19, 45, 30)
        formatted_dt = format_audit_dt_filter(test_dt)
        self.assertIn('23 Aug 2026', formatted_dt)
        self.assertIn('07:45:30 PM', formatted_dt)

        formatted_date = format_audit_date_filter(test_dt)
        self.assertEqual(formatted_date, '23 Aug 2026')

        formatted_time = format_audit_time_filter(test_dt)
        self.assertEqual(formatted_time, '07:45:30 PM')

        # Test string parsing
        str_formatted = format_audit_dt_filter('2026-08-23 19:45:30')
        self.assertIn('23 Aug 2026', str_formatted)
        self.assertIn('07:45:30 PM', str_formatted)

        # Test relative time filter
        recent_dt = get_ist_now().replace(tzinfo=None) - timedelta(minutes=5)
        rel_str = time_ago_filter(recent_dt)
        self.assertEqual(rel_str, '5m ago')

        yesterday_dt = get_ist_now().replace(tzinfo=None) - timedelta(days=1)
        self.assertEqual(time_ago_filter(yesterday_dt), 'Yesterday')

    def test_03_log_activity_persistence(self):
        """Verify log_activity accurately records IST timestamp into tbl_activity_logs."""
        actor = {
            'username': 'test_admin',
            'name': 'Test Officer',
            'role': 'super_admin',
            'flat_no': 'A/4-C'
        }
        test_desc = "Automated test IST audit trail verification entry"
        log_activity('TEST_IST_ACTION', test_desc, actor=actor, ip_address='127.0.0.1')

        # Query recent entry
        row = query_db("SELECT * FROM tbl_activity_logs WHERE action_type = 'TEST_IST_ACTION' ORDER BY id DESC LIMIT 1", one=True)
        self.assertIsNotNone(row)
        self.assertEqual(row['actor_username'], 'test_admin')
        self.assertEqual(row['description'], test_desc)
        
        # Verify created_at is near IST now
        created_at = row['created_at']
        if isinstance(created_at, str):
            dt = datetime.strptime(created_at[:19], '%Y-%m-%d %H:%M:%S')
        else:
            dt = created_at
        now_naive = get_ist_now().replace(tzinfo=None)
        diff = abs((now_naive - dt).total_seconds())
        self.assertLess(diff, 60) # within 60 seconds

    def test_04_admin_audit_logs_endpoint_rendering(self):
        """Verify /admin/audit-logs renders successfully with formatted IST timestamp elements."""
        with self.client.session_transaction() as sess:
            sess['user'] = {
                'username': 'admin',
                'name': 'Mr. Sanjoy Chakraborty',
                'role': 'super_admin',
                'flat_no': 'Office'
            }
        response = self.client.get('/admin/audit-logs')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Timestamp (IST)', response.data)
        self.assertIn(b'IST</span>', response.data)
        self.assertIn(b'Chronological Activity Records', response.data)

if __name__ == '__main__':
    unittest.main()
