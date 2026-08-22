import unittest
from app import app

class TestChartCrossFilter(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()
        app.config['TESTING'] = True

    def test_dashboard_chart_and_filter_attributes(self):
        self.client.post('/login', data={'username': 'treasurer', 'password': 'sdera@123'}, follow_redirects=True)
        resp = self.client.get('/dashboard')
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode('utf-8')
        
        # Check chart canvas & titles
        self.assertIn('id="expenseMonthlyChart"', html)
        self.assertIn('Monthly Expenditure Trajectory', html)
        self.assertIn('Society Expenditure Outlays', html)
        
        # Check active filter banner & buttons
        self.assertIn('id="adminExpFilterBanner"', html)
        self.assertIn('id="adminExpFilterLabel"', html)
        self.assertIn('id="adminExpFilterStat"', html)
        self.assertIn('clearMonthlyChartFilter()', html)
        
        # Check table data attributes
        self.assertIn('id="adminRecentExpensesTable"', html)
        self.assertIn('data-voucher-date=', html)
        self.assertIn('data-particulars=', html)
        print("[OK] Dashboard HTML contains all required chart cross-filtering elements and attributes.")

    def test_expenses_page_chart_and_filter_attributes(self):
        self.client.post('/login', data={'username': 'treasurer', 'password': 'sdera@123'}, follow_redirects=True)
        resp = self.client.get('/expenses')
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode('utf-8')
        
        self.assertIn('id="expenseMonthlyChart"', html)
        self.assertIn('id="expensesFilterBanner"', html)
        self.assertIn('id="expensesTable"', html)
        self.assertIn('data-voucher-date=', html)
        print("[OK] Expenses page HTML contains all required chart cross-filtering elements and attributes.")

    def test_charts_js_functions(self):
        resp = self.client.get('/static/js/charts.js')
        self.assertEqual(resp.status_code, 200)
        js_text = resp.data.decode('utf-8')
        
        self.assertIn('toggleMonthExpenditureFilter', js_text)
        self.assertIn('clearMonthlyChartFilter', js_text)
        self.assertIn('applyExpenditureFilters', js_text)
        self.assertIn('parseVoucherMonthYear', js_text)
        self.assertIn('getBarColors', js_text)
        print("[OK] charts.js contains all cross-filter and helper functions.")

if __name__ == '__main__':
    unittest.main()
