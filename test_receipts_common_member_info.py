import unittest
import json
from app import app
from database import init_db

class TestReceiptsCommonMemberInfo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def setUp(self):
        self.client = app.test_client()
        app.config['TESTING'] = True
        # Login as treasurer (committee admin)
        self.client.post('/login', data={'username': 'treasurer', 'password': 'sdera@123'}, follow_redirects=True)

    def test_01_admin_receipts_contains_common_member_info_elements(self):
        """Verify receipts tab contains Common Member Info components, selector, and modal"""
        resp = self.client.get('/admin/receipts')
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode('utf-8')

        # Check section and cards
        self.assertIn('id="commonMemberInfoSection"', html)
        self.assertIn('id="commonMemberInfoCard"', html)
        self.assertIn('id="commonMemberSelectorCard"', html)
        self.assertIn('Common Member Information Hub', html)
        self.assertIn('id="quickMemberSelect"', html)

        # Check modal
        self.assertIn('id="commonMemberInfoModal"', html)
        self.assertIn('id="modalCmiFlatBadge"', html)
        self.assertIn('id="modalCmiName"', html)
        self.assertIn('id="modalCmiPaid"', html)

        # Check client lookup dictionary and JS functions
        self.assertIn('window.MEMBERS_LOOKUP =', html)
        self.assertIn('function showCommonMemberInfo(', html)
        self.assertIn('function openCommonMemberInfoModal(', html)
        self.assertIn('function issueReceiptForMember(', html)

        # Check interactive row attributes
        self.assertIn('showCommonMemberInfo(', html)
        self.assertIn('openCommonMemberInfoModal(', html)
        print("[OK] Receipts tab contains all Common Member Info structure, modal, and lookup engine.")

    def test_02_admin_receipts_with_flat_filter_displays_member_info(self):
        """Filtering by flat in receipts tab populates member details, contact, and specs"""
        resp = self.client.get('/admin/receipts?flat=A/4-C')
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode('utf-8')

        self.assertIn('COMMON MEMBER INFO', html)
        self.assertIn('Flat A/4-C', html)
        self.assertIn('Swapnadeep Ganguly', html)
        self.assertIn('Total Paid in Ledger', html)
        self.assertIn('Monthly Maintenance', html)
        self.assertIn('Flat Size &amp; Spaces', html)
        self.assertIn('Issue Receipt', html)
        print("[OK] Filtered Receipts view successfully renders server-side Common Member Info card for Flat A/4-C.")

    def test_03_api_member_info_endpoint(self):
        """API endpoints /api/member-info and /api/members/<flat>/info return full member specs and metrics"""
        # Test query parameter
        resp = self.client.get('/api/member-info?flat=A/4-C')
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data['success'])
        self.assertEqual(data['flat_no'], 'A/4-C')
        self.assertIn('Swapnadeep Ganguly', data['member_name'])
        self.assertIn('total_paid', data)
        self.assertIn('receipts_count', data)
        self.assertIn('monthly_charge', data)
        self.assertIn('flat_size', data)
        self.assertIn('penalty', data)

        # Test URL path parameter
        resp2 = self.client.get('/api/members/A/4-C/info')
        self.assertEqual(resp2.status_code, 200)
        data2 = resp2.get_json()
        self.assertTrue(data2['success'])
        self.assertEqual(data2['flat_no'], 'A/4-C')
        print(f"[OK] Member Info API verified for {data['member_name']} (Total Paid: INR {data['total_paid']:,.2f}, {data['receipts_count']} receipts).")

    def test_04_create_receipt_modal_contains_mini_member_info(self):
        """Create receipt modal includes live mini member preview container"""
        resp = self.client.get('/admin/receipts')
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode('utf-8')
        self.assertIn('id="modalCreateMemberInfo"', html)
        print("[OK] Create Receipt modal contains live member info preview container.")

    def test_05_create_receipt_modal_other_person_elements(self):
        """Verify Create Receipt modal has Category toggle, Other Person dropdown, preview card, and purpose selector"""
        resp = self.client.get('/admin/receipts')
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode('utf-8')

        # Check Category Switcher
        self.assertIn('id="btnCategoryMonthly"', html)
        self.assertIn('id="btnCategoryOther"', html)
        self.assertIn('setCreateReceiptType(', html)

        # Check Other Person Section & Dropdown
        self.assertIn('id="rcptOtherPersonSection"', html)
        self.assertIn('id="other_person_select"', html)
        self.assertIn('Khokhon Routh', html)
        self.assertIn('Sanjoy Chakraborty', html)
        self.assertIn('Commercial Vehicle Transporter', html)
        self.assertIn('Community Hall Booker', html)
        self.assertIn('Table &amp; Chair Renter', html)
        self.assertIn('__custom__', html)

        # Check Dynamic Card & Custom inputs
        self.assertIn('id="otherPersonDynamicCard"', html)
        self.assertIn('id="otherPersonInputsGrid"', html)
        self.assertIn('id="other_person_name"', html)
        self.assertIn('id="other_person_flat"', html)
        self.assertIn('id="other_person_phone"', html)
        self.assertIn('id="other_income_purpose_select"', html)
        self.assertIn('4 Wheeler Parking Charge', html)

        # Check JS functions
        self.assertIn('function onOtherPersonChange(', html)
        self.assertIn('function toggleOtherPersonInputs(', html)
        self.assertIn('function onOtherIncomePurposeChange(', html)
        print("[OK] Create Receipt Modal successfully contains all Other Person UI components, dropdown options, and handlers.")

    def test_06_issue_other_income_receipt_with_other_person(self):
        """Issue an Other Income receipt for an Other Person, verify DB record and receipt view"""
        from database import query_db, execute_db

        # Clean up any previous test receipt #9991 and #9992
        execute_db("DELETE FROM tbl_receipts WHERE receipt_no IN (9991, 9992)")

        # 1. Issue receipt for Staff (Khokhon Routh)
        post_data_staff = {
            'receipt_no': '9991',
            'subscription_type': 'Other Income',
            'other_person_select': 'Khokhon Routh',
            'other_person_name': 'Khokhon Routh',
            'other_person_flat': 'STAFF',
            'other_person_phone': '9831000001',
            'amount': '750.00',
            'pymnt_mode': 'Cash',
            'remarks': 'Staff Maintenance Reimbursement',
            'payment_date': '2026-10-27',
            'receipt_date': '2026-10-27',
            'auto_email': '0'
        }
        resp = self.client.post('/admin/receipts/new', data=post_data_staff, follow_redirects=True)
        self.assertEqual(resp.status_code, 200)

        # Verify DB entry
        rcpt1 = query_db("SELECT * FROM tbl_receipts WHERE receipt_no = 9991", one=True)
        self.assertIsNotNone(rcpt1)
        self.assertEqual(rcpt1['subscription_type'], 'Other Income')
        self.assertEqual(rcpt1['member_name'], 'Khokhon Routh')
        self.assertEqual(rcpt1['flat_no'], 'STAFF')
        self.assertEqual(float(rcpt1['amount']), 750.00)

        # Verify HTML view
        resp_view = self.client.get('/receipts/9991')
        self.assertEqual(resp_view.status_code, 200)
        view_html = resp_view.data.decode('utf-8')
        self.assertIn('Khokhon Routh', view_html)
        self.assertIn('STAFF', view_html)
        self.assertIn('Payer / Person Name', view_html)
        self.assertIn('OFFICIAL MISCELLANEOUS / SUNDRY RECEIPT', view_html)

        # Verify PDF generation
        resp_pdf = self.client.get('/receipts/9991/pdf')
        self.assertEqual(resp_pdf.status_code, 200)
        self.assertEqual(resp_pdf.content_type, 'application/pdf')

        # 2. Issue receipt for Custom Other Person (Commercial Vehicle)
        post_data_custom = {
            'receipt_no': '9992',
            'subscription_type': 'Other Income',
            'other_person_select': '__custom__',
            'other_person_name': 'WB Transport Fleet (Delivery Bay)',
            'other_person_flat': 'OTHER',
            'other_person_phone': '9830012345',
            'amount': '1500.00',
            'pymnt_mode': 'Online',
            'remarks': 'Commercial Vehicle Bay Parking',
            'payment_date': '2026-10-27',
            'receipt_date': '2026-10-27',
            'auto_email': '0'
        }
        resp2 = self.client.post('/admin/receipts/new', data=post_data_custom, follow_redirects=True)
        self.assertEqual(resp2.status_code, 200)

        rcpt2 = query_db("SELECT * FROM tbl_receipts WHERE receipt_no = 9992", one=True)
        self.assertIsNotNone(rcpt2)
        self.assertEqual(rcpt2['subscription_type'], 'Other Income')
        self.assertEqual(rcpt2['member_name'], 'WB Transport Fleet (Delivery Bay)')
        self.assertEqual(rcpt2['flat_no'], 'OTHER')
        self.assertEqual(float(rcpt2['amount']), 1500.00)

        # Verify HTML view
        resp_view2 = self.client.get('/receipts/9992')
        self.assertEqual(resp_view2.status_code, 200)
        view_html2 = resp_view2.data.decode('utf-8')
        self.assertIn('WB Transport Fleet (Delivery Bay)', view_html2)
        self.assertIn('OTHER', view_html2)
        self.assertNotIn('Flat OTHER', view_html2)  # Clean display without redundant "Flat"

        # Clean up
        execute_db("DELETE FROM tbl_receipts WHERE receipt_no IN (9991, 9992)")
        print("[OK] Other Income receipts with Other Person details successfully issued, saved in DB, and rendered in receipt view.")

    def test_07_edit_receipt_change_member_name(self):
        """Verify editing receipt details allows changing member name and persists in DB, API, and view"""
        from database import query_db, execute_db

        # 1. Check template elements
        resp_admin = self.client.get('/admin/receipts')
        self.assertEqual(resp_admin.status_code, 200)
        admin_html = resp_admin.data.decode('utf-8')
        self.assertIn('id="edit_member_name"', admin_html)
        self.assertIn('function resetEditMemberToRegisteredOwner(', admin_html)

        # 2. Insert temporary receipt #9993
        execute_db("DELETE FROM tbl_receipts WHERE receipt_no = 9993")
        execute_db(
            """INSERT INTO tbl_receipts (receipt_no, flat_no, member_name, amount, pymnt_mode, subscription_type, remarks, payment_date, receipt_date, coverage_start, coverage_end)
               VALUES (9993, 'A/1-A', 'Original Payer Name', 2000.00, 'Online', 'Monthly Subscription', 'Aug 2026', '2026-08-10', '2026-08-10', '2026-08-01', '2026-08-31')"""
        )

        # 3. Check receipt view template contains editable member name
        resp_view_initial = self.client.get('/receipts/9993')
        self.assertEqual(resp_view_initial.status_code, 200)
        view_html_initial = resp_view_initial.data.decode('utf-8')
        self.assertIn('id="view_edit_member_name"', view_html_initial)
        self.assertIn('Original Payer Name', view_html_initial)

        # 4. Perform Edit POST with modified member_name
        edit_data = {
            'member_name': 'Dr. S. Mukherjee (Tenant Representative)',
            'payment_date': '2026-08-12',
            'receipt_date': '2026-08-12',
            'amount': '2000.00',
            'pymnt_mode': 'Online',
            'subscription_type': 'Monthly Subscription',
            'remarks': 'Aug 2026 Maintenance (Adjusted)'
        }
        edit_resp = self.client.post('/admin/receipts/9993/edit', data=edit_data, follow_redirects=True)
        self.assertEqual(edit_resp.status_code, 200)

        # 5. Verify database record
        rcpt_updated = query_db("SELECT * FROM tbl_receipts WHERE receipt_no = 9993", one=True)
        self.assertIsNotNone(rcpt_updated)
        self.assertEqual(rcpt_updated['member_name'], 'Dr. S. Mukherjee (Tenant Representative)')
        self.assertEqual(rcpt_updated['remarks'], 'Aug 2026 Maintenance (Adjusted)')

        # 6. Verify receipt view reflects updated member name
        resp_view_updated = self.client.get('/receipts/9993')
        self.assertEqual(resp_view_updated.status_code, 200)
        view_html_updated = resp_view_updated.data.decode('utf-8')
        self.assertIn('Dr. S. Mukherjee (Tenant Representative)', view_html_updated)

        # 7. Verify API returns updated member name
        resp_api = self.client.get('/api/receipts/9993')
        self.assertEqual(resp_api.status_code, 200)
        api_data = resp_api.get_json()
        self.assertTrue(api_data['success'])
        self.assertEqual(api_data['receipt']['member_name'], 'Dr. S. Mukherjee (Tenant Representative)')

        # Clean up
        execute_db("DELETE FROM tbl_receipts WHERE receipt_no = 9993")
        print("[OK] Editing receipt member name successfully verified across UI, DB, API, and View voucher.")

if __name__ == '__main__':
    unittest.main()
