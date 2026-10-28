import unittest
from datetime import datetime, date
from app import app, get_ist_now
from database import query_db, execute_db, init_db

class TestReceiptMonthAutopopulation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        self.client = app.test_client()
        app.config['TESTING'] = True
        self.client.post('/login', data={'username': 'treasurer', 'password': 'sdera@123'}, follow_redirects=True)

    def test_01_receipt_page_renders_current_month_default_value(self):
        """Verify admin receipts page renders the Month/Remarks field auto-populated with current IST month (e.g. Oct'2026)."""
        resp = self.client.get('/admin/receipts')
        self.assertEqual(resp.status_code, 200)
        
        current_ist_month = get_ist_now().strftime("%b'%Y")
        expected_val_attr = f'value="{current_ist_month}"'
        
        html = resp.data.decode('utf-8')
        self.assertIn('id="rcpt_remarks"', html)
        self.assertIn(expected_val_attr, html)
        self.assertIn('id="rcptMonthQuickPills"', html)
        self.assertIn('formatMonthRemarks', html)
        self.assertIn('openCreateReceiptModal', html)

    def test_02_backend_auto_populates_october_when_paying_for_october(self):
        """Verify backend auto-populates Oct'2026 when creating receipt with October payment date and blank remarks."""
        test_rcpt_no = 9993
        execute_db("DELETE FROM tbl_receipts WHERE receipt_no = %s", (test_rcpt_no,))

        resp = self.client.post('/admin/receipts/new', data={
            'receipt_no': str(test_rcpt_no),
            'flat_no': 'A/4-C',
            'amount': '2110.00',
            'pymnt_mode': 'Online',
            'subscription_type': 'Monthly Subscription',
            'remarks': '',  # intentionally left blank to test auto-population
            'payment_date': '2026-10-15',
            'receipt_date': '2026-10-28',
            'auto_email': '0'
        }, follow_redirects=True)

        self.assertEqual(resp.status_code, 200)
        rcpt = query_db("SELECT * FROM tbl_receipts WHERE receipt_no = %s", (test_rcpt_no,), one=True)
        self.assertIsNotNone(rcpt)
        self.assertEqual(rcpt['remarks'], "Oct'2026")

        execute_db("DELETE FROM tbl_receipts WHERE receipt_no = %s", (test_rcpt_no,))

    def test_03_backend_auto_populates_november_when_paying_for_november(self):
        """Verify backend auto-populates Nov'2026 when creating receipt with November payment date and blank remarks."""
        test_rcpt_no = 9994
        execute_db("DELETE FROM tbl_receipts WHERE receipt_no = %s", (test_rcpt_no,))

        resp = self.client.post('/admin/receipts/new', data={
            'receipt_no': str(test_rcpt_no),
            'flat_no': 'A/4-C',
            'amount': '2110.00',
            'pymnt_mode': 'Online',
            'subscription_type': 'Monthly Subscription',
            'remarks': '',  # blank to test auto-population for November
            'payment_date': '2026-11-08',
            'receipt_date': '2026-11-08',
            'auto_email': '0'
        }, follow_redirects=True)

        self.assertEqual(resp.status_code, 200)
        rcpt = query_db("SELECT * FROM tbl_receipts WHERE receipt_no = %s", (test_rcpt_no,), one=True)
        self.assertIsNotNone(rcpt)
        self.assertEqual(rcpt['remarks'], "Nov'2026")

        execute_db("DELETE FROM tbl_receipts WHERE receipt_no = %s", (test_rcpt_no,))

    def test_04_user_custom_remarks_are_preserved(self):
        """Verify that if a user provides custom remarks (e.g. advance payment or multiple months), it is preserved."""
        test_rcpt_no = 9995
        execute_db("DELETE FROM tbl_receipts WHERE receipt_no = %s", (test_rcpt_no,))

        custom_text = "Advance Oct'2026 to Dec'2026 (3 Months)"
        resp = self.client.post('/admin/receipts/new', data={
            'receipt_no': str(test_rcpt_no),
            'flat_no': 'A/4-C',
            'amount': '6330.00',
            'pymnt_mode': 'Cheque',
            'subscription_type': 'Monthly Subscription',
            'remarks': custom_text,
            'payment_date': '2026-10-20',
            'receipt_date': '2026-10-28',
            'auto_email': '0'
        }, follow_redirects=True)

        self.assertEqual(resp.status_code, 200)
        rcpt = query_db("SELECT * FROM tbl_receipts WHERE receipt_no = %s", (test_rcpt_no,), one=True)
        self.assertIsNotNone(rcpt)
        self.assertEqual(rcpt['remarks'], custom_text)

        execute_db("DELETE FROM tbl_receipts WHERE receipt_no = %s", (test_rcpt_no,))

if __name__ == '__main__':
    unittest.main()
