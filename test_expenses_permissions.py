import unittest
from app import app
from database import init_db, query_db, execute_db

class TestExpensesPermissions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        self.client = app.test_client()
        app.config['TESTING'] = True

    def _login_as_admin(self):
        return self.client.post('/login', data={'username': 'admin', 'password': 'passwd'}, follow_redirects=True)

    def test_01_delete_button_removed_from_ui(self):
        """Delete button/form must not exist in expenses.html"""
        self._login_as_admin()
        resp = self.client.get('/expenses')
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode('utf-8')
        
        # Verify delete form and button are removed
        self.assertNotIn('/delete', html)
        self.assertNotIn('Delete Record', html)
        self.assertIn('Edit Voucher', html)

    def test_02_delete_endpoint_disallowed(self):
        """Calling delete expense endpoint does not delete the database record"""
        self._login_as_admin()
        # Find a test expense voucher
        exp = query_db("SELECT voucher_no FROM tbl_expenses LIMIT 1", one=True)
        self.assertIsNotNone(exp)
        v_no = exp['voucher_no']

        # Attempt to delete
        resp = self.client.post(f'/admin/expenses/{v_no}/delete', follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Deleting society expense records is disabled', resp.data)

        # Check voucher still exists in database
        check_exp = query_db("SELECT voucher_no FROM tbl_expenses WHERE voucher_no = %s", (v_no,), one=True)
        self.assertIsNotNone(check_exp)

    def test_03_edit_expense_cannot_alter_amount_or_vno(self):
        """Editing expense updates date, description, particulars, spl_head, payment_by, but preserves original amount"""
        self._login_as_admin()
        exp = query_db("SELECT * FROM tbl_expenses LIMIT 1", one=True)
        self.assertIsNotNone(exp)
        v_no = exp['voucher_no']
        orig_amount = float(exp['amount'])

        # Attempt to edit, passing a manipulated amount
        resp = self.client.post(
            f'/admin/expenses/{v_no}/edit',
            data={
                'voucher_date': '2026-08-20',
                'expense_description': 'Updated Maintenance Testing Description',
                'particulars': 'Repair & Maintenance',
                'spl_head': 'Lift & Motor Service',
                'payment_by': 'Cheque',
                'amount': '9999999.99' # Manipulated amount that must be ignored
            },
            follow_redirects=True
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'updated successfully', resp.data)

        # Verify in database: amount is unchanged, other fields are updated
        updated_exp = query_db("SELECT * FROM tbl_expenses WHERE voucher_no = %s", (v_no,), one=True)
        self.assertIsNotNone(updated_exp)
        self.assertEqual(float(updated_exp['amount']), orig_amount)
        self.assertEqual(str(updated_exp['voucher_date'])[:10], '2026-08-20')
        self.assertEqual(updated_exp['expense_description'], 'Updated Maintenance Testing Description')
        self.assertEqual(updated_exp['particulars'], 'Repair & Maintenance')
        self.assertEqual(updated_exp['spl_head'], 'Lift & Motor Service')
        self.assertEqual(updated_exp['payment_by'], 'Cheque')

    def test_04_edit_modal_ui_locks_amount_and_vno(self):
        """Edit modal displays Amount and Voucher Number with locked/readonly attributes"""
        self._login_as_admin()
        resp = self.client.get('/expenses')
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode('utf-8')

        self.assertIn('id="edit_exp_vno"', html)
        self.assertIn('id="edit_exp_amount"', html)
        self.assertIn('cursor: not-allowed', html)

if __name__ == '__main__':
    unittest.main()
