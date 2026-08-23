import unittest
from datetime import datetime, date
from app import app, calculate_flat_penalty
from database import query_db, execute_db, init_db
from whatsapp_service import format_receipt_whatsapp_message
from pdf_service import generate_receipt_pdf_bytes

class TestReceiptDatesAndPenaltyCalculation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        self.client = app.test_client()
        app.config['TESTING'] = True
        # Login as treasurer / admin
        self.client.post('/login', data={'username': 'treasurer', 'password': 'sdera@123'}, follow_redirects=True)

    def test_01_receipt_creation_with_varying_dates(self):
        """Verify receipt creation records distinct payment_date and receipt_date in database."""
        test_rcpt_no = 9991
        # Cleanup if exists
        execute_db("DELETE FROM tbl_receipts WHERE receipt_no = %s", (test_rcpt_no,))

        resp = self.client.post('/admin/receipts/new', data={
            'receipt_no': str(test_rcpt_no),
            'flat_no': 'A/4-C',
            'amount': '2110.00',
            'pymnt_mode': 'Online',
            'subscription_type': 'Monthly Subscription',
            'remarks': "Jul'2026",
            'payment_date': '2026-07-10',
            'receipt_date': '2026-08-23',
            'coverage_start': '2026-07-01',
            'coverage_end': '2026-07-31',
            'auto_email': '0'
        }, follow_redirects=True)

        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'generated successfully', resp.data)

        # Verify in database
        rcpt = query_db("SELECT * FROM tbl_receipts WHERE receipt_no = %s", (test_rcpt_no,), one=True)
        self.assertIsNotNone(rcpt)
        self.assertEqual(str(rcpt['payment_date']), '2026-07-10')
        self.assertEqual(str(rcpt['receipt_date']), '2026-08-23')
        self.assertEqual(float(rcpt['amount']), 2110.00)

        # Cleanup
        execute_db("DELETE FROM tbl_receipts WHERE receipt_no = %s", (test_rcpt_no,))

    def test_02_penalty_calculation_strictly_based_on_payment_date(self):
        """
        Verify that penalty calculation evaluates overdue status as of the Payment Date,
        regardless of what day receipt is generated or evaluated.
        """
        # Flat A/4-C is covered through July 2026 (2026-07-31).
        # August 2026 maintenance is due on 2026-08-31.
        # September 2026 maintenance is due on 2026-09-30.

        # 1. Payment made on 2026-08-20 (Before August 31) -> 0 overdue months, 0 penalty
        calc_aug = calculate_flat_penalty('A/4-C', target_date='2026-08-20')
        self.assertEqual(calc_aug['overdue_months'], 0)
        self.assertEqual(calc_aug['penalty_amount'], 0)

        # 2. Payment made on 2026-09-05 (Past August 31, but before Sept 30) -> 1 overdue month (August), ₹100 penalty
        calc_sep = calculate_flat_penalty('A/4-C', target_date='2026-09-05')
        self.assertEqual(calc_sep['overdue_months'], 1)
        self.assertEqual(calc_sep['penalty_amount'], 100)

        # 3. Payment made on 2026-10-05 (Past Sept 30) -> 2 overdue months (August & September), ₹300 penalty
        calc_oct = calculate_flat_penalty('A/4-C', target_date='2026-10-05')
        self.assertEqual(calc_oct['overdue_months'], 2)
        self.assertEqual(calc_oct['penalty_amount'], 300) # (2 * 3 / 2) * 100 = 300

    def test_03_api_penalties_calculate_endpoint_with_payment_date(self):
        """Verify /api/penalties/calculate accepts payment_date parameter and returns accurate calculation."""
        resp = self.client.get('/api/penalties/calculate?flat=A/4-C&payment_date=2026-09-05')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['data']['overdue_months'], 1)
        self.assertEqual(data['data']['penalty_amount'], 100)
        self.assertEqual(data['data']['as_of_date'], '2026-09-05')

    def test_04_api_get_receipt_and_edit_receipt(self):
        """Verify /api/receipts/<receipt_no> and /admin/receipts/<receipt_no>/edit work correctly."""
        test_rcpt_no = 9992
        execute_db("DELETE FROM tbl_receipts WHERE receipt_no = %s", (test_rcpt_no,))

        # Create receipt
        execute_db(
            """INSERT INTO tbl_receipts (receipt_no, flat_no, member_name, amount, pymnt_mode, subscription_type, remarks, payment_date, receipt_date)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (test_rcpt_no, 'A/4-C', 'Swapnadeep Ganguly', 2110.00, 'Cash', 'Monthly Subscription', "Jul'2026", '2026-07-05', '2026-07-05')
        )

        # 1. Fetch via API
        resp_get = self.client.get(f'/api/receipts/{test_rcpt_no}')
        self.assertEqual(resp_get.status_code, 200)
        json_r = resp_get.get_json()
        self.assertTrue(json_r['success'])
        self.assertEqual(json_r['receipt']['receipt_no'], test_rcpt_no)
        self.assertEqual(json_r['receipt']['payment_date'], '2026-07-05')

        # 2. Edit dates & remarks
        resp_edit = self.client.post(f'/admin/receipts/{test_rcpt_no}/edit', data={
            'payment_date': '2026-07-08',
            'receipt_date': '2026-08-20',
            'amount': '2210.00',
            'pymnt_mode': 'Online UPI',
            'subscription_type': 'Monthly Subscription',
            'remarks': "Jul'2026 + Penalty ₹100",
            'coverage_start': '2026-07-01',
            'coverage_end': '2026-07-31'
        }, follow_redirects=True)

        self.assertEqual(resp_edit.status_code, 200)
        self.assertIn(b'updated successfully', resp_edit.data)

        # 3. Verify updated in DB
        updated = query_db("SELECT * FROM tbl_receipts WHERE receipt_no = %s", (test_rcpt_no,), one=True)
        self.assertEqual(str(updated['payment_date']), '2026-07-08')
        self.assertEqual(str(updated['receipt_date']), '2026-08-20')
        self.assertEqual(float(updated['amount']), 2210.00)
        self.assertEqual(updated['remarks'], "Jul'2026 + Penalty ₹100")
        self.assertEqual(updated['pymnt_mode'], 'Online UPI')

        # Cleanup
        execute_db("DELETE FROM tbl_receipts WHERE receipt_no = %s", (test_rcpt_no,))

    def test_05_whatsapp_message_dual_dates(self):
        """Verify WhatsApp message includes both Payment Date and Date of Issue when they differ."""
        rcpt = {
            'receipt_no': 2999,
            'flat_no': 'A/4-C',
            'member_name': 'Swapnadeep Ganguly',
            'amount': 2110.0,
            'payment_date': '2026-07-15',
            'receipt_date': '2026-08-20',
            'pymnt_mode': 'Online UPI',
            'remarks': "Jul'2026",
            'subscription_type': 'Monthly Subscription'
        }
        msg = format_receipt_whatsapp_message(rcpt)
        self.assertIn('*Payment Date:* 2026-07-15', msg)
        self.assertIn('*Date of Issue:* 2026-08-20', msg)
        self.assertIn('*Receipt No:* `SDERA_2999`', msg)

    def test_06_pdf_receipt_generation_with_dual_dates(self):
        """Verify vector PDF generation succeeds with distinct payment_date and receipt_date."""
        rcpt = {
            'receipt_no': 2999,
            'flat_no': 'A/4-C',
            'member_name': 'Swapnadeep Ganguly',
            'amount': 2110.0,
            'payment_date': '2026-07-15',
            'receipt_date': '2026-08-20',
            'pymnt_mode': 'Online UPI',
            'remarks': "Jul'2026",
            'subscription_type': 'Monthly Subscription'
        }
        pdf_bytes = generate_receipt_pdf_bytes(rcpt)
        self.assertTrue(len(pdf_bytes) > 1000)
        self.assertTrue(pdf_bytes.startswith(b'%PDF-'))

if __name__ == '__main__':
    unittest.main()
