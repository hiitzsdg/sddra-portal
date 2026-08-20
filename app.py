import os
import re
import calendar
import traceback
from functools import wraps
from datetime import datetime, date
from decimal import Decimal
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, abort
from config import Config
from database import init_db, query_db, execute_db, verify_password, hash_password
from email_service import send_receipt_email

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
template_dir = os.path.join(BASE_DIR, 'templates')
if not os.path.exists(template_dir):
    template_dir = os.path.join(os.getcwd(), 'templates')

static_dir = os.path.join(BASE_DIR, 'static')
if not os.path.exists(static_dir):
    static_dir = os.path.join(os.getcwd(), 'static')

app = Flask(
    __name__,
    template_folder=template_dir,
    static_folder=static_dir,
    static_url_path='/static'
)
app.config.from_object(Config)

@app.after_request
def set_response_headers(response):
    if request.path.startswith('/static/'):
        response.headers['Cache-Control'] = 'public, max-age=31536000'
    return response

# Ensure database tables and initial hashes exist non-destructively
try:
    init_db()
except Exception as _e:
    pass

# Administrative & Privileged Roles
ADMIN_ROLES = {'super_admin', 'billing_admin', 'president', 'secretary', 'treasurer', 'caretaker'}
EXECUTIVE_ROLES = {'super_admin', 'billing_admin', 'president', 'secretary', 'treasurer'}

@app.context_processor
def inject_globals():
    user = session.get('user')
    if not isinstance(user, dict):
        user = None
    is_admin = bool(user and (user.get('role') in ADMIN_ROLES or user.get('is_admin', False)))
    is_exec = bool(user and (user.get('role') in EXECUTIVE_ROLES or user.get('is_admin', False)))
    return {
        'config': Config,
        'now': datetime.now(),
        'current_user': user,
        'is_admin': is_admin,
        'is_executive': is_exec,
        'asset_version': '2.1.2'
    }

# --- Defensive Decorators ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = session.get('user')
        if not user or not isinstance(user, dict) or 'role' not in user:
            session.pop('user', None)
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def roles_required(*allowed_roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user = session.get('user')
            if not user or not isinstance(user, dict):
                session.pop('user', None)
                flash('Please log in to continue.', 'warning')
                return redirect(url_for('login', next=request.url))
            user_role = user.get('role', 'MEMBER')
            is_admin = user.get('is_admin', False)
            if user_role not in allowed_roles and not is_admin:
                flash('Access Denied: You do not have permission to view this resource.', 'danger')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# --- Error Handlers ---
@app.errorhandler(500)
def internal_server_error(e):
    app.logger.error(f"Internal Server Error: {e}\n{traceback.format_exc()}")
    # Clear invalid session if it caused the issue
    return render_template('error.html', error=e, code=500), 500

@app.errorhandler(404)
def page_not_found(e):
    return render_template('error.html', error=e, code=404), 404

# --- Authentication Routes ---
@app.route('/')
def index():
    if session.get('user'):
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    # If already logged in and session is valid, redirect to dashboard
    if session.get('user') and isinstance(session.get('user'), dict) and 'role' in session['user']:
        return redirect(url_for('dashboard'))

    # Quick demo login parameter handler
    demo_user = request.args.get('demo')
    if demo_user:
        try:
            # 1. Check if demo is an admin username
            admin = query_db("SELECT * FROM tbl_admins WHERE username = %s", (demo_user,), one=True)
            if admin:
                session['user'] = {
                    'id': admin['admin_id'],
                    'username': admin['username'],
                    'name': f"{admin['username'].title()} ({admin['role']})",
                    'role': admin['role'],
                    'is_admin': True,
                    'flat_no': 'Office'
                }
                flash(f"Welcome back, {admin['username']} ({admin['role']})!", 'success')
                return redirect(url_for('dashboard'))
                
            # 2. Check if demo matches a flat_no in tbl_membership
            member = query_db("SELECT * FROM tbl_membership WHERE flat_no = %s OR id = %s", (demo_user, demo_user), one=True)
            if member:
                contact = query_db("SELECT * FROM tbl_mbr_cntct WHERE flat_no = %s", (member['flat_no'],), one=True)
                session['user'] = {
                    'id': member['id'],
                    'username': member['flat_no'],
                    'name': member['member_name'],
                    'flat_no': member['flat_no'],
                    'role': 'MEMBER',
                    'is_admin': False,
                    'email': contact.get('email_1') if contact else None,
                    'phone': contact.get('mobile_num_1') if contact else None,
                    'monthly_charge': member.get('monthly_charge', 0),
                    'sq_feet': member.get('RvsdFlatSize')
                }
                flash(f"Welcome back, {member['member_name']} (Flat {member['flat_no']})!", 'success')
                return redirect(url_for('dashboard'))
        except Exception as e:
            flash(f"Demo login note: {e}", 'warning')

    if request.method == 'POST':
        raw_login = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        if not raw_login or not password:
            flash('Please enter both your Flat Number or Username and Password.', 'danger')
            return render_template('login.html')

        try:
            # 1. Check tbl_admins first (by username)
            admin = query_db("SELECT * FROM tbl_admins WHERE LOWER(username) = LOWER(%s)", (raw_login,), one=True)
            if admin and verify_password(password, admin.get('password_hash', '')):
                session['user'] = {
                    'id': admin['admin_id'],
                    'username': admin['username'],
                    'name': f"{admin['username'].title()}",
                    'role': admin.get('role', 'super_admin'),
                    'is_admin': True,
                    'flat_no': 'Office'
                }
                flash(f"Login successful! Welcome, {admin['username']}.", 'success')
                next_p = request.args.get('next')
                return redirect(next_p or url_for('dashboard'))

            # 2. Check tbl_membership with flexible normalization
            # Variants: e.g. "A/4-C", "a/4-c", "A-4-C", "A4C", "a4c"
            clean_input = raw_login.upper()
            variants = [
                raw_login,
                clean_input,
                clean_input.replace('-', '/'),
                clean_input.replace('_', '/'),
                clean_input.replace(' ', ''),
            ]
            
            # Extract pattern like "A4C" -> "A/4-C"
            m_match = re.match(r'^([A-Z])[\/-]?([0-9]|GR)[\/-]?([A-Z])$', clean_input)
            if m_match:
                blk, flr, unt = m_match.groups()
                variants.append(f"{blk}/{flr}-{unt}")
                variants.append(f"{blk}/{flr}{unt}")
            
            # Remove duplicates
            variants = list(dict.fromkeys(variants))
            
            # Query members by any of the flat variants or email or mobile number
            placeholders = ", ".join(["%s"] * len(variants))
            member = query_db(
                f"""SELECT m.*, c.email_1, c.email_2, c.mobile_num_1 
                    FROM tbl_membership m
                    LEFT JOIN tbl_mbr_cntct c ON m.flat_no = c.flat_no
                    WHERE m.flat_no IN ({placeholders}) 
                       OR c.email_1 = %s 
                       OR c.email_2 = %s 
                       OR c.mobile_num_1 = %s 
                       OR c.mobile_num_2 = %s 
                    LIMIT 1""",
                (*variants, raw_login, raw_login, raw_login, raw_login),
                one=True
            )

            if member and verify_password(password, member.get('password_hash', '')):
                session['user'] = {
                    'id': member['id'],
                    'username': member['flat_no'],
                    'name': member['member_name'],
                    'flat_no': member['flat_no'],
                    'role': 'MEMBER',
                    'is_admin': False,
                    'email': member.get('email_1'),
                    'phone': member.get('mobile_num_1'),
                    'monthly_charge': member.get('monthly_charge', 0),
                    'sq_feet': member.get('RvsdFlatSize')
                }
                flash(f"Welcome, {member['member_name']} (Flat {member['flat_no']})!", 'success')
                next_p = request.args.get('next')
                return redirect(next_p or url_for('dashboard'))
            else:
                flash('Invalid credentials. Please verify your Flat Number (e.g. A/4-C) and password (default: sdera@123).', 'danger')
        except Exception as e:
            flash(f"Database login error: {e}", 'danger')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('login'))

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    user = session.get('user', {})
    flat_no = user.get('flat_no', '')
    is_admin = bool(user.get('is_admin', False))
    
    member = query_db("SELECT * FROM tbl_membership WHERE flat_no = %s", (flat_no,), one=True) if flat_no else None
    contact = query_db("SELECT * FROM tbl_mbr_cntct WHERE flat_no = %s", (flat_no,), one=True) if flat_no else None
    admin = query_db("SELECT * FROM tbl_admins WHERE username = %s", (user.get('username'),), one=True) if is_admin else None

    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'update_info' and not is_admin:
            email1 = request.form.get('email', '').strip()
            phone1 = request.form.get('phone', '').strip()
            
            if contact:
                execute_db("UPDATE tbl_mbr_cntct SET email_1 = %s, mobile_num_1 = %s WHERE flat_no = %s", (email1, phone1, flat_no))
            else:
                execute_db("INSERT INTO tbl_mbr_cntct (flat_no, email_1, mobile_num_1) VALUES (%s, %s, %s)", (flat_no, email1, phone1))
                
            session['user']['email'] = email1
            session['user']['phone'] = phone1
            flash('Contact details updated successfully.', 'success')
            return redirect(url_for('profile'))
            
        elif action == 'change_password':
            current_pwd = request.form.get('current_password', '')
            new_pwd = request.form.get('new_password', '')
            confirm_pwd = request.form.get('confirm_password', '')
            
            current_hash = admin['password_hash'] if is_admin else (member.get('password_hash') if member else None)
            
            if not verify_password(current_pwd, current_hash):
                flash('Current password does not match.', 'danger')
            elif len(new_pwd) < 6:
                flash('New password must be at least 6 characters.', 'danger')
            elif new_pwd != confirm_pwd:
                flash('New password confirmation does not match.', 'danger')
            else:
                new_h = hash_password(new_pwd)
                if is_admin:
                    execute_db("UPDATE tbl_admins SET password_hash = %s WHERE username = %s", (new_h, user['username']))
                else:
                    execute_db("UPDATE tbl_membership SET password_hash = %s WHERE flat_no = %s", (new_h, flat_no))
                flash('Password updated successfully!', 'success')
                return redirect(url_for('profile'))

    penalty_info = calculate_flat_penalty(flat_no, member=member) if flat_no else None
    return render_template('profile.html', member=member or user, contact=contact, penalty_info=penalty_info)

# --- Dashboard ---
@app.route('/dashboard')
@login_required
def dashboard():
    user = session.get('user', {})
    is_admin = bool(user.get('is_admin') or user.get('role') in ADMIN_ROLES)
    
    if is_admin:
        total_collected_row = query_db("SELECT COALESCE(SUM(amount), 0) as total, COUNT(*) as count FROM tbl_receipts", one=True)
        total_collected = float(total_collected_row['total']) if total_collected_row else 0.0
        total_receipts_count = total_collected_row['count'] if total_collected_row else 0
        
        total_expenses_row = query_db("SELECT COALESCE(SUM(amount), 0) as total, COUNT(*) as count FROM tbl_expenses", one=True)
        total_expenses = float(total_expenses_row['total']) if total_expenses_row else 0.0
        total_vouchers_count = total_expenses_row['count'] if total_expenses_row else 0
        
        total_members_row = query_db("SELECT COUNT(*) as count FROM tbl_membership", one=True)
        total_members = total_members_row['count'] if total_members_row else 0
        
        # Calculate Defaulters & Penalty Overview KPIs
        members_all = query_db("SELECT flat_no, monthly_charge, member_name FROM tbl_membership")
        defaulters_total_count = 0
        total_penalty_accumulated = 0.0
        total_maintenance_overdue = 0.0
        for m_row in members_all:
            p_calc = calculate_flat_penalty(m_row['flat_no'], member=m_row)
            if p_calc['overdue_months'] > 0:
                defaulters_total_count += 1
                total_maintenance_overdue += p_calc['base_due']
                total_penalty_accumulated += p_calc['penalty_amount']

        search_q = request.args.get('q', '').strip()
        rcpt_query = "SELECT * FROM tbl_receipts"
        rcpt_params = []
        if search_q:
            rcpt_query += " WHERE flat_no LIKE %s OR member_name LIKE %s OR remarks LIKE %s OR receipt_no = %s"
            rcpt_params.extend([f"%{search_q}%", f"%{search_q}%", f"%{search_q}%", search_q if search_q.isdigit() else 0])
        rcpt_query += " ORDER BY receipt_no DESC"
        recent_receipts = query_db(rcpt_query, rcpt_params)
        recent_expenses = query_db("SELECT * FROM tbl_expenses ORDER BY voucher_no DESC")
        
        return render_template(
            'dashboard.html',
            is_admin=True,
            total_members=total_members,
            total_collected=total_collected,
            total_receipts_count=total_receipts_count,
            total_expenses=total_expenses,
            total_vouchers_count=total_vouchers_count,
            net_balance=total_collected - total_expenses,
            defaulters_total_count=defaulters_total_count,
            total_penalty_accumulated=total_penalty_accumulated,
            total_maintenance_overdue=total_maintenance_overdue,
            recent_receipts=recent_receipts,
            recent_expenses=recent_expenses,
            search_q=search_q,
            current_year=2026
        )
    else:
        flat_no = user.get('flat_no', '')
        my_receipts = query_db(
            "SELECT * FROM tbl_receipts WHERE flat_no = %s ORDER BY receipt_no DESC", 
            (flat_no,)
        )
        
        total_paid_row = query_db(
            "SELECT COALESCE(SUM(amount), 0) as total FROM tbl_receipts WHERE flat_no = %s",
            (flat_no,),
            one=True
        )
        total_paid = float(total_paid_row['total']) if total_paid_row else 0.0
        
        member = query_db("SELECT * FROM tbl_membership WHERE flat_no = %s", (flat_no,), one=True)
        my_penalty = calculate_flat_penalty(flat_no, member=member)
        
        total_expenses_row = query_db("SELECT COALESCE(SUM(amount), 0) as total FROM tbl_expenses", one=True)
        total_expenses = float(total_expenses_row['total']) if total_expenses_row else 0.0
        recent_expenses = query_db("SELECT * FROM tbl_expenses ORDER BY voucher_no DESC LIMIT 5")

        return render_template(
            'dashboard.html',
            is_admin=False,
            member=member,
            my_receipts=my_receipts,
            total_paid=total_paid,
            outstanding=my_penalty['base_due'],
            my_penalty=my_penalty,
            total_expenses=total_expenses,
            recent_expenses=recent_expenses,
            current_year=2026
        )

# --- Receipt View & Email Dispatch ---
@app.route('/receipts/<int:receipt_no>')
@login_required
def view_receipt(receipt_no):
    user = session.get('user', {})
    is_admin = bool(user.get('is_admin') or user.get('role') in ADMIN_ROLES)
    
    receipt = query_db("SELECT * FROM tbl_receipts WHERE receipt_no = %s", (receipt_no,), one=True)
    if not receipt:
        abort(404, description="Receipt not found")
        
    if not is_admin and receipt.get('flat_no') != user.get('flat_no'):
        flash('Access Denied: You are not authorized to view another resident\'s receipt.', 'danger')
        return redirect(url_for('dashboard'))
        
    member_info = query_db("SELECT * FROM tbl_membership WHERE flat_no = %s", (receipt['flat_no'],), one=True)
    contact_info = query_db("SELECT * FROM tbl_mbr_cntct WHERE flat_no = %s", (receipt['flat_no'],), one=True)
    
    return render_template('receipt_view.html', receipt=receipt, member=member_info or {}, contact=contact_info or {})

@app.route('/receipts/<int:receipt_no>/email', methods=['POST'])
@login_required
def email_receipt(receipt_no):
    user = session.get('user', {})
    is_admin = bool(user.get('is_admin') or user.get('role') in ADMIN_ROLES)
    is_ajax = bool(
        request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 
        request.is_json or 
        'application/json' in request.headers.get('Accept', '')
    )
    
    receipt = query_db("SELECT * FROM tbl_receipts WHERE receipt_no = %s", (receipt_no,), one=True)
    if not receipt:
        if is_ajax:
            return jsonify({"success": False, "message": f"Receipt #{receipt_no} not found."}), 404
        flash(f"Receipt #{receipt_no} not found.", 'danger')
        return redirect(url_for('dashboard'))
        
    if not is_admin and str(receipt.get('flat_no')).strip().lower() != str(user.get('flat_no')).strip().lower():
        if is_ajax:
            return jsonify({"success": False, "message": "Access Denied: You cannot dispatch another resident's receipt."}), 403
        flash("Access Denied: You cannot dispatch another resident's receipt.", 'danger')
        return redirect(url_for('dashboard'))
        
    custom_email = None
    if request.is_json:
        custom_email = (request.get_json(silent=True) or {}).get('email')
    if not custom_email:
        custom_email = request.form.get('email')
        
    try:
        result = send_receipt_email(receipt_no, custom_recipient=custom_email)
    except Exception as e:
        result = {"success": False, "message": f"Dispatch error: {str(e)}"}
        
    if is_ajax:
        return jsonify(result), (200 if result.get('success') else 400)
        
    if result.get('success'):
        flash(result['message'], 'success')
    else:
        flash(result['message'], 'danger')
    return redirect(request.referrer or url_for('view_receipt', receipt_no=receipt_no))

# --- Association Expenses ---
@app.route('/expenses')
@login_required
def expenses_list():
    particulars_filter = request.args.get('particulars', '').strip()
    spl_head_filter = request.args.get('spl_head', '').strip()
    search_q = request.args.get('q', '').strip()
    
    query = "SELECT * FROM tbl_expenses WHERE 1=1"
    params = []
    
    if particulars_filter:
        query += " AND particulars = %s"
        params.append(particulars_filter)
    if spl_head_filter:
        query += " AND spl_head = %s"
        params.append(spl_head_filter)
    if search_q:
        query += " AND (expense_description LIKE %s OR particulars LIKE %s OR spl_head LIKE %s OR voucher_no = %s)"
        params.extend([f"%{search_q}%", f"%{search_q}%", f"%{search_q}%", search_q if search_q.isdigit() else 0])
        
    query += " ORDER BY voucher_no DESC"
    
    expenses = query_db(query, params)
    
    particulars_list = query_db("""
        SELECT DISTINCT particulars, COUNT(*) as cnt, SUM(amount) as total 
        FROM tbl_expenses 
        WHERE particulars IS NOT NULL AND TRIM(particulars) != '' 
        GROUP BY particulars 
        ORDER BY particulars ASC
    """)
    spl_heads_list = query_db("""
        SELECT DISTINCT spl_head, COUNT(*) as cnt, SUM(amount) as total 
        FROM tbl_expenses 
        WHERE spl_head IS NOT NULL AND TRIM(spl_head) != '' 
        GROUP BY spl_head 
        ORDER BY spl_head ASC
    """)
    
    total_incurred_row = query_db("SELECT COALESCE(SUM(amount), 0) as total FROM tbl_expenses", one=True)
    total_incurred = float(total_incurred_row['total']) if total_incurred_row else 0.0
    
    return render_template(
        'expenses.html',
        expenses=expenses,
        particulars_list=particulars_list,
        spl_heads_list=spl_heads_list,
        total_incurred=total_incurred,
        current_particulars=particulars_filter,
        current_spl_head=spl_head_filter,
        search_q=search_q
    )

@app.route('/admin/expenses/new', methods=['POST'])
@roles_required('super_admin', 'billing_admin', 'president', 'secretary', 'treasurer')
def add_expense():
    voucher_date = request.form.get('voucher_date', str(date.today()))
    expense_description = request.form.get('expense_description', '').strip()
    particulars = request.form.get('particulars', 'Misc & Other Expenses').strip()
    spl_head = request.form.get('spl_head', '').strip()
    payment_by = request.form.get('payment_by', 'Cash')
    amount = request.form.get('amount', '0').strip()
    
    if not expense_description or not amount:
        flash('Description and Amount are required.', 'danger')
        return redirect(url_for('expenses_list'))
        
    try:
        execute_db(
            """INSERT INTO tbl_expenses (voucher_date, expense_description, particulars, spl_head, payment_by, amount)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (voucher_date, expense_description, particulars, spl_head, payment_by, float(amount))
        )
        flash(f"Expense voucher for INR {float(amount):,.2f} recorded successfully.", 'success')
    except Exception as e:
        flash(f"Error adding expense: {e}", 'danger')
        
    return redirect(url_for('expenses_list'))

@app.route('/admin/expenses/<int:voucher_no>/delete', methods=['POST'])
@roles_required('super_admin', 'billing_admin', 'president', 'secretary', 'treasurer')
def delete_expense(voucher_no):
    execute_db("DELETE FROM tbl_expenses WHERE voucher_no = %s", (voucher_no,))
    flash(f"Voucher #{voucher_no} deleted.", 'info')
    return redirect(url_for('expenses_list'))

# --- Administrative: Receipts Ledger ---
@app.route('/admin/receipts')
@roles_required('super_admin', 'billing_admin', 'president', 'secretary', 'treasurer', 'caretaker')
def admin_receipts():
    flat_filter = request.args.get('flat', '').strip()
    month_filter = request.args.get('month', '').strip()
    search_q = request.args.get('q', '').strip()
    
    query = "SELECT * FROM tbl_receipts WHERE 1=1"
    params = []
    
    if flat_filter:
        query += " AND flat_no = %s"
        params.append(flat_filter)
    if month_filter:
        query += " AND remarks LIKE %s"
        params.append(f"%{month_filter}%")
    if search_q:
        query += " AND (flat_no LIKE %s OR member_name LIKE %s OR remarks LIKE %s OR receipt_no = %s)"
        params.extend([f"%{search_q}%", f"%{search_q}%", f"%{search_q}%", search_q if search_q.isdigit() else 0])
        
    query += " ORDER BY receipt_no DESC"
    
    receipts = query_db(query, params)
    all_flats = query_db("SELECT flat_no, member_name FROM tbl_membership ORDER BY flat_no")
    
    return render_template(
        'admin_receipts.html',
        receipts=receipts,
        all_flats=all_flats,
        flat_filter=flat_filter,
        month_filter=month_filter,
        search_q=search_q
    )

@app.route('/admin/receipts/new', methods=['POST'])
@roles_required('super_admin', 'billing_admin', 'president', 'secretary', 'treasurer', 'caretaker')
def create_receipt():
    flat_no = request.form.get('flat_no', '').strip()
    amount = request.form.get('amount', '0').strip()
    pymnt_mode = request.form.get('pymnt_mode', 'Online')
    subscription_type = request.form.get('subscription_type', 'Monthly Subscription')
    remarks = request.form.get('remarks', "Aug'2026").strip()
    payment_date = request.form.get('payment_date', str(date.today()))
    receipt_date = request.form.get('receipt_date', str(date.today()))
    coverage_start = request.form.get('coverage_start') or payment_date
    coverage_end = request.form.get('coverage_end') or payment_date
    auto_email = request.form.get('auto_email') == '1'
    
    member = query_db("SELECT member_name FROM tbl_membership WHERE flat_no = %s", (flat_no,), one=True)
    member_name = member['member_name'] if member else 'Resident'
    
    try:
        receipt_no = execute_db(
            """INSERT INTO tbl_receipts (flat_no, member_name, amount, pymnt_mode, subscription_type, remarks, payment_date, receipt_date, coverage_start, coverage_end)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (flat_no, member_name, float(amount), pymnt_mode, subscription_type, remarks, payment_date, receipt_date, coverage_start, coverage_end)
        )
        flash(f"Receipt #{receipt_no} generated successfully for Flat {flat_no} ({member_name})!", 'success')
        
        if auto_email:
            send_res = send_receipt_email(receipt_no)
            if send_res['success']:
                flash("Receipt emailed to resident.", 'info')
    except Exception as e:
        flash(f"Error creating receipt: {e}", 'danger')
        
    return redirect(url_for('admin_receipts'))

# --- Administrative: Resident Directory ---
@app.route('/admin/members')
@roles_required('super_admin', 'billing_admin', 'president', 'secretary', 'treasurer', 'caretaker')
def admin_members():
    search_q = request.args.get('q', '').strip()
    
    query = """
        SELECT m.*, 
               c.mobile_num_1, c.mobile_num_2, c.email_1, c.email_2,
               COALESCE(SUM(r.amount), 0) as total_paid,
               COUNT(r.receipt_no) as receipts_count,
               MAX(r.payment_date) as last_payment_date
        FROM tbl_membership m
        LEFT JOIN tbl_mbr_cntct c ON m.flat_no = c.flat_no
        LEFT JOIN tbl_receipts r ON m.flat_no = r.flat_no
    """
    params = []
    if search_q:
        query += " WHERE m.flat_no LIKE %s OR m.member_name LIKE %s OR c.mobile_num_1 LIKE %s OR c.email_1 LIKE %s"
        params.extend([f"%{search_q}%", f"%{search_q}%", f"%{search_q}%", f"%{search_q}%"])
        
    query += " GROUP BY m.id ORDER BY m.flat_no"
    members = query_db(query, params)
    
    return render_template('admin_members.html', members=members, search_q=search_q)

@app.route('/api/member-receipts')
@app.route('/api/members/<path:flat_no>/receipts')
@roles_required('super_admin', 'billing_admin', 'president', 'secretary', 'treasurer', 'caretaker')
def api_member_receipts(flat_no=None):
    if not flat_no:
        flat_no = request.args.get('flat', '').strip()
    receipts = query_db("SELECT * FROM tbl_receipts WHERE flat_no = %s ORDER BY receipt_no DESC", (flat_no,))
    member = query_db("SELECT * FROM tbl_membership WHERE flat_no = %s", (flat_no,), one=True)
    contact = query_db("SELECT * FROM tbl_mbr_cntct WHERE flat_no = %s", (flat_no,), one=True)
    return jsonify({
        "success": True,
        "flat_no": flat_no,
        "member_name": member['member_name'] if member else 'Resident',
        "monthly_charge": float(member.get('monthly_charge', 0) if member else 0),
        "total_paid": sum(float(r['amount'] or 0) for r in receipts),
        "receipts_count": len(receipts),
        "email": (contact.get('email_1') or contact.get('email_2')) if contact else None,
        "phone": (contact.get('mobile_num_1') or contact.get('mobile_num_2')) if contact else None,
        "receipts": receipts
    })

# ================= Overdue Maintenance & Cumulative Penalty Engine =================
def calculate_flat_penalty(flat_no, member=None, target_date=None):
    """
    Calculate overdue months N and cumulative penalty using official formula:
    Penalty = (N * (N + 1) / 2) * 100
    where N = number of months maintenance is due from coverage end date.
    """
    if not target_date:
        target_date = datetime.now().date()
    elif isinstance(target_date, str):
        try:
            target_date = datetime.strptime(target_date[:10], '%Y-%m-%d').date()
        except Exception:
            target_date = datetime.now().date()

    if not member:
        member = query_db("SELECT * FROM tbl_membership WHERE flat_no = %s", (flat_no,), one=True)

    monthly_charge = float(member.get('monthly_charge', 0) if member else 0)
    member_name = member.get('member_name', 'Resident') if member else 'Resident'
    flat_size = member.get('RvsdFlatSize') if member else None

    # Retrieve all valid coverage end dates for this flat
    rcpt_rows = query_db(
        """SELECT coverage_end, payment_date, remarks, subscription_type 
           FROM tbl_receipts 
           WHERE flat_no = %s""",
        (flat_no,)
    )

    valid_coverage_dates = []
    month_lookup = {
        'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
        'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
    }

    for r in (rcpt_rows or []):
        cov = r.get('coverage_end')
        if cov:
            if isinstance(cov, str) and cov.strip().lower() not in ('none', 'null', ''):
                try:
                    d = datetime.strptime(cov.strip()[:10], '%Y-%m-%d').date()
                    valid_coverage_dates.append(d)
                except Exception:
                    pass
            elif hasattr(cov, 'year'):
                d = cov if not hasattr(cov, 'date') else cov.date()
                valid_coverage_dates.append(d)

        # Fallback/Supplemental: inspect remarks for coverage text like "May'2026 to Sep'2026" or "Sep'2026"
        sub_type = str(r.get('subscription_type', '')).lower()
        if 'monthly' in sub_type or 'subscription' in sub_type:
            rem = str(r.get('remarks', ''))
            matches = re.findall(r'([A-Za-z]{3,9})[\'\"\s\-_]*(\d{4})', rem)
            for m_name, y_str in matches:
                m_prefix = m_name[:3].lower()
                if m_prefix in month_lookup:
                    m_val = month_lookup[m_prefix]
                    y_val = int(y_str)
                    last_day = 31 if m_val in (1,3,5,7,8,10,12) else (28 if m_val == 2 else 30)
                    try:
                        valid_coverage_dates.append(datetime(y_val, m_val, last_day).date())
                    except Exception:
                        pass

    latest_cov = max(valid_coverage_dates) if valid_coverage_dates else None

    if not latest_cov:
        # Default association billing epoch start: April 2026 (covered through March 2026)
        cov_year = 2026
        cov_month = 3
        coverage_display = "No Receipts (Due from Apr'2026)"
        last_covered_text = "None"
    else:
        cov_year = latest_cov.year
        cov_month = latest_cov.month
        coverage_display = latest_cov.strftime("%b'%Y")
        last_covered_text = latest_cov.strftime("%B %Y")

    # Count overdue months N that have passed their respective due dates (last calendar day of each month)
    # Start iterating from the month immediately following latest_cov up to target_date
    overdue_months = 0
    cur_y = cov_year
    cur_m = cov_month + 1
    if cur_m > 12:
        cur_y += 1
        cur_m = 1

    while True:
        # If candidate unpaid month is beyond target_date's year and month, stop
        if (cur_y > target_date.year) or (cur_y == target_date.year and cur_m > target_date.month):
            break
        
        # Last day of this candidate unpaid month (e.g. Aug 31, Sep 30, Feb 28/29)
        _, last_day = calendar.monthrange(cur_y, cur_m)
        due_date = date(cur_y, cur_m, last_day)
        
        # A month is strictly overdue only if target_date has passed its monthly due date
        # (e.g. August 2026 maintenance is due on 31st August 2026, so no penalty is levied on or before 31st August)
        if target_date > due_date:
            overdue_months += 1

        # Advance to next month
        cur_m += 1
        if cur_m > 12:
            cur_y += 1
            cur_m = 1

    # Formula: N * (N + 1) / 2 * 100
    if overdue_months > 0:
        penalty_amount = (overdue_months * (overdue_months + 1) // 2) * 100
        base_due = overdue_months * monthly_charge
    else:
        penalty_amount = 0
        base_due = 0.0

    total_due = base_due + penalty_amount

    # Month-by-month penalty ladder calculation for transparency
    penalty_ladder = []
    cum_pen = 0
    for m in range(1, overdue_months + 1):
        m_pen = m * 100
        cum_pen += m_pen
        penalty_ladder.append({
            'month_index': m,
            'month_penalty': m_pen,
            'cumulative_penalty': cum_pen
        })

    return {
        'flat_no': flat_no,
        'member_name': member_name,
        'flat_size': flat_size,
        'monthly_charge': monthly_charge,
        'coverage_end': latest_cov.strftime('%Y-%m-%d') if latest_cov else None,
        'coverage_display': coverage_display,
        'last_covered_text': last_covered_text,
        'as_of_date': target_date.strftime('%Y-%m-%d'),
        'as_of_display': target_date.strftime("%b'%Y"),
        'as_of_full': target_date.strftime("%B %d, %Y"),
        'overdue_months': overdue_months,
        'base_due': base_due,
        'penalty_amount': penalty_amount,
        'total_due': total_due,
        'is_overdue': overdue_months > 0,
        'penalty_ladder': penalty_ladder,
        'status': 'Paid Up / Advance' if overdue_months == 0 else (
            '1 Month Due (₹100)' if overdue_months == 1 else f'{overdue_months} Months Overdue (Penalty ₹{penalty_amount:,})'
        )
    }

@app.route('/admin/penalties')
@roles_required('super_admin', 'billing_admin', 'president', 'secretary', 'treasurer', 'caretaker')
def admin_penalties():
    members = query_db("SELECT * FROM tbl_membership ORDER BY flat_no")
    target_date_str = request.args.get('as_of', '').strip()
    search_q = request.args.get('q', '').strip()
    status_filter = request.args.get('status', 'all').strip()

    target_date = None
    if target_date_str:
        try:
            target_date = datetime.strptime(target_date_str, '%Y-%m-%d').date()
        except Exception:
            target_date = None

    if not target_date:
        target_date = datetime.now().date()

    roster = []
    total_base_due = 0.0
    total_penalty_due = 0.0
    total_gross_due = 0.0
    defaulters_count = 0
    paid_up_count = 0

    for m in members:
        calc = calculate_flat_penalty(m['flat_no'], member=m, target_date=target_date)
        
        # Apply search filter
        if search_q:
            sq = search_q.lower().replace('/', '').replace('-', '').replace(' ', '')
            f_norm = calc['flat_no'].lower().replace('/', '').replace('-', '').replace(' ', '')
            n_norm = calc['member_name'].lower().replace(' ', '')
            if sq not in f_norm and sq not in n_norm:
                continue

        # Apply status filter
        if status_filter == 'defaulters' and calc['overdue_months'] == 0:
            continue
        elif status_filter == 'paid_up' and calc['overdue_months'] > 0:
            continue

        roster.append(calc)

        if calc['overdue_months'] > 0:
            defaulters_count += 1
            total_base_due += calc['base_due']
            total_penalty_due += calc['penalty_amount']
            total_gross_due += calc['total_due']
        else:
            paid_up_count += 1

    return render_template(
        'admin_penalties.html',
        roster=roster,
        total_flats=len(members),
        defaulters_count=defaulters_count,
        paid_up_count=paid_up_count,
        total_base_due=total_base_due,
        total_penalty_due=total_penalty_due,
        total_gross_due=total_gross_due,
        target_date=target_date.strftime('%Y-%m-%d'),
        target_display=target_date.strftime("%B %Y"),
        search_q=search_q,
        status_filter=status_filter
    )

@app.route('/api/penalties/calculate')
@login_required
def api_calculate_penalty():
    flat_no = request.args.get('flat', '').strip()
    as_of = request.args.get('as_of', '').strip()
    
    if not flat_no:
        return jsonify({'success': False, 'error': 'Missing flat number parameter'}), 400
        
    calc = calculate_flat_penalty(flat_no, target_date=as_of if as_of else None)
    return jsonify({
        'success': True,
        'data': calc
    })

# --- Chart Data API ---
@app.route('/api/expenses/chart-data')
@login_required
def chart_data():
    particulars_rows = query_db("""
        SELECT particulars, SUM(amount) as total 
        FROM tbl_expenses 
        GROUP BY particulars 
        ORDER BY total DESC 
        LIMIT 7
    """)
    
    monthly_rows = query_db("""
        SELECT DATE_FORMAT(voucher_date, '%b %Y') as ym, SUM(amount) as total 
        FROM tbl_expenses 
        GROUP BY DATE_FORMAT(voucher_date, '%b %Y'), DATE_FORMAT(voucher_date, '%Y-%m') 
        ORDER BY DATE_FORMAT(voucher_date, '%Y-%m')
    """)
    
    return jsonify({
        'categories': [{'category': r['particulars'], 'total': float(r['total'])} for r in particulars_rows],
        'monthly': [{'month': r['ym'], 'total': float(r['total'])} for r in monthly_rows]
    })

if __name__ == '__main__':
    init_db()
    print("Starting SDDRA Billing & Residents' Association Web Portal on http://127.0.0.1:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)
