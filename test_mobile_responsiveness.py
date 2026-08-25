import unittest
from app import app
from database import init_db

class TestMobileResponsiveness(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        self.client = app.test_client()
        app.config['TESTING'] = True

    def _login_as_admin(self):
        return self.client.post('/login', data={'username': 'admin', 'password': 'passwd'}, follow_redirects=True)

    def _login_as_resident(self):
        return self.client.post('/login', data={'username': 'A/1-B', 'password': 'sdera@123'}, follow_redirects=True)

    def test_viewport_meta_tag_present(self):
        """All pages must have a responsive viewport meta tag with width=device-width"""
        pages = ['/login']
        for p in pages:
            resp = self.client.get(p)
            self.assertEqual(resp.status_code, 200)
            html = resp.data.decode('utf-8')
            self.assertIn('<meta name="viewport"', html)
            self.assertIn('width=device-width', html)

    def test_css_responsive_rules_present(self):
        """style.css must contain responsive breakpoints and overflow containment"""
        with open('static/css/style.css', 'r', encoding='utf-8') as f:
            css = f.read()

        self.assertIn('overflow-x: hidden', css)
        self.assertIn('@media (max-width: 1024px)', css)
        self.assertIn('@media (max-width: 900px)', css)
        self.assertIn('@media (max-width: 768px)', css)
        self.assertIn('@media (max-width: 640px)', css)
        self.assertIn('@media (max-width: 480px)', css)
        self.assertIn('font-size: 16px !important', css) # iOS auto-zoom prevention

    def test_login_page_mobile_elements(self):
        """Login page must have responsive demo buttons, cards, and containers"""
        resp = self.client.get('/login')
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode('utf-8')

        self.assertIn('login-container', html)
        self.assertIn('login-card', html)
        self.assertIn('demo-hub-card', html)
        self.assertIn('flex-wrap: wrap', html) # Demo button wrapping

    def test_dashboard_admin_and_resident_responsiveness(self):
        """Dashboard must render cleanly for both admin and resident with table-containers"""
        self._login_as_admin()
        resp = self.client.get('/dashboard')
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode('utf-8')
        self.assertIn('building-visualizer-card', html)

        self.client.get('/logout')
        self._login_as_resident()
        resp2 = self.client.get('/dashboard')
        self.assertEqual(resp2.status_code, 200)
        html2 = resp2.data.decode('utf-8')
        self.assertIn('status-stepper-container', html2)
        self.assertIn('table-container', html2)

    def test_notices_page_responsiveness(self):
        """Notices list page must render with responsive filter bar and cards"""
        self._login_as_resident()
        resp = self.client.get('/notices')
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode('utf-8')
        self.assertIn('filter-box', html)
        self.assertIn('notices-grid', html)

    def test_expenses_page_responsiveness(self):
        """Expenses list page must render with responsive filter bar and table container"""
        self._login_as_resident()
        resp = self.client.get('/expenses')
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode('utf-8')
        self.assertIn('filter-box', html)
        self.assertIn('table-container', html)

    def test_admin_billing_rates_formula_wrapping(self):
        """Admin tariff console formula block must have word-break and white-space normal"""
        self._login_as_admin()
        resp = self.client.get('/admin/billing-rates')
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode('utf-8')
        self.assertIn('word-break: break-word', html)
        self.assertIn('white-space: normal', html)

    def test_admin_penalties_responsiveness(self):
        """Admin penalties formula and scale cards must have word-break and responsive grid"""
        self._login_as_admin()
        resp = self.client.get('/admin/penalties')
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode('utf-8')
        self.assertIn('word-break: break-word', html)
        self.assertIn('table-container', html)

    def test_admin_members_and_receipts_tables(self):
        """Admin members and receipts ledger tables must be inside table-containers"""
        self._login_as_admin()
        resp_m = self.client.get('/admin/members')
        self.assertEqual(resp_m.status_code, 200)
        self.assertIn(b'table-container', resp_m.data)

        resp_r = self.client.get('/admin/receipts')
        self.assertEqual(resp_r.status_code, 200)
        self.assertIn(b'table-container', resp_r.data)

    def test_receipt_voucher_responsiveness(self):
        """Single receipt view must have responsive toolbar and voucher details"""
        from database import query_db
        rcpt = query_db("SELECT receipt_no FROM tbl_receipts LIMIT 1", one=True)
        self._login_as_admin()
        resp = self.client.get(f'/receipts/{rcpt["receipt_no"]}')
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode('utf-8')
        self.assertIn('receipt-voucher', html)
        self.assertIn('flex-wrap: wrap', html)

    def test_notice_single_responsiveness(self):
        """Single notice circular must have responsive meta tag and media queries"""
        from database import query_db
        notc = query_db("SELECT id FROM tbl_notices LIMIT 1", one=True)
        self._login_as_admin()
        resp = self.client.get(f'/notices/{notc["id"]}/view')
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode('utf-8')
        self.assertIn('<meta name="viewport"', html)
        self.assertIn('@media (max-width: 640px)', html)

if __name__ == '__main__':
    unittest.main()
