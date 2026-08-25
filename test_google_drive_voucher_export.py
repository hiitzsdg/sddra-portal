import unittest
import io
import zipfile
from app import app
from database import init_db, query_db

class TestGoogleDriveVoucherExport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        self.client = app.test_client()
        app.config['TESTING'] = True

    def _login_as_admin(self):
        return self.client.post('/login', data={'username': 'admin', 'password': 'passwd'}, follow_redirects=True)

    def test_01_individual_voucher_pdf_generation(self):
        """Single expense voucher PDF endpoint generates valid vector PDF bytes"""
        self._login_as_admin()
        exp = query_db("SELECT voucher_no FROM tbl_expenses LIMIT 1", one=True)
        self.assertIsNotNone(exp)
        v_no = exp['voucher_no']

        resp = self.client.get(f'/expenses/{v_no}/pdf')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.mimetype, 'application/pdf')
        # Check standard PDF header magic bytes
        self.assertTrue(resp.data.startswith(b'%PDF-'))
        self.assertGreater(len(resp.data), 1000)

    def test_02_bulk_zip_archive_generation(self):
        """Bulk ZIP export generates valid ZIP archive containing PDF files for all vouchers"""
        self._login_as_admin()
        total_count = query_db("SELECT COUNT(*) as cnt FROM tbl_expenses", one=True)['cnt']
        self.assertGreater(total_count, 0)

        resp = self.client.get('/expenses/export-zip')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.mimetype, 'application/zip')
        
        # Verify ZIP content
        zip_buf = io.BytesIO(resp.data)
        with zipfile.ZipFile(zip_buf, 'r') as zf:
            names = zf.namelist()
            self.assertEqual(len(names), total_count)
            # Verify each file in the zip is a valid PDF
            for name in names[:5]:
                self.assertTrue(name.endswith('.pdf'))
                pdf_data = zf.read(name)
                self.assertTrue(pdf_data.startswith(b'%PDF-'))

    def test_03_master_pdf_compendium(self):
        """Master PDF Compendium endpoint generates a combined multi-page PDF"""
        self._login_as_admin()
        resp = self.client.get('/expenses/export-master-pdf')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.mimetype, 'application/pdf')
        self.assertTrue(resp.data.startswith(b'%PDF-'))
        self.assertGreater(len(resp.data), 5000)

    def test_04_api_expenses_list_json(self):
        """JSON metadata endpoint returns all vouchers and URLs"""
        self._login_as_admin()
        resp = self.client.get('/api/expenses/list-json')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data['success'])
        self.assertGreater(data['count'], 0)
        self.assertEqual(len(data['vouchers']), data['count'])
        self.assertIn('zip_url', data)
        self.assertIn('master_pdf_url', data)

    def test_05_ui_buttons_and_modals_rendered(self):
        """Expenses page renders Google Drive buttons, PDF download links, and cloud modals"""
        self._login_as_admin()
        resp = self.client.get('/expenses')
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode('utf-8')

        self.assertIn('Save All to Drive', html)
        self.assertIn('All PDFs (ZIP)', html)
        self.assertIn('Master PDF', html)
        self.assertIn('googleDriveBulkModal', html)
        self.assertIn('googleDriveSingleModal', html)
        self.assertIn('saveSingleVoucherToDrive', html)

if __name__ == '__main__':
    unittest.main()
