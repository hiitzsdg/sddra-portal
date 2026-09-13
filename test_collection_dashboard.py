import unittest
import json
from app import app

class TestCollectionDashboard(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        app.config['TESTING'] = True

    def test_collections_chart_data_api(self):
        # 1. Test unauthenticated access redirects
        unauth_resp = self.client.get('/api/collections/chart-data')
        self.assertIn(unauth_resp.status_code, [302, 401])

        # 2. Test authenticated access
        self.client.post('/login', data={'username': 'treasurer', 'password': 'sdera@123'}, follow_redirects=True)
        resp = self.client.get('/api/collections/chart-data')
        self.assertEqual(resp.status_code, 200)
        
        data = resp.get_json()
        self.assertTrue(data.get('success'))
        self.assertIn('payment_modes', data)
        self.assertIn('monthly', data)
        self.assertIn('blocks', data)
        self.assertIn('summary', data)
        
        # Verify monthly collection data contains expected structure
        self.assertTrue(len(data['monthly']) > 0)
        first_month = data['monthly'][0]
        self.assertIn('month', first_month)
        self.assertIn('total', first_month)
        self.assertTrue(first_month['total'] > 0)

        # Verify payment modes contain expected modes (NEFT, Cash)
        modes = [m['mode'] for m in data['payment_modes']]
        self.assertTrue('NEFT' in modes or 'Cash' in modes)
        print(f"[OK] Collection Chart API verified: {len(data['monthly'])} monthly trends, {len(data['payment_modes'])} payment modes, Total: INR {data['summary']['total_collected']:,.2f}")

    def test_dashboard_collection_elements(self):
        self.client.post('/login', data={'username': 'treasurer', 'password': 'sdera@123'}, follow_redirects=True)
        resp = self.client.get('/dashboard')
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode('utf-8')

        # Check collection chart canvases
        self.assertIn('id="collectionModeChart"', html)
        self.assertIn('id="collectionMonthlyChart"', html)
        self.assertIn('id="collectionMonthlyPills"', html)
        self.assertIn('Monthly Maintenance Inflow Trend', html)
        self.assertIn('Maintenance Inflow &amp; Collection Analytics', html)

        # Check filter banner & badges
        self.assertIn('id="adminRcptFilterBanner"', html)
        self.assertIn('id="adminRcptFilterLabel"', html)
        self.assertIn('id="adminRcptFilterStat"', html)
        self.assertIn('id="adminRcptTotalBadge"', html)
        self.assertIn('clearMonthlyCollectionFilter()', html)

        # Check table data attributes
        self.assertIn('id="adminRecentReceiptsTable"', html)
        self.assertIn('data-payment-date=', html)
        self.assertIn('data-payment-ym=', html)
        self.assertIn('data-amount=', html)
        self.assertIn('data-pymnt-mode=', html)
        print("[OK] Dashboard HTML contains all required maintenance collection charts, pills, filter banners, and table attributes.")

    def test_admin_receipts_collection_elements(self):
        self.client.post('/login', data={'username': 'treasurer', 'password': 'sdera@123'}, follow_redirects=True)
        resp = self.client.get('/admin/receipts')
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode('utf-8')

        # Check collection chart canvases in master receipts portal
        self.assertIn('id="collectionModeChart"', html)
        self.assertIn('id="collectionMonthlyChart"', html)
        self.assertIn('id="collectionMonthlyPills"', html)
        self.assertIn('Maintenance Collection &amp; Transparency Ledger', html)

        # Check filter banner & badges
        self.assertIn('id="receiptsFilterBanner"', html)
        self.assertIn('id="receiptsFilterLabel"', html)
        self.assertIn('id="receiptsFilterStat"', html)
        self.assertIn('id="rcptTotalBadge"', html)
        self.assertIn('clearMonthlyCollectionFilter()', html)

        # Check table data attributes
        self.assertIn('id="adminReceiptsTable"', html)
        self.assertIn('data-payment-date=', html)
        self.assertIn('data-payment-ym=', html)
        self.assertIn('data-amount=', html)
        self.assertIn('data-pymnt-mode=', html)
        print("[OK] Admin Receipts page contains all required maintenance collection dashboard elements and cross-filtering attributes.")

    def test_charts_js_collection_functions(self):
        resp = self.client.get('/static/js/charts.js')
        self.assertEqual(resp.status_code, 200)
        js_text = resp.data.decode('utf-8')

        self.assertIn('toggleMonthCollectionFilter', js_text)
        self.assertIn('clearMonthlyCollectionFilter', js_text)
        self.assertIn('togglePaymentModeCollectionFilter', js_text)
        self.assertIn('applyCollectionFilters', js_text)
        self.assertIn('renderCollectionCharts', js_text)
        self.assertIn('getCollectionBarColors', js_text)
        self.assertIn('/api/collections/chart-data', js_text)
        print("[OK] charts.js contains all collection analytics and cross-filtering functions.")

if __name__ == '__main__':
    unittest.main()
