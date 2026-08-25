import os
import io
import re
import zipfile
import calendar
import traceback
from functools import wraps
from datetime import datetime, date, timedelta, timezone
from decimal import Decimal
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, abort, Response
from config import Config
from database import init_db, query_db, execute_db, verify_password, hash_password, determine_engine
from email_service import send_receipt_email, broadcast_notice_email, get_notice_email_recipients
from pdf_service import (
    generate_receipt_pdf_bytes,
    generate_expense_voucher_pdf_bytes,
    generate_all_expenses_book_pdf_bytes
)
from whatsapp_service import (
    normalize_whatsapp_phone,
    build_whatsapp_url,
    format_receipt_whatsapp_message,
    format_dues_reminder_whatsapp_message,
    format_notice_whatsapp_message,
    send_whatsapp_message,
    get_whatsapp_committee_contacts,
    log_whatsapp_dispatch
)

# --- Standard Timezone: Indian Standard Time (IST, UTC+05:30) ---
IST = timezone(timedelta(hours=5, minutes=30))

def get_ist_now():
    """Return current datetime in Indian Standard Time (IST, UTC+05:30)."""
    return datetime.now(IST)


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
        response.headers['Cache-Control'] = 'public, max-age=0, must-revalidate'
    return response

@app.teardown_appcontext
def close_request_db(exception=None):
    # Keep persistent MySQL/SQLite connections warm across requests for ultra-low latency
    pass

# Ensure database tables and initial hashes exist non-destructively
try:
    init_db()
except Exception as _e:
    pass

# Administrative & Privileged Roles
ADMIN_ROLES = {'super_admin', 'billing_admin', 'president', 'secretary', 'treasurer', 'caretaker'}
EXECUTIVE_ROLES = {'super_admin', 'billing_admin', 'president', 'secretary', 'treasurer'}

def get_app_base_url():
    """Retrieve canonical absolute base URL, supporting Vercel HTTPS reverse proxy."""
    proto = request.headers.get('X-Forwarded-Proto', request.scheme or 'https')
    host = request.headers.get('X-Forwarded-Host', request.host)
    return f"{proto}://{host}".rstrip('/')

# --- Jinja Template Filters for Timestamps & Dates ---
def _parse_dt_safe(val):
    if not val:
        return None
    if isinstance(val, datetime):
        return val
    if isinstance(val, date):
        return datetime(val.year, val.month, val.day)
    try:
        val_str = str(val).strip().replace('T', ' ')
        val_clean = val_str.split('+')[0].split('.')[0]
        if len(val_clean) == 10:  # YYYY-MM-DD
            return datetime.strptime(val_clean, '%Y-%m-%d')
        elif len(val_clean) >= 19:  # YYYY-MM-DD HH:MM:SS
            return datetime.strptime(val_clean[:19], '%Y-%m-%d %H:%M:%S')
    except Exception:
        pass
    return None

@app.template_filter('format_audit_dt')
def format_audit_dt_filter(val):
    """Format datetime as e.g. '23 Aug 2026, 07:33:49 PM'"""
    dt = _parse_dt_safe(val)
    if not dt:
        return str(val)[:19] if val else '-'
    return dt.strftime('%d %b %Y, %I:%M:%S %p')

@app.template_filter('format_audit_date')
def format_audit_date_filter(val):
    """Format date as e.g. '23 Aug 2026'"""
    dt = _parse_dt_safe(val)
    if not dt:
        return str(val)[:10] if val else '-'
    return dt.strftime('%d %b %Y')

@app.template_filter('format_audit_time')
def format_audit_time_filter(val):
    """Format time as e.g. '07:33:49 PM'"""
    dt = _parse_dt_safe(val)
    if not dt:
        return str(val)[11:19] if val and len(str(val)) >= 19 else '-'
    return dt.strftime('%I:%M:%S %p')

@app.template_filter('time_ago')
def time_ago_filter(val):
    """Generate human-friendly relative time e.g. 'Just now', '5 mins ago', '2 hours ago', 'Yesterday'"""
    dt = _parse_dt_safe(val)
    if not dt:
        return ''
    try:
        now_dt = get_ist_now().replace(tzinfo=None)
        diff = now_dt - dt
        seconds = int(diff.total_seconds())
        if seconds < 0:
            return 'Just now'
        if seconds < 60:
            return f"{max(1, seconds)}s ago"
        minutes = seconds // 60
        if minutes < 60:
            return f"{minutes}m ago"
        hours = minutes // 60
        if hours < 24:
            return f"{hours}h ago"
        days = hours // 24
        if days == 1:
            return "Yesterday"
        if days < 30:
            return f"{days}d ago"
        months = days // 30
        if months < 12:
            return f"{months}mo ago"
        years = days // 365
        return f"{years}y ago"
    except Exception:
        return ''

@app.context_processor
def inject_globals():
    user = session.get('user')
    if not isinstance(user, dict):
        user = None
    is_admin = bool(user and (user.get('role') in ADMIN_ROLES or user.get('is_admin', False)))
    is_exec = bool(user and (user.get('role') in EXECUTIVE_ROLES or user.get('is_admin', False)))
    is_billing_admin = bool(user and (user.get('role') in {'super_admin', 'billing_admin'} or user.get('username') == 'admin'))
    return {
        'config': Config,
        'now': get_ist_now(),
        'current_user': user,
        'is_admin': is_admin,
        'is_executive': is_exec,
        'is_billing_admin': is_billing_admin,
        'committee_whatsapp_contacts': get_whatsapp_committee_contacts(),
        'asset_version': '2.2.0'
    }

# --- Activity & Audit Logging Engine ---
def log_activity(action_type, description, actor=None, ip_address=None):
    """Record an audit trail entry for member & administrator actions across the portal in IST."""
    try:
        if actor is None:
            actor = session.get('user', {})
        if not isinstance(actor, dict):
            actor = {}
            
        username = actor.get('username', 'System')
        name = actor.get('name', username)
        role = actor.get('role', 'MEMBER')
        flat_no = actor.get('flat_no', '-')
        
        if not ip_address:
            try:
                ip_address = request.headers.get('X-Forwarded-For', request.remote_addr) if request else '127.0.0.1'
                if ip_address and ',' in ip_address:
                    ip_address = ip_address.split(',')[0].strip()
            except Exception:
                ip_address = '127.0.0.1'
                
        now_dt = get_ist_now().strftime('%Y-%m-%d %H:%M:%S')
        execute_db(
            """INSERT INTO tbl_activity_logs (actor_username, actor_name, actor_role, flat_no, action_type, description, ip_address, created_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
            (username, name, role, flat_no, action_type, description, ip_address or '127.0.0.1', now_dt)
        )
    except Exception as err:
        app.logger.warning(f"Could not persist activity log: {err}")

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
            user_role = str(user.get('role', 'MEMBER')).lower()
            allowed_lowers = [str(r).lower() for r in allowed_roles]
            username = str(user.get('username', '')).lower()
            
            has_role = (
                (user_role in allowed_lowers) or 
                (user_role == 'super_admin') or
                (username == 'admin')
            )
            if not has_role:
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
            # 1. Admin accounts MUST require explicit password authentication
            admin = query_db("SELECT * FROM tbl_admins WHERE LOWER(username) = LOWER(%s)", (demo_user,), one=True)
            if admin:
                flash(f"🔒 Administrator account '{admin['username']}' requires password authentication. Please enter your password.", 'info')
                return render_template('login.html', prefill_username=admin['username'], admin_auth_prompt=True)
                
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
                admin_u = admin['username'].lower()
                officer_names = {
                    'president': 'Dr. Asit Kumar Bera',
                    'secretary': 'Mr. Somenath Halder',
                    'admin': 'Mr. Sanjoy Chakraborty',
                    'treasurer': 'Mr. Swapnadeep Ganguly',
                    'caretaker': 'Mr. Sanjoy Chakraborty'
                }
                officer_titles = {
                    'president': 'President Dr. Asit Kumar Bera',
                    'secretary': 'General Secretary Mr. Somenath Halder',
                    'admin': 'Billing Administrator Mr. Sanjoy Chakraborty',
                    'treasurer': 'Treasurer Mr. Swapnadeep Ganguly',
                    'caretaker': 'Caretaker Mr. Sanjoy Chakraborty'
                }
                officer_flats = {
                    'treasurer': 'A/4-C',
                    'president': 'A/2-A',
                    'secretary': 'A/1-C',
                    'caretaker': 'Estate Office',
                    'admin': 'Office'
                }
                admin_fno = officer_flats.get(admin_u, 'Office')
                admin_email = admin.get('email')
                admin_phone = None
                if admin_fno and admin_fno != 'Office':
                    cnt_row = query_db("SELECT email_1, email_2, mobile_num_1, mobile_num_2 FROM tbl_mbr_cntct WHERE LOWER(TRIM(flat_no)) = LOWER(TRIM(%s))", (admin_fno,), one=True)
                    if cnt_row:
                        if not admin_email:
                            admin_email = cnt_row.get('email_1') or cnt_row.get('email_2')
                        admin_phone = cnt_row.get('mobile_num_1') or cnt_row.get('mobile_num_2')

                session['user'] = {
                    'id': admin['admin_id'],
                    'username': admin['username'],
                    'name': officer_names.get(admin_u, admin['username'].title()),
                    'title': officer_titles.get(admin_u, admin['username'].title()),
                    'role': admin.get('role', 'super_admin'),
                    'is_admin': True,
                    'flat_no': admin_fno,
                    'email': admin_email,
                    'phone': admin_phone
                }
                log_activity('LOGIN', f"Administrative sign in ({officer_titles.get(admin_u, admin['username'])})", actor=session['user'])
                flash(f"Login successful! Welcome, {officer_titles.get(admin_u, admin['username'])}.", 'success')
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
                    LEFT JOIN tbl_mbr_cntct c ON LOWER(TRIM(m.flat_no)) = LOWER(TRIM(c.flat_no))
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
                cnt_row = query_db("SELECT email_1, email_2, mobile_num_1, mobile_num_2 FROM tbl_mbr_cntct WHERE LOWER(TRIM(flat_no)) = LOWER(TRIM(%s))", (member['flat_no'],), one=True)
                mbr_email = (cnt_row.get('email_1') or cnt_row.get('email_2')) if cnt_row else member.get('email_1')
                mbr_phone = (cnt_row.get('mobile_num_1') or cnt_row.get('mobile_num_2')) if cnt_row else member.get('mobile_num_1')
                
                session['user'] = {
                    'id': member['id'],
                    'username': member['flat_no'],
                    'name': member['member_name'],
                    'flat_no': member['flat_no'],
                    'role': 'MEMBER',
                    'is_admin': False,
                    'email': mbr_email,
                    'phone': mbr_phone,
                    'monthly_charge': member.get('monthly_charge', 0),
                    'sq_feet': member.get('RvsdFlatSize')
                }
                log_activity('LOGIN', f"Member signed in to resident portal from Flat {member['flat_no']}", actor=session['user'])
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
    log_activity('LOGOUT', f"User signed out from portal")
    session.clear()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('login'))

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    user = session.get('user', {})
    flat_no = user.get('flat_no', '')
    is_admin = bool(user.get('is_admin', False))
    
    member = query_db("SELECT * FROM tbl_membership WHERE LOWER(TRIM(flat_no)) = LOWER(TRIM(%s))", (flat_no,), one=True) if flat_no else None
    contact = query_db("SELECT * FROM tbl_mbr_cntct WHERE LOWER(TRIM(flat_no)) = LOWER(TRIM(%s))", (flat_no,), one=True) if flat_no else None
    admin = query_db("SELECT * FROM tbl_admins WHERE username = %s", (user.get('username'),), one=True) if is_admin else None

    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'update_info':
            email1 = request.form.get('email', '').strip()
            phone1 = request.form.get('phone', '').strip()
            
            if not email1:
                flash('Please provide a valid email address for receipt delivery.', 'danger')
                return redirect(url_for('profile'))
            
            try:
                if flat_no:
                    # Check if contact entry exists in tbl_mbr_cntct
                    cnt = query_db("SELECT flat_no FROM tbl_mbr_cntct WHERE LOWER(TRIM(flat_no)) = LOWER(TRIM(%s))", (flat_no,), one=True)
                    if cnt:
                        execute_db(
                            "UPDATE tbl_mbr_cntct SET email_1 = %s, mobile_num_1 = %s WHERE LOWER(TRIM(flat_no)) = LOWER(TRIM(%s))", 
                            (email1, phone1, flat_no)
                        )
                    else:
                        execute_db(
                            "INSERT INTO tbl_mbr_cntct (flat_no, email_1, mobile_num_1) VALUES (%s, %s, %s)", 
                            (flat_no, email1, phone1)
                        )
                    # Also keep members table in sync if it exists
                    try:
                        execute_db("UPDATE members SET email = %s, phone = %s WHERE LOWER(TRIM(flat_number)) = LOWER(TRIM(%s))", (email1, phone1, flat_no))
                    except Exception:
                        pass
                
                if is_admin and admin:
                    try:
                        execute_db("UPDATE tbl_admins SET email = %s WHERE username = %s", (email1, user.get('username')))
                    except Exception:
                        pass
                    
                if 'user' in session:
                    session['user']['email'] = email1
                    session['user']['phone'] = phone1
                    session.modified = True
                    
                log_activity('PROFILE_UPDATE', f"Updated official contact info for Flat {flat_no} (Email: {email1}, Phone: {phone1})")
                flash('Contact details updated successfully in the official registry.', 'success')
                return redirect(url_for('profile'))
            except Exception as e:
                flash(f"Could not persist contact details update: {e}", 'danger')
                return redirect(url_for('profile'))
            
        elif action == 'change_password':
            current_pwd = request.form.get('current_password', '')
            new_pwd = request.form.get('new_password', '')
            confirm_pwd = request.form.get('confirm_password', '')
            
            current_hash = (admin.get('password_hash') if (is_admin and admin) else None) or (member.get('password_hash') if member else None)
            
            if not current_hash or not verify_password(current_pwd, current_hash):
                flash('Current password does not match. Please verify your existing password.', 'danger')
            elif len(new_pwd) < 6:
                flash('New password must be at least 6 characters long.', 'danger')
            elif new_pwd != confirm_pwd:
                flash('New password and confirmation password do not match.', 'danger')
            else:
                try:
                    new_h = hash_password(new_pwd)
                    if is_admin:
                        execute_db("UPDATE tbl_admins SET password_hash = %s WHERE username = %s", (new_h, user.get('username')))
                    else:
                        execute_db("UPDATE tbl_membership SET password_hash = %s WHERE LOWER(TRIM(flat_no)) = LOWER(TRIM(%s))", (new_h, flat_no))
                    session.modified = True
                    log_activity('PASSWORD_CHANGE', f"Changed portal account security password for Flat {flat_no}")
                    flash('Your password has been updated successfully!', 'success')
                    return redirect(url_for('profile'))
                except Exception as e:
                    flash(f"Could not persist password update ({e}). If on read-only serverless, please use standard credentials.", 'warning')
                    return redirect(url_for('profile'))

    penalty_info = calculate_flat_penalty(flat_no, member=member) if (flat_no and flat_no != 'Office') else None

    # Resolve active email & phone with complete fallback hierarchy
    resolved_email = ''
    resolved_phone = ''
    if contact:
        resolved_email = contact.get('email_1') or contact.get('email_2') or ''
        resolved_phone = contact.get('mobile_num_1') or contact.get('mobile_num_2') or ''
    if not resolved_email and admin:
        resolved_email = admin.get('email') or ''
    if not resolved_phone and admin:
        resolved_phone = admin.get('phone') or ''
    if not resolved_email and user:
        resolved_email = user.get('email') or ''
    if not resolved_phone and user:
        resolved_phone = user.get('phone') or ''

    return render_template(
        'profile.html',
        member=member or user,
        contact=contact,
        admin=admin,
        penalty_info=penalty_info,
        resolved_email=resolved_email,
        resolved_phone=resolved_phone
    )

# --- Dashboard ---
@app.route('/dashboard')
@login_required
def dashboard():
    try:
        user = session.get('user', {})
        if not isinstance(user, dict):
            user = {}
        is_admin = bool(user.get('is_admin') or user.get('role') in ADMIN_ROLES)
        
        if is_admin:
            try:
                total_collected_row = query_db("SELECT COALESCE(SUM(amount), 0) as total, COUNT(*) as count FROM tbl_receipts", one=True)
                total_collected = float(total_collected_row.get('total') or 0.0) if total_collected_row else 0.0
                total_receipts_count = int(total_collected_row.get('count') or 0) if total_collected_row else 0
            except Exception:
                total_collected = 0.0
                total_receipts_count = 0
            
            try:
                total_expenses_row = query_db("SELECT COALESCE(SUM(amount), 0) as total, COUNT(*) as count FROM tbl_expenses", one=True)
                total_expenses = float(total_expenses_row.get('total') or 0.0) if total_expenses_row else 0.0
                total_vouchers_count = int(total_expenses_row.get('count') or 0) if total_expenses_row else 0
            except Exception:
                total_expenses = 0.0
                total_vouchers_count = 0
            
            try:
                total_members_row = query_db("SELECT COUNT(*) as count FROM tbl_membership", one=True)
                total_members = int(total_members_row.get('count') or 0) if total_members_row else 0
            except Exception:
                total_members = 44
            
            # Calculate Defaulters & Penalty Overview KPIs
            # Fast batch calculation: Pre-fetch all receipts once into memory to eliminate 44 N+1 queries
            try:
                all_rcpts_for_penalty = query_db("SELECT flat_no, coverage_end, payment_date, remarks, subscription_type FROM tbl_receipts") or []
            except Exception:
                all_rcpts_for_penalty = []
            rcpts_by_flat_map = {}
            for r_p in all_rcpts_for_penalty:
                fn_k = str(r_p.get('flat_no', '')).strip().upper()
                rcpts_by_flat_map.setdefault(fn_k, []).append(r_p)

            try:
                members_all = query_db("SELECT flat_no, monthly_charge, member_name FROM tbl_membership") or []
            except Exception:
                members_all = []
                
            defaulters_total_count = 0
            total_penalty_accumulated = 0.0
            total_maintenance_overdue = 0.0
            building_blocks = {'Block A': {}, 'Block B': {}, 'Block C': {}}
            for m_row in members_all:
                try:
                    fn = str(m_row.get('flat_no', '')).strip()
                    p_calc = calculate_flat_penalty(fn, member=m_row, receipts_by_flat=rcpts_by_flat_map)
                    overdue_m = int(p_calc.get('overdue_months', 0)) if p_calc else 0
                    
                    if overdue_m > 0:
                        defaulters_total_count += 1
                        total_maintenance_overdue += float(p_calc.get('base_due') or 0.0)
                        total_penalty_accumulated += float(p_calc.get('penalty_amount') or 0.0)

                    if overdue_m == 0:
                        stat = 'paid'
                    elif overdue_m <= 2:
                        stat = 'due'
                    else:
                        stat = 'critical'

                    # Extract block and floor across 3 Wings (Block A, Block B, Block C)
                    blk = 'Block A'
                    flr = '1'
                    unt = fn
                    if '/' in fn:
                        parts = fn.split('/')
                        b_letter = parts[0].strip().upper()
                        blk = f"Block {b_letter}" if b_letter in ['A', 'B', 'C'] else 'Block A'
                        if '-' in parts[1]:
                            flr_part, unt_part = parts[1].split('-', 1)
                            flr = 'GR' if 'GR' in flr_part.upper() else flr_part.strip().upper()
                            unt = unt_part.strip().upper()
                        else:
                            p1 = parts[1].strip().upper()
                            if 'GR' in p1:
                                flr = 'GR'
                                unt = 'GR'
                            else:
                                flr = p1[:1]
                                unt = p1[1:] if len(p1) > 1 else p1
                    elif fn == '-' or 'ROUTH' in str(m_row.get('member_name', '')).upper():
                        blk = 'Block C'
                        flr = 'GR'
                        unt = 'Staff'
                    
                    unit_obj = {
                        'flat_no': fn,
                        'unit': unt,
                        'member_name': m_row.get('member_name', 'Resident'),
                        'monthly_charge': float(m_row.get('monthly_charge', 0.0) or 0.0),
                        'sq_feet': m_row.get('RvsdFlatSize', 1200),
                        'status': stat,
                        'overdue_months': overdue_m,
                        'base_due': float(p_calc.get('base_due', 0.0) or 0.0),
                        'penalty_amount': float(p_calc.get('penalty_amount', 0.0) or 0.0),
                        'total_due': float(p_calc.get('total_due', 0.0) or 0.0),
                        'coverage_display': p_calc.get('coverage_display', 'Up to date')
                    }
                    
                    building_blocks.setdefault(blk, {}).setdefault(flr, []).append(unit_obj)
                except Exception:
                    pass

            # Sort floors descending for realistic building elevation (4, 3, 2, 1, GR)
            floor_order = ['4', '3', '2', '1', 'GR']
            sorted_building_blocks = {}
            for b_name, flr_dict in building_blocks.items():
                sorted_building_blocks[b_name] = []
                for f_code in floor_order:
                    if f_code in flr_dict:
                        f_label = 'Ground' if f_code == 'GR' else f"{f_code}F"
                        sorted_building_blocks[b_name].append({
                            'floor_code': f_code,
                            'floor_label': f_label,
                            'units': sorted(flr_dict[f_code], key=lambda u: u['unit'])
                        })
                # Add any extra floors not in standard list
                for f_code, u_list in flr_dict.items():
                    if f_code not in floor_order:
                        sorted_building_blocks[b_name].append({
                            'floor_code': f_code,
                            'floor_label': f_code,
                            'units': sorted(u_list, key=lambda u: u['unit'])
                        })

            search_q = request.args.get('q', '').strip()
            rcpt_query = "SELECT * FROM tbl_receipts"
            rcpt_params = []
            if search_q:
                rcpt_query += " WHERE flat_no LIKE %s OR member_name LIKE %s OR remarks LIKE %s OR receipt_no = %s"
                rcpt_params.extend([f"%{search_q}%", f"%{search_q}%", f"%{search_q}%", search_q if search_q.isdigit() else 0])
            rcpt_query += " ORDER BY receipt_no DESC LIMIT 100"
            
            try:
                recent_receipts = query_db(rcpt_query, rcpt_params) or []
            except Exception:
                recent_receipts = []
                
            try:
                recent_expenses = query_db("SELECT * FROM tbl_expenses ORDER BY voucher_no DESC LIMIT 100") or []
            except Exception:
                recent_expenses = []
            
            try:
                pinned_notices = query_db("SELECT * FROM tbl_notices WHERE is_pinned = 1 AND status = 'ACTIVE' ORDER BY priority = 'URGENT' DESC, id DESC LIMIT 3") or []
                recent_notices = query_db("SELECT * FROM tbl_notices WHERE status = 'ACTIVE' ORDER BY is_pinned DESC, priority = 'URGENT' DESC, id DESC LIMIT 4") or []
            except Exception:
                pinned_notices = []
                recent_notices = []
                
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
                building_blocks=sorted_building_blocks,
                recent_receipts=recent_receipts,
                recent_expenses=recent_expenses,
                pinned_notices=pinned_notices,
                recent_notices=recent_notices,
                search_q=search_q,
                current_year=2026
            )
        else:
            flat_no = user.get('flat_no', '')
            try:
                my_receipts = query_db(
                    "SELECT * FROM tbl_receipts WHERE flat_no = %s ORDER BY receipt_no DESC", 
                    (flat_no,)
                ) or []
            except Exception:
                my_receipts = []
            
            try:
                total_paid_row = query_db(
                    "SELECT COALESCE(SUM(amount), 0) as total FROM tbl_receipts WHERE flat_no = %s",
                    (flat_no,),
                    one=True
                )
                total_paid = float(total_paid_row.get('total') or 0.0) if total_paid_row else 0.0
            except Exception:
                total_paid = 0.0
            
            try:
                member = query_db("SELECT * FROM tbl_membership WHERE flat_no = %s", (flat_no,), one=True)
                my_penalty = calculate_flat_penalty(flat_no, member=member)
            except Exception:
                member = None
                my_penalty = {
                    'flat_no': flat_no,
                    'member_name': user.get('name', 'Resident'),
                    'overdue_months': 0,
                    'base_due': 0.0,
                    'penalty_amount': 0.0,
                    'total_due': 0.0,
                    'coverage_display': 'Up to Date'
                }
            
            try:
                total_expenses_row = query_db("SELECT COALESCE(SUM(amount), 0) as total FROM tbl_expenses", one=True)
                total_expenses = float(total_expenses_row.get('total') or 0.0) if total_expenses_row else 0.0
                recent_expenses = query_db("SELECT * FROM tbl_expenses ORDER BY voucher_no DESC LIMIT 5") or []
            except Exception:
                total_expenses = 0.0
                recent_expenses = []
            
            try:
                pinned_notices = query_db("SELECT * FROM tbl_notices WHERE is_pinned = 1 AND status = 'ACTIVE' ORDER BY priority = 'URGENT' DESC, id DESC LIMIT 3") or []
                recent_notices = query_db("SELECT * FROM tbl_notices WHERE status = 'ACTIVE' ORDER BY is_pinned DESC, priority = 'URGENT' DESC, id DESC LIMIT 4") or []
            except Exception:
                pinned_notices = []
                recent_notices = []

            return render_template(
                'dashboard.html',
                is_admin=False,
                member=member,
                my_receipts=my_receipts,
                total_paid=total_paid,
                outstanding=my_penalty.get('base_due', 0.0) if my_penalty else 0.0,
                my_penalty=my_penalty,
                total_expenses=total_expenses,
                recent_expenses=recent_expenses,
                pinned_notices=pinned_notices,
                recent_notices=recent_notices,
                current_year=2026
            )
    except Exception as e:
        app.logger.error(f"Dashboard render exception: {e}\n{traceback.format_exc()}")
        return render_template(
            'dashboard.html',
            is_admin=bool(session.get('user', {}).get('is_admin')),
            total_members=44,
            total_collected=0.0,
            total_receipts_count=0,
            total_expenses=0.0,
            total_vouchers_count=0,
            net_balance=0.0,
            defaulters_total_count=0,
            total_penalty_accumulated=0.0,
            total_maintenance_overdue=0.0,
            recent_receipts=[],
            recent_expenses=[],
            recent_activity_logs=[],
            pinned_notices=[],
            recent_notices=[],
            search_q='',
            current_year=2026
        )

# --- Modern Web App APIs (Command Palette & Helpdesk) ---
@app.route('/api/command-palette-data')
@login_required
def command_palette_data():
    """Provides instant JSON search indexing for the global Command Palette (Ctrl+K)."""
    user = session.get('user', {})
    if not isinstance(user, dict):
        user = {}
    is_admin = bool(user.get('is_admin') or user.get('role') in ADMIN_ROLES)
    
    # 1. Navigation items
    nav_items = [
        {'id': 'nav-dash', 'title': 'Dashboard', 'desc': 'Overview, financials & announcements', 'category': 'Navigation', 'icon': '📊', 'url': url_for('dashboard')},
        {'id': 'nav-notices', 'title': 'Notice Board', 'desc': 'Official circulars & broadcasts', 'category': 'Navigation', 'icon': '📢', 'url': url_for('notices_list')},
        {'id': 'nav-expenses', 'title': 'Society Expenses', 'desc': 'Audited outlays & monthly charts', 'category': 'Navigation', 'icon': '🧾', 'url': url_for('expenses_list')},
        {'id': 'nav-profile', 'title': 'My Profile', 'desc': 'Account settings & contact info', 'category': 'Navigation', 'icon': '⚙️', 'url': url_for('profile')}
    ]
    
    if is_admin:
        nav_items.extend([
            {'id': 'nav-members', 'title': 'Resident Directory', 'desc': '44 Flat roster & contacts', 'category': 'Admin Console', 'icon': '👥', 'url': url_for('admin_members')},
            {'id': 'nav-receipts', 'title': 'Receipts Ledger', 'desc': 'Issue & print official slips', 'category': 'Admin Console', 'icon': '💳', 'url': url_for('admin_receipts')},
            {'id': 'nav-penalties', 'title': 'Penalties & Defaulters', 'desc': 'Track overdue accounts', 'category': 'Admin Console', 'icon': '⚖️', 'url': url_for('admin_penalties')},
            {'id': 'nav-audit', 'title': 'Activity & Audit Logs', 'desc': 'Trace system actions & IPs', 'category': 'Admin Console', 'icon': '🛡️', 'url': url_for('admin_audit_logs')},
            {'id': 'nav-tariffs', 'title': 'Tariff & Rates Engine', 'desc': 'Per sq-ft and penalty rules', 'category': 'Admin Console', 'icon': '⚡', 'url': url_for('admin_billing_rates')}
        ])

    # 2. Quick Actions
    action_items = [
        {'id': 'act-theme', 'title': 'Toggle Dark / Light Theme', 'desc': 'Switch visual color palette', 'category': 'Actions', 'icon': '🌓', 'action': 'toggle_theme'}
    ]
    if is_admin:
        action_items.extend([
            {'id': 'act-expense', 'title': 'Record New Society Expense', 'desc': 'Log vendor invoice or voucher', 'category': 'Actions', 'icon': '➕', 'url': url_for('expenses_list') + '#new-expense'},
            {'id': 'act-notice', 'title': 'Post New Notice Broadcast', 'desc': 'Draft official circular', 'category': 'Actions', 'icon': '📢', 'url': url_for('notices_list') + '#new-notice'},
            {'id': 'act-receipt', 'title': 'Issue Maintenance Receipt', 'desc': 'Generate verified payment slip', 'category': 'Actions', 'icon': '💳', 'url': url_for('admin_receipts') + '#issue-receipt'}
        ])
    else:
        action_items.append({
            'id': 'act-pay', 'title': 'Pay Maintenance via UPI QR', 'desc': 'Instant QR code payment', 'category': 'Actions', 'icon': '📱', 'action': 'open_upi_modal'
        })

    # 3. Flats & Residents Directory
    flat_items = []
    try:
        members_data = query_db("SELECT flat_no, member_name FROM tbl_membership ORDER BY flat_no") or []
        for m in members_data:
            flat_items.append({
                'id': f"flat-{m['flat_no']}",
                'title': f"Flat {m['flat_no']} - {m['member_name']}",
                'desc': 'Resident directory record',
                'category': 'Residents',
                'icon': '🏠',
                'url': url_for('admin_members') if is_admin else url_for('dashboard')
            })
    except Exception:
        pass

    # 4. Recent Notices
    notice_items = []
    try:
        notices_data = query_db("SELECT id, title, category, priority FROM tbl_notices WHERE status = 'ACTIVE' ORDER BY id DESC LIMIT 8") or []
        for n in notices_data:
            notice_items.append({
                'id': f"notice-{n['id']}",
                'title': n['title'],
                'desc': f"Notice #{n['id']} • {n.get('category', 'GENERAL')}",
                'category': 'Announcements',
                'icon': '📌' if n.get('priority') == 'URGENT' else '📄',
                'url': url_for('notices_list') + f"#notice-{n['id']}"
            })
    except Exception:
        pass

    return jsonify({
        'navigation': nav_items,
        'actions': action_items,
        'residents': flat_items,
        'notices': notice_items
    })

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

@app.route('/receipts/<int:receipt_no>/pdf')
@login_required
def download_receipt_pdf(receipt_no):
    user = session.get('user', {})
    is_admin = bool(user.get('is_admin') or user.get('role') in ADMIN_ROLES)
    
    receipt = query_db("SELECT * FROM tbl_receipts WHERE receipt_no = %s", (receipt_no,), one=True)
    if not receipt:
        abort(404, description="Receipt not found")
        
    if not is_admin and str(receipt.get('flat_no')).strip().lower() != str(user.get('flat_no')).strip().lower():
        flash('Access Denied: You are not authorized to view another resident\'s receipt.', 'danger')
        return redirect(url_for('dashboard'))
        
    member_info = query_db("SELECT * FROM tbl_membership WHERE flat_no = %s", (receipt['flat_no'],), one=True)
    contact_info = query_db("SELECT * FROM tbl_mbr_cntct WHERE flat_no = %s", (receipt['flat_no'],), one=True)
    
    pdf_bytes = generate_receipt_pdf_bytes(receipt, member_info or {}, contact_info or {})
    clean_flat = str(receipt.get('flat_no', '')).replace('/', '_').replace(' ', '')
    filename = f"Official_Receipt_SDERA_{receipt_no}_{clean_flat}.pdf"
    
    as_attachment = request.args.get('download', '0') == '1'
    disposition = 'attachment' if as_attachment else 'inline'
    
    return Response(
        pdf_bytes,
        mimetype='application/pdf',
        headers={
            'Content-Disposition': f'{disposition}; filename="{filename}"',
            'Content-Length': str(len(pdf_bytes)),
            'Cache-Control': 'private, max-age=0, must-revalidate'
        }
    )

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
    if not custom_email and not is_admin and user.get('email'):
        custom_email = user.get('email')
        
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

@app.route('/receipts/<int:receipt_no>/whatsapp', methods=['GET', 'POST'])
@login_required
def whatsapp_receipt(receipt_no):
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
        
    member_info = query_db("SELECT * FROM tbl_membership WHERE flat_no = %s", (receipt['flat_no'],), one=True)
    contact_info = query_db("SELECT * FROM tbl_mbr_cntct WHERE flat_no = %s", (receipt['flat_no'],), one=True)
    
    target_phone = None
    if request.is_json:
        target_phone = (request.get_json(silent=True) or {}).get('phone')
    if not target_phone:
        target_phone = request.form.get('phone') or request.args.get('phone')
    if not target_phone and contact_info:
        target_phone = contact_info.get('mobile_num_1') or contact_info.get('mobile_num_2')
        
    base_url = get_app_base_url()
    formatted_msg = format_receipt_whatsapp_message(receipt, member_info, contact_info, base_url=base_url)
    
    sender_name = user.get('name') or user.get('username') or 'Admin'
    result = send_whatsapp_message(
        phone_raw=target_phone,
        message_text=formatted_msg,
        msg_type='RECEIPT',
        recipient_flat=receipt.get('flat_no', '-'),
        recipient_name=receipt.get('member_name', ''),
        sent_by=sender_name,
        base_url=base_url
    )
    result['message_text'] = formatted_msg
    result['clean_phone'] = normalize_whatsapp_phone(target_phone)
    result['receipt_no'] = receipt_no
    
    log_activity('WHATSAPP_RECEIPT', f"Generated WhatsApp receipt slip for SDERA_{receipt_no} (Flat {receipt['flat_no']})")
    
    if is_ajax:
        return jsonify(result), 200
        
    return redirect(result['direct_url'])

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
    
    next_voucher_row = query_db("SELECT COALESCE(MAX(voucher_no), 0) + 1 as next_v FROM tbl_expenses", one=True)
    next_voucher_no = int(next_voucher_row['next_v']) if next_voucher_row else 1
    
    return render_template(
        'expenses.html',
        expenses=expenses,
        particulars_list=particulars_list,
        spl_heads_list=spl_heads_list,
        total_incurred=total_incurred,
        current_particulars=particulars_filter,
        current_spl_head=spl_head_filter,
        search_q=search_q,
        next_voucher_no=next_voucher_no
    )

@app.route('/admin/expenses/new', methods=['POST'])
@roles_required('super_admin', 'billing_admin', 'president', 'secretary', 'treasurer', 'caretaker')
def add_expense():
    voucher_date = request.form.get('voucher_date', str(date.today()))
    expense_description = request.form.get('expense_description', '').strip()
    particulars = request.form.get('particulars', 'Misc & Other Expenses').strip()
    spl_head = request.form.get('spl_head', '').strip()
    payment_by = request.form.get('payment_by', 'Cash')
    amount = request.form.get('amount', '0').strip()
    voucher_no_input = request.form.get('voucher_no', '').strip()
    
    if not expense_description or not amount:
        flash('Description and Amount are required.', 'danger')
        return redirect(url_for('expenses_list'))
        
    try:
        max_v_row = query_db("SELECT COALESCE(MAX(voucher_no), 0) + 1 as next_v FROM tbl_expenses", one=True)
        calc_next = int(max_v_row['next_v']) if max_v_row else 1
        v_no = int(voucher_no_input) if (voucher_no_input and voucher_no_input.isdigit()) else calc_next

        execute_db(
            """INSERT INTO tbl_expenses (voucher_no, voucher_date, expense_description, particulars, spl_head, payment_by, amount)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (v_no, voucher_date, expense_description, particulars, spl_head, payment_by, float(amount))
        )
        log_activity('EXPENSE_RECORDED', f"Recorded Expense Voucher #{v_no} ({expense_description}) - INR {float(amount):,.2f} ({particulars})")
        flash(f"✓ Expense voucher #{v_no} for INR {float(amount):,.2f} recorded successfully.", 'success')
    except Exception as e:
        flash(f"Error adding expense: {e}", 'danger')
        
    return redirect(url_for('expenses_list'))

@app.route('/admin/expenses/<int:voucher_no>/edit', methods=['POST'])
@roles_required('super_admin', 'billing_admin', 'president', 'secretary', 'treasurer', 'caretaker')
def edit_expense(voucher_no):
    voucher_date = request.form.get('voucher_date', '').strip()
    expense_description = request.form.get('expense_description', '').strip()
    particulars = request.form.get('particulars', '').strip()
    spl_head = request.form.get('spl_head', '').strip()
    payment_by = request.form.get('payment_by', 'Online').strip()
    
    if not expense_description or not voucher_date:
        flash('Expense description and voucher date are required.', 'danger')
        return redirect(url_for('expenses_list'))
        
    try:
        current_exp = query_db("SELECT * FROM tbl_expenses WHERE voucher_no = %s", (voucher_no,), one=True)
        if not current_exp:
            flash(f"Expense voucher #{voucher_no} not found.", 'danger')
            return redirect(url_for('expenses_list'))

        execute_db(
            """UPDATE tbl_expenses 
               SET voucher_date = %s, expense_description = %s, particulars = %s, spl_head = %s, payment_by = %s 
               WHERE voucher_no = %s""",
            (voucher_date, expense_description, particulars, spl_head, payment_by, voucher_no)
        )
        log_activity('EXPENSE_UPDATED', f"Updated Expense Voucher #{voucher_no} ({expense_description}) - INR {float(current_exp['amount']):,.2f} ({particulars})")
        flash(f"✓ Expense Voucher #{voucher_no} updated successfully.", 'success')
    except Exception as e:
        flash(f"Error updating expense voucher #{voucher_no}: {e}", 'danger')
        
    return redirect(url_for('expenses_list'))

@app.route('/admin/expenses/<int:voucher_no>/delete', methods=['POST'])
@roles_required('super_admin', 'billing_admin', 'president', 'secretary', 'treasurer', 'caretaker')
def delete_expense(voucher_no):
    flash('Deleting society expense records is disabled to maintain financial and audit integrity.', 'warning')
    return redirect(url_for('expenses_list'))

@app.route('/expenses/<int:voucher_no>/pdf')
@login_required
def download_expense_pdf(voucher_no):
    expense = query_db("SELECT * FROM tbl_expenses WHERE voucher_no = %s", (voucher_no,), one=True)
    if not expense:
        abort(404, description="Expense voucher not found")
    
    pdf_bytes = generate_expense_voucher_pdf_bytes(expense)
    filename = f"SDERA_Expense_Voucher_{int(voucher_no):03d}.pdf"
    
    return Response(
        pdf_bytes,
        mimetype='application/pdf',
        headers={
            'Content-Disposition': f'inline; filename="{filename}"',
            'Content-Type': 'application/pdf'
        }
    )

@app.route('/expenses/export-zip')
@login_required
def export_all_expenses_zip():
    expenses = query_db("SELECT * FROM tbl_expenses ORDER BY voucher_no ASC") or []
    if not expenses:
        flash("No expense vouchers available for export.", "warning")
        return redirect(url_for('expenses_list'))
        
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        for exp in expenses:
            v_no = int(exp['voucher_no'])
            pdf_data = generate_expense_voucher_pdf_bytes(exp)
            filename = f"SDERA_Expense_Voucher_{v_no:03d}.pdf"
            zip_file.writestr(filename, pdf_data)
            
    zip_buffer.seek(0)
    zip_bytes = zip_buffer.getvalue()
    zip_buffer.close()
    
    timestamp = datetime.now().strftime('%Y%m%d')
    archive_filename = f"SDERA_All_Expense_Vouchers_{timestamp}.zip"
    
    return Response(
        zip_bytes,
        mimetype='application/zip',
        headers={
            'Content-Disposition': f'attachment; filename="{archive_filename}"',
            'Content-Type': 'application/zip'
        }
    )

@app.route('/expenses/export-master-pdf')
@login_required
def export_all_expenses_master_pdf():
    expenses = query_db("SELECT * FROM tbl_expenses ORDER BY voucher_no ASC") or []
    if not expenses:
        flash("No expense vouchers available for compilation.", "warning")
        return redirect(url_for('expenses_list'))
        
    pdf_bytes = generate_all_expenses_book_pdf_bytes(expenses)
    timestamp = datetime.now().strftime('%Y%m%d')
    filename = f"SDERA_Master_Expense_Book_{timestamp}.pdf"
    
    return Response(
        pdf_bytes,
        mimetype='application/pdf',
        headers={
            'Content-Disposition': f'attachment; filename="{filename}"',
            'Content-Type': 'application/pdf'
        }
    )

@app.route('/api/expenses/list-json')
@login_required
def api_expenses_list_json():
    expenses = query_db("SELECT voucher_no, voucher_date, expense_description, particulars, spl_head, payment_by, amount FROM tbl_expenses ORDER BY voucher_no ASC") or []
    items = []
    for e in expenses:
        v_no = int(e['voucher_no'])
        items.append({
            'voucher_no': v_no,
            'voucher_date': str(e['voucher_date'])[:10],
            'description': e['expense_description'],
            'particulars': e['particulars'],
            'spl_head': e['spl_head'] or '',
            'payment_by': e['payment_by'],
            'amount': float(e['amount']),
            'pdf_url': url_for('download_expense_pdf', voucher_no=v_no),
            'filename': f"SDERA_Expense_Voucher_{v_no:03d}.pdf"
        })
    return jsonify({
        'success': True,
        'count': len(items),
        'vouchers': items,
        'zip_url': url_for('export_all_expenses_zip'),
        'master_pdf_url': url_for('export_all_expenses_master_pdf')
    })

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
    all_flats = query_db("SELECT flat_no, member_name, monthly_charge FROM tbl_membership ORDER BY flat_no")
    
    max_rcpt_row = query_db("SELECT COALESCE(MAX(receipt_no), 2390) + 1 as next_r FROM tbl_receipts", one=True)
    next_receipt_no = int(max_rcpt_row['next_r']) if max_rcpt_row else 2391
    
    return render_template(
        'admin_receipts.html',
        receipts=receipts,
        all_flats=all_flats,
        flat_filter=flat_filter,
        month_filter=month_filter,
        search_q=search_q,
        next_receipt_no=next_receipt_no
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
    receipt_no_input = request.form.get('receipt_no', '').strip()
    
    member = query_db("SELECT member_name FROM tbl_membership WHERE flat_no = %s", (flat_no,), one=True)
    member_name = member['member_name'] if member else 'Resident'
    
    try:
        max_r_row = query_db("SELECT COALESCE(MAX(receipt_no), 2390) + 1 as next_r FROM tbl_receipts", one=True)
        calc_next = int(max_r_row['next_r']) if max_r_row else 2391
        r_no = int(receipt_no_input) if (receipt_no_input and receipt_no_input.isdigit()) else calc_next

        execute_db(
            """INSERT INTO tbl_receipts (receipt_no, flat_no, member_name, amount, pymnt_mode, subscription_type, remarks, payment_date, receipt_date, coverage_start, coverage_end)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (r_no, flat_no, member_name, float(amount), pymnt_mode, subscription_type, remarks, payment_date, receipt_date, coverage_start, coverage_end)
        )
        receipt_no = r_no
        log_activity('RECEIPT_ISSUED', f"Generated Receipt #{receipt_no} for Flat {flat_no} ({member_name}) - INR {float(amount):,.2f} ({remarks})")
        flash(f"✓ Receipt #{receipt_no} (SDERA_{receipt_no}) generated successfully for Flat {flat_no} ({member_name})!", 'success')
        
        if auto_email:
            send_res = send_receipt_email(receipt_no)
            if send_res['success']:
                flash(f"✓ Official receipt PDF emailed to Flat {flat_no}.", 'info')
    except Exception as e:
        flash(f"Error creating receipt: {e}", 'danger')
        
    return redirect(url_for('admin_receipts'))

@app.route('/api/receipts/<int:receipt_no>')
@login_required
def api_get_receipt(receipt_no):
    user = session.get('user', {})
    is_admin = bool(user.get('is_admin') or user.get('role') in ADMIN_ROLES)
    rcpt = query_db("SELECT * FROM tbl_receipts WHERE receipt_no = %s", (receipt_no,), one=True)
    if not rcpt:
        return jsonify({'success': False, 'message': f'Receipt #{receipt_no} not found'}), 404
    if not is_admin and str(rcpt.get('flat_no')).strip().lower() != str(user.get('flat_no')).strip().lower():
        return jsonify({'success': False, 'message': 'Access Denied'}), 403
    
    rcpt_dict = dict(rcpt)
    if rcpt_dict.get('payment_date'):
        rcpt_dict['payment_date'] = str(rcpt_dict['payment_date'])
    if rcpt_dict.get('receipt_date'):
        rcpt_dict['receipt_date'] = str(rcpt_dict['receipt_date'])
    if rcpt_dict.get('coverage_start'):
        rcpt_dict['coverage_start'] = str(rcpt_dict['coverage_start'])
    if rcpt_dict.get('coverage_end'):
        rcpt_dict['coverage_end'] = str(rcpt_dict['coverage_end'])
    rcpt_dict['amount'] = float(rcpt_dict.get('amount') or 0)
    
    return jsonify({'success': True, 'receipt': rcpt_dict})

@app.route('/admin/receipts/<int:receipt_no>/edit', methods=['POST'])
@roles_required('super_admin', 'billing_admin', 'president', 'secretary', 'treasurer', 'caretaker')
def edit_receipt(receipt_no):
    rcpt = query_db("SELECT * FROM tbl_receipts WHERE receipt_no = %s", (receipt_no,), one=True)
    if not rcpt:
        flash(f"Receipt #{receipt_no} not found.", 'danger')
        return redirect(url_for('admin_receipts'))
        
    payment_date = request.form.get('payment_date', '').strip() or str(date.today())
    receipt_date = request.form.get('receipt_date', '').strip() or str(date.today())
    amount_str = request.form.get('amount', '').strip()
    pymnt_mode = request.form.get('pymnt_mode', 'Online').strip()
    subscription_type = request.form.get('subscription_type', 'Monthly Subscription').strip()
    remarks = request.form.get('remarks', '').strip()
    coverage_start = request.form.get('coverage_start', '').strip() or payment_date
    coverage_end = request.form.get('coverage_end', '').strip() or payment_date
    
    try:
        amount = float(amount_str)
        if amount <= 0:
            flash("Amount must be greater than zero.", 'danger')
            return redirect(url_for('admin_receipts'))
            
        execute_db(
            """UPDATE tbl_receipts 
               SET payment_date = %s, receipt_date = %s, amount = %s, pymnt_mode = %s, 
                   subscription_type = %s, remarks = %s, coverage_start = %s, coverage_end = %s 
               WHERE receipt_no = %s""",
            (payment_date, receipt_date, amount, pymnt_mode, subscription_type, remarks, coverage_start, coverage_end, receipt_no)
        )
        log_activity('RECEIPT_UPDATED', f"Updated Receipt #{receipt_no} (SDERA_{receipt_no}) for Flat {rcpt.get('flat_no')} - Payment Date: {payment_date}, Issue Date: {receipt_date}, Amount: INR {amount:,.2f}")
        flash(f"✓ Receipt SDERA_{receipt_no} updated successfully (Payment Date: {payment_date}, Issue Date: {receipt_date}).", 'success')
    except Exception as e:
        flash(f"Error updating receipt #{receipt_no}: {e}", 'danger')
        
    return redirect(url_for('admin_receipts'))

@app.route('/admin/receipts/<int:receipt_no>/delete', methods=['POST'])
@roles_required('super_admin', 'billing_admin', 'president', 'secretary', 'treasurer', 'caretaker')
def delete_receipt(receipt_no):
    try:
        rcpt = query_db("SELECT flat_no, member_name FROM tbl_receipts WHERE receipt_no = %s", (receipt_no,), one=True)
        execute_db("DELETE FROM tbl_receipts WHERE receipt_no = %s", (receipt_no,))
        try:
            execute_db("DELETE FROM receipts WHERE receipt_no = %s OR receipt_no = %s", (str(receipt_no), f"SDERA_{receipt_no}"))
        except Exception:
            pass
        log_activity('RECEIPT_DELETED', f"Deleted Receipt #{receipt_no} for Flat {rcpt['flat_no'] if rcpt else '-'}")
        if rcpt:
            flash(f"✓ Receipt #{receipt_no} (SDERA_{receipt_no}) for Flat {rcpt['flat_no']} ({rcpt['member_name']}) was deleted successfully.", 'info')
        else:
            flash(f"✓ Receipt #{receipt_no} deleted.", 'info')
    except Exception as e:
        flash(f"Error deleting receipt #{receipt_no}: {e}", 'danger')
        
    return redirect(url_for('admin_receipts'))

# --- Administrative: Resident Directory ---
@app.route('/admin/members')
@roles_required('super_admin', 'billing_admin', 'president', 'secretary', 'treasurer', 'caretaker')
def admin_members():
    search_q = request.args.get('q', '').strip()
    
    query = """
        SELECT m.*, 
               c.mobile_num_1, c.mobile_num_2, c.email_1, c.email_2,
               COALESCE(r.total_paid, 0) as total_paid,
               COALESCE(r.receipts_count, 0) as receipts_count,
               r.last_payment_date
        FROM tbl_membership m
        LEFT JOIN tbl_mbr_cntct c ON LOWER(TRIM(m.flat_no)) = LOWER(TRIM(c.flat_no))
        LEFT JOIN (
            SELECT LOWER(TRIM(flat_no)) as flat_no,
                   SUM(amount) as total_paid,
                   COUNT(receipt_no) as receipts_count,
                   MAX(payment_date) as last_payment_date
            FROM tbl_receipts
            GROUP BY LOWER(TRIM(flat_no))
        ) r ON LOWER(TRIM(m.flat_no)) = r.flat_no
    """
    params = []
    if search_q:
        query += " WHERE m.flat_no LIKE %s OR m.member_name LIKE %s OR c.mobile_num_1 LIKE %s OR c.email_1 LIKE %s"
        params.extend([f"%{search_q}%", f"%{search_q}%", f"%{search_q}%", f"%{search_q}%"])
        
    query += " ORDER BY m.flat_no"
    members = query_db(query, params)
    
    return render_template('admin_members.html', members=members, search_q=search_q)

@app.route('/admin/members/update-contact', methods=['POST'])
@roles_required('super_admin', 'billing_admin', 'president', 'secretary', 'treasurer', 'caretaker')
def admin_update_member_contact():
    flat_no = request.form.get('flat_no', '').strip()
    email = request.form.get('email', '').strip()
    phone = request.form.get('phone', '').strip()
    
    if not flat_no:
        flash('Flat number is required.', 'danger')
        return redirect(url_for('admin_members'))
        
    try:
        cnt = query_db("SELECT flat_no FROM tbl_mbr_cntct WHERE LOWER(TRIM(flat_no)) = LOWER(TRIM(%s))", (flat_no,), one=True)
        if cnt:
            execute_db(
                "UPDATE tbl_mbr_cntct SET email_1 = %s, mobile_num_1 = %s WHERE LOWER(TRIM(flat_no)) = LOWER(TRIM(%s))",
                (email, phone, flat_no)
            )
        else:
            execute_db(
                "INSERT INTO tbl_mbr_cntct (flat_no, email_1, mobile_num_1) VALUES (%s, %s, %s)",
                (flat_no, email, phone)
            )

        # Sync officer admin table if flat belongs to a committee bearer
        officer_flats_map = {'A/4-C': 'treasurer', 'A/2-A': 'president', 'A/1-C': 'secretary', 'Estate Office': 'caretaker', 'Office': 'admin'}
        u_name = officer_flats_map.get(flat_no)
        if u_name:
            try:
                execute_db("UPDATE tbl_admins SET email = %s, phone = %s WHERE LOWER(username) = LOWER(%s)", (email, phone, u_name))
            except Exception:
                pass
            
        log_activity('PROFILE_UPDATE', f"Treasurer/Admin updated official contact registry for Flat {flat_no} (Email: {email}, Phone: {phone})")
        flash(f"✓ Contact details for Flat {flat_no} updated successfully ({email}).", 'success')
    except Exception as e:
        flash(f"Error updating contact details for Flat {flat_no}: {e}", 'danger')
        
    return redirect(url_for('admin_members'))

# --- Administrative: Activity & Audit Trail Panel ---
@app.route('/admin/audit-logs')
@roles_required('super_admin', 'billing_admin', 'president', 'secretary', 'treasurer', 'caretaker')
def admin_audit_logs():
    search_q = request.args.get('q', '').strip()
    role_filter = request.args.get('role', '').strip()
    action_filter = request.args.get('action', '').strip()
    days_filter = request.args.get('days', '30').strip()
    
    query = "SELECT * FROM tbl_activity_logs WHERE 1=1"
    params = []
    
    if search_q:
        query += " AND (actor_username LIKE %s OR actor_name LIKE %s OR flat_no LIKE %s OR description LIKE %s OR action_type LIKE %s)"
        params.extend([f"%{search_q}%", f"%{search_q}%", f"%{search_q}%", f"%{search_q}%", f"%{search_q}%"])
        
    if role_filter:
        query += " AND actor_role = %s"
        params.append(role_filter)
        
    if action_filter:
        query += " AND action_type = %s"
        params.append(action_filter)
        
    if days_filter and days_filter.isdigit():
        d_val = int(days_filter)
        if d_val > 0:
            query += " AND created_at >= %s"
            params.append((get_ist_now().replace(tzinfo=None) - timedelta(days=d_val)).strftime('%Y-%m-%d %H:%M:%S'))
            
    query += " ORDER BY id DESC LIMIT 500"
    
    try:
        logs = query_db(query, params) or []
    except Exception as err:
        app.logger.warning(f"Failed to query audit logs: {err}")
        logs = []
    
    # Calculate stats with 1 single aggregated query instead of 4 separate queries
    try:
        stats_row = query_db("""
            SELECT 
                COUNT(*) as total,
                COALESCE(SUM(CASE WHEN actor_role = 'MEMBER' THEN 1 ELSE 0 END), 0) as member,
                COALESCE(SUM(CASE WHEN actor_role != 'MEMBER' THEN 1 ELSE 0 END), 0) as admin,
                COALESCE(SUM(CASE WHEN action_type IN ('LOGIN', 'LOGOUT', 'PASSWORD_CHANGE') THEN 1 ELSE 0 END), 0) as security
            FROM tbl_activity_logs
        """, one=True)
        stats = {
            'total': int(stats_row['total'] or 0) if stats_row else 0,
            'member': int(stats_row['member'] or 0) if stats_row else 0,
            'admin': int(stats_row['admin'] or 0) if stats_row else 0,
            'security': int(stats_row['security'] or 0) if stats_row else 0
        }
    except Exception:
        stats = {'total': len(logs), 'member': 0, 'admin': len(logs), 'security': 0}
    
    try:
        distinct_roles = query_db("SELECT DISTINCT actor_role FROM tbl_activity_logs WHERE actor_role IS NOT NULL ORDER BY actor_role") or []
        distinct_actions = query_db("SELECT DISTINCT action_type FROM tbl_activity_logs WHERE action_type IS NOT NULL ORDER BY action_type") or []
    except Exception:
        distinct_roles = []
        distinct_actions = []
    
    return render_template(
        'admin_audit_logs.html',
        logs=logs,
        stats=stats,
        distinct_roles=distinct_roles,
        distinct_actions=distinct_actions,
        search_q=search_q,
        current_role=role_filter,
        current_action=action_filter,
        current_days=days_filter
    )

@app.route('/api/db-status')
def api_db_status():
    from database import determine_engine, get_mysql_connection
    detected_keys = [k for k in ['DATABASE_URL', 'MYSQL_URL', 'TIDB_URL', 'DB_HOST', 'DB_USER', 'DB_NAME', 'DB_PORT', 'DB_SSL', 'TIDB_HOST', 'MYSQLHOST'] if os.environ.get(k)]
    
    mysql_ok = False
    mysql_err = None
    mysql_version = None
    mysql_tables = []
    
    try:
        conn = get_mysql_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT VERSION() as v;")
                row = cur.fetchone()
                mysql_version = row['v'] if row else 'Unknown'
                cur.execute("SHOW TABLES;")
                mysql_tables = [list(r.values())[0] for r in cur.fetchall()]
            mysql_ok = True
        finally:
            conn.close()
    except Exception as e:
        mysql_err = str(e)
        
    engine = determine_engine()
    
    return jsonify({
        "status": "online",
        "active_engine": engine,
        "mysql_connected": mysql_ok,
        "mysql_error": mysql_err,
        "mysql_version": mysql_version,
        "mysql_tables_count": len(mysql_tables),
        "mysql_tables": mysql_tables,
        "configured_host": Config.DB_HOST[:8] + "..." if len(Config.DB_HOST) > 8 else Config.DB_HOST,
        "configured_port": Config.DB_PORT,
        "configured_db": Config.DB_NAME,
        "configured_ssl": Config.DB_SSL,
        "env_vars_detected": detected_keys
    })

@app.route('/api/seed-cloud-db')
def api_seed_cloud_db():
    from database import get_mysql_connection, ensure_mysql_schema, init_db
    try:
        from seed_data import SEED_MEMBERSHIP, SEED_CONTACTS, SEED_RECEIPTS, SEED_EXPENSES, SEED_ADMINS, SEED_NOTICES
        conn = get_mysql_connection()
        try:
            ensure_mysql_schema(conn)
            
            with conn.cursor() as cur:
                table_map = {
                    'tbl_membership': SEED_MEMBERSHIP,
                    'tbl_mbr_cntct': SEED_CONTACTS,
                    'tbl_receipts': SEED_RECEIPTS,
                    'tbl_expenses': SEED_EXPENSES,
                    'tbl_admins': SEED_ADMINS,
                    'tbl_notices': SEED_NOTICES
                }
                for tbl, rows in table_map.items():
                    if rows:
                        cols = [c for c in rows[0].keys() if not (tbl == 'tbl_membership' and c == 'monthly_charge')]
                        placeholders = ", ".join(["%s"] * len(cols))
                        col_names = ", ".join([f"`{c}`" for c in cols])
                        insert_sql = f"REPLACE INTO `{tbl}` ({col_names}) VALUES ({placeholders});"
                        val_list = [tuple(r.get(c) for c in cols) for r in rows]
                        cur.executemany(insert_sql, val_list)
                conn.commit()
            
            init_db()
            
            members = query_db("SELECT COUNT(*) as cnt FROM tbl_membership;", one=True)
            contacts = query_db("SELECT COUNT(*) as cnt FROM tbl_mbr_cntct;", one=True)
            receipts = query_db("SELECT COUNT(*) as cnt FROM tbl_receipts;", one=True)
            expenses = query_db("SELECT COUNT(*) as cnt FROM tbl_expenses;", one=True)
            
            return jsonify({
                "success": True, 
                "message": "Cloud database successfully populated with all official association data!",
                "members_count": members['cnt'] if members else 0,
                "contacts_count": contacts['cnt'] if contacts else 0,
                "receipts_count": receipts['cnt'] if receipts else 0,
                "expenses_count": expenses['cnt'] if expenses else 0
            })
        finally:
            conn.close()
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

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
def calculate_flat_penalty(flat_no, member=None, target_date=None, receipts_by_flat=None):
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

    # Retrieve all valid coverage end dates for this flat (in-memory lookup when batch provided)
    if receipts_by_flat is not None:
        fn_key = str(flat_no).strip().upper()
        rcpt_rows = receipts_by_flat.get(fn_key, [])
    else:
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

    # Fast batch calculation: Pre-fetch all receipts once into memory to eliminate 44 N+1 queries
    all_rcpts_for_penalty = query_db("SELECT flat_no, coverage_end, payment_date, remarks, subscription_type FROM tbl_receipts") or []
    rcpts_by_flat_map = {}
    for r_p in all_rcpts_for_penalty:
        fn_k = str(r_p.get('flat_no', '')).strip().upper()
        rcpts_by_flat_map.setdefault(fn_k, []).append(r_p)

    for m in members:
        calc = calculate_flat_penalty(m['flat_no'], member=m, target_date=target_date, receipts_by_flat=rcpts_by_flat_map)
        
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
    payment_date = request.args.get('payment_date', '').strip()
    as_of = request.args.get('as_of', '').strip()
    target_date = payment_date or as_of or None
    
    if not flat_no:
        return jsonify({'success': False, 'error': 'Missing flat number parameter'}), 400
        
    calc = calculate_flat_penalty(flat_no, target_date=target_date)
    return jsonify({
        'success': True,
        'data': calc
    })

@app.route('/admin/penalties/whatsapp-reminder', methods=['POST'])
@roles_required('super_admin', 'billing_admin', 'president', 'secretary', 'treasurer', 'caretaker')
def admin_whatsapp_penalty_reminder():
    user = session.get('user', {})
    is_ajax = bool(
        request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 
        request.is_json or 
        'application/json' in request.headers.get('Accept', '')
    )
    
    data = request.get_json(silent=True) if request.is_json else request.form
    flat_no = data.get('flat_no', '').strip()
    target_date_str = data.get('as_of', '').strip()
    custom_phone = data.get('phone', '').strip()
    
    if not flat_no:
        if is_ajax:
            return jsonify({"success": False, "message": "Flat number is required."}), 400
        flash("Flat number is required.", 'danger')
        return redirect(url_for('admin_penalties'))
        
    member = query_db("SELECT * FROM tbl_membership WHERE flat_no = %s", (flat_no,), one=True)
    contact = query_db("SELECT * FROM tbl_mbr_cntct WHERE flat_no = %s", (flat_no,), one=True)
    
    target_date = None
    if target_date_str:
        try:
            target_date = datetime.strptime(target_date_str, '%Y-%m-%d').date()
        except Exception:
            target_date = None
            
    calc = calculate_flat_penalty(flat_no, member=member, target_date=target_date)
    base_url = get_app_base_url()
    formatted_msg = format_dues_reminder_whatsapp_message(calc, contact_info=contact, base_url=base_url)
    
    target_phone = custom_phone
    if not target_phone and contact:
        target_phone = contact.get('mobile_num_1') or contact.get('mobile_num_2')
        
    sender_name = user.get('name') or user.get('username') or 'Admin'
    result = send_whatsapp_message(
        phone_raw=target_phone,
        message_text=formatted_msg,
        msg_type='DUES_REMINDER',
        recipient_flat=flat_no,
        recipient_name=calc.get('member_name', ''),
        sent_by=sender_name,
        base_url=base_url
    )
    result['message_text'] = formatted_msg
    result['clean_phone'] = normalize_whatsapp_phone(target_phone)
    result['member_name'] = calc.get('member_name')
    result['total_due'] = calc.get('total_due')
    
    log_activity('WHATSAPP_REMINDER', f"Issued WhatsApp maintenance reminder to Flat {flat_no} ({calc.get('member_name')}) for Rs {calc.get('total_due'):,.2f}")
    
    if is_ajax:
        return jsonify(result), 200
        
    return redirect(result['direct_url'])


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

# ================= Maintenance Tariff & Billing Rate Scale Console =================
def compute_flat_monthly_charge(sq_feet, flat_charges, capital_fund, common_expenses, cps_charges, tws_charges):
    """
    Compute rounded monthly maintenance charge based on the official formula:
    Total = Round10((Flat Area * Flat Charges) + (Flat Area * Capital Fund) + Common Expenses + CPS Charges + TWS Charges)
    """
    try:
        sq_ft = float(sq_feet or 0)
        fc = float(flat_charges or 0)
        cf = float(capital_fund or 0)
        ce = float(common_expenses or 0)
        cps = float(cps_charges or 0)
        tws = float(tws_charges or 0)
        
        raw_total = (sq_ft * fc) + (sq_ft * cf) + ce + cps + tws
        return int(round(raw_total / 10.0) * 10)
    except Exception:
        return 0

@app.route('/admin/billing-rates', methods=['GET', 'POST'])
@roles_required('super_admin', 'billing_admin')
def admin_billing_rates():
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'apply_global_rates':
            try:
                flat_charges = float(request.form.get('flat_charges', 1.55))
                capital_fund = float(request.form.get('capital_fund', 0.21))
                common_expenses = float(request.form.get('common_expenses', 170.0))
                cps_base_rate = float(request.form.get('cps_charges', 160.0))
                tws_base_rate = float(request.form.get('tws_charges', 150.0))
                
                members = query_db("SELECT * FROM tbl_membership")
                old_total = sum(float(m.get('monthly_charge') or 0) for m in members)
                new_total = 0
                
                is_mysql = (determine_engine() == 'mysql')
                
                for m in members:
                    sq_ft = float(m.get('RvsdFlatSize') or 0)
                    cps_chg = cps_base_rate if m.get('cps_owner') else 0.0
                    tws_chg = (tws_base_rate * (m.get('tws_count') or 1)) if m.get('tws_owner') else 0.0
                    
                    if is_mysql:
                        execute_db(
                            """UPDATE tbl_membership 
                               SET flat_charges = %s, capital_fund = %s, common_expenses = %s, cps_charges = %s, tws_charges = %s 
                               WHERE id = %s""",
                            (flat_charges, capital_fund, common_expenses, cps_chg, tws_chg, m['id'])
                        )
                    else:
                        m_calc = compute_flat_monthly_charge(sq_ft, flat_charges, capital_fund, common_expenses, cps_chg, tws_chg)
                        execute_db(
                            """UPDATE tbl_membership 
                               SET flat_charges = %s, capital_fund = %s, common_expenses = %s, cps_charges = %s, tws_charges = %s, monthly_charge = %s 
                               WHERE id = %s""",
                            (flat_charges, capital_fund, common_expenses, cps_chg, tws_chg, m_calc, m['id'])
                        )
                    
                    new_total += compute_flat_monthly_charge(sq_ft, flat_charges, capital_fund, common_expenses, cps_chg, tws_chg)
                
                log_activity('RATES_UPDATED', f"Applied new global maintenance rates: Flat SqFt Rs {flat_charges}, Common Rs {common_expenses}, CPS Rs {cps_base_rate}, TwS Rs {tws_base_rate}")
                flash(f"⚡ Tariff Rate Scale applied to all 44 flats! Monthly society inflow updated: ₹{old_total:,.2f} ➔ ₹{new_total:,.2f} (Delta: {'+' if new_total >= old_total else ''}₹{new_total - old_total:,.2f})", 'success')
                return redirect(url_for('admin_billing_rates'))
            except Exception as e:
                flash(f"Error applying global rates: {e}", 'danger')
                return redirect(url_for('admin_billing_rates'))

    # GET Request: Prepare statistics, roster & breakdown
    members = query_db("SELECT * FROM tbl_membership ORDER BY flat_no")
    search_q = request.args.get('q', '').strip().lower()
    
    total_area = sum(int(m.get('RvsdFlatSize') or 0) for m in members)
    total_monthly_collection = sum(float(m.get('monthly_charge') or 0) for m in members)
    
    cps_units_count = sum(1 for m in members if m.get('cps_owner'))
    tws_units_count = sum(int(m.get('tws_count') or 1) for m in members if m.get('tws_owner'))
    
    total_flat_area_revenue = sum(float(m.get('RvsdFlatSize') or 0) * float(m.get('flat_charges') or 0) for m in members)
    total_capital_fund_revenue = sum(float(m.get('RvsdFlatSize') or 0) * float(m.get('capital_fund') or 0) for m in members)
    total_common_exp_revenue = sum(float(m.get('common_expenses') or 0) for m in members)
    total_cps_revenue = sum(float(m.get('cps_charges') or 0) for m in members)
    total_tws_revenue = sum(float(m.get('tws_charges') or 0) for m in members)
    
    # Standard rates (from first member or default)
    ref_member = members[0] if members else {}
    current_flat_charges = float(ref_member.get('flat_charges') or 1.55)
    current_capital_fund = float(ref_member.get('capital_fund') or 0.21)
    current_common_expenses = float(ref_member.get('common_expenses') or 170.0)
    current_cps_rate = 160.0
    for m in members:
        if m.get('cps_owner') and float(m.get('cps_charges') or 0) > 0:
            current_cps_rate = float(m['cps_charges'])
            break
            
    current_tws_rate = 150.0
    for m in members:
        if m.get('tws_owner') and float(m.get('tws_charges') or 0) > 0:
            count = m.get('tws_count') or 1
            current_tws_rate = float(m['tws_charges']) / count
            break
            
    filtered_members = []
    for m in members:
        if search_q:
            f_no = str(m.get('flat_no', '')).lower()
            m_name = str(m.get('member_name', '')).lower()
            if search_q not in f_no and search_q not in m_name:
                continue
        filtered_members.append(m)

    return render_template(
        'admin_billing_rates.html',
        members=filtered_members,
        all_members=members,
        total_flats=len(members),
        total_area=total_area,
        total_monthly_collection=total_monthly_collection,
        cps_units_count=cps_units_count,
        tws_units_count=tws_units_count,
        total_flat_area_revenue=total_flat_area_revenue,
        total_capital_fund_revenue=total_capital_fund_revenue,
        total_common_exp_revenue=total_common_exp_revenue,
        total_cps_revenue=total_cps_revenue,
        total_tws_revenue=total_tws_revenue,
        current_flat_charges=current_flat_charges,
        current_capital_fund=current_capital_fund,
        current_common_expenses=current_common_expenses,
        current_cps_rate=current_cps_rate,
        current_tws_rate=current_tws_rate,
        search_q=search_q
    )

@app.route('/admin/billing-rates/unit/<int:member_id>', methods=['POST'])
@roles_required('super_admin', 'billing_admin')
def admin_update_unit_rates(member_id):
    try:
        member = query_db("SELECT * FROM tbl_membership WHERE id = %s", (member_id,), one=True)
        if not member:
            flash("Member flat not found.", 'danger')
            return redirect(url_for('admin_billing_rates'))
            
        sq_ft = float(request.form.get('sq_feet', member['RvsdFlatSize']))
        flat_charges = float(request.form.get('flat_charges', member['flat_charges']))
        capital_fund = float(request.form.get('capital_fund', member['capital_fund']))
        common_expenses = float(request.form.get('common_expenses', member['common_expenses']))
        
        cps_owner = 1 if request.form.get('cps_owner') == '1' else 0
        cps_space = request.form.get('car_parking_space', member.get('car_parking_space', '-')).strip()
        cps_charges = float(request.form.get('cps_charges', member['cps_charges'])) if cps_owner else 0.0
        
        tws_owner = 1 if request.form.get('tws_owner') == '1' else 0
        tws_count = int(request.form.get('tws_count', member.get('tws_count', 0))) if tws_owner else 0
        tws_charges = float(request.form.get('tws_charges', member['tws_charges'])) if tws_owner else 0.0
        
        is_mysql = (determine_engine() == 'mysql')
        if is_mysql:
            execute_db(
                """UPDATE tbl_membership 
                   SET RvsdFlatSize = %s, car_parking_space = %s, cps_owner = %s, cps_charges = %s,
                       tws_owner = %s, tws_count = %s, tws_charges = %s,
                       flat_charges = %s, capital_fund = %s, common_expenses = %s
                   WHERE id = %s""",
                (sq_ft, cps_space, cps_owner, cps_charges, tws_owner, tws_count, tws_charges, flat_charges, capital_fund, common_expenses, member_id)
            )
        else:
            new_monthly = compute_flat_monthly_charge(sq_ft, flat_charges, capital_fund, common_expenses, cps_charges, tws_charges)
            execute_db(
                """UPDATE tbl_membership 
                   SET RvsdFlatSize = %s, car_parking_space = %s, cps_owner = %s, cps_charges = %s,
                       tws_owner = %s, tws_count = %s, tws_charges = %s,
                       flat_charges = %s, capital_fund = %s, common_expenses = %s, monthly_charge = %s
                   WHERE id = %s""",
                (sq_ft, cps_space, cps_owner, cps_charges, tws_owner, tws_count, tws_charges, flat_charges, capital_fund, common_expenses, new_monthly, member_id)
            )
            
        flash(f"Unit tariff updated successfully for Flat {member['flat_no']} ({member['member_name']})!", 'success')
    except Exception as e:
        flash(f"Error updating unit tariff: {e}", 'danger')
        
    return redirect(url_for('admin_billing_rates'))

# --- Digital Notice Board Routes ---
NOTICE_CATEGORIES = [
    ('ALL', 'All Notices', '📢'),
    ('GENERAL', 'General Circulars', '📄'),
    ('MAINTENANCE', 'Maintenance & Repairs', '⚡'),
    ('WATER_SUPPLY', 'Water & Utilities', '💧'),
    ('SECURITY', 'Security & Gate', '🛡️'),
    ('AGM_MEETING', 'AGM & Meetings', '🏛️'),
    ('EVENTS_FESTIVAL', 'Events & Puja', '🎉'),
    ('FINANCIAL', 'Accounts & Dues', '💰'),
    ('EMERGENCY', 'Urgent Alerts', '🚨')
]

MEETING_TYPES = [
    ('AGM', 'Annual General Meeting (AGM)', '🏛️'),
    ('GB', 'General Body Meeting (GB)', '👥'),
    ('SGB', 'Special General Body Meeting (SGB)', '📜'),
    ('GOVERNING_BODY', 'Governing Body Meeting', '🏛️'),
    ('EGM', 'Extraordinary General Meeting (EGM)', '🚨'),
    ('MANAGING_COMMITTEE', 'Managing / Executive Committee Meeting', '💼'),
    ('EMERGENCY', 'Emergency Meeting', '⚡'),
    ('CUSTOM', 'Custom Meeting Type...', '✍️')
]

@app.route('/notices')
@login_required
def notices_list():
    user = session.get('user', {})
    is_admin = bool(user.get('is_admin') or user.get('role') in ADMIN_ROLES)
    
    cat_filter = request.args.get('category', 'ALL').strip().upper()
    meeting_type_filter = request.args.get('meeting_type', 'ALL').strip()
    priority_filter = request.args.get('priority', 'ALL').strip().upper()
    search_q = request.args.get('q', '').strip()
    status_filter = request.args.get('status', 'ACTIVE').strip().upper()
    
    query = "SELECT * FROM tbl_notices WHERE 1=1"
    params = []
    
    if status_filter != 'ALL':
        query += " AND status = %s"
        params.append(status_filter)
        
    if cat_filter != 'ALL':
        query += " AND category = %s"
        params.append(cat_filter)

    if meeting_type_filter != 'ALL' and meeting_type_filter:
        query += " AND meeting_type = %s"
        params.append(meeting_type_filter)
        
    if priority_filter != 'ALL':
        query += " AND priority = %s"
        params.append(priority_filter)
        
    if search_q:
        query += " AND (title LIKE %s OR content LIKE %s OR posted_by LIKE %s OR meeting_type LIKE %s)"
        like_term = f"%{search_q}%"
        params.extend([like_term, like_term, like_term, like_term])
        
    query += " ORDER BY is_pinned DESC, (priority = 'URGENT') DESC, (priority = 'HIGH') DESC, id DESC"
    notices = query_db(query, params)
    
    # Calculate category counts for UI badges
    cat_counts = {}
    total_active = 0
    all_notices_raw = query_db("SELECT category, COUNT(*) as cnt FROM tbl_notices WHERE status = 'ACTIVE' GROUP BY category")
    for r in (all_notices_raw or []):
        cat_counts[r['category']] = r['cnt']
        total_active += r['cnt']
    cat_counts['ALL'] = total_active

    # Pinned urgent notices for top marquee / alert cards
    pinned_urgent = [n for n in (notices or []) if n.get('is_pinned') and n.get('priority') == 'URGENT']
    recipients_info = get_notice_email_recipients() if is_admin else None

    return render_template(
        'notices.html',
        notices=notices,
        categories=NOTICE_CATEGORIES,
        meeting_types=MEETING_TYPES,
        current_category=cat_filter,
        current_meeting_type=meeting_type_filter,
        current_priority=priority_filter,
        current_status=status_filter,
        search_q=search_q,
        cat_counts=cat_counts,
        pinned_urgent=pinned_urgent,
        recipients_info=recipients_info,
        is_admin=is_admin,
        now=datetime.now()
    )

@app.route('/api/notices/email-recipients', methods=['GET'])
@roles_required('super_admin', 'billing_admin', 'president', 'secretary', 'treasurer', 'caretaker')
def api_notice_email_recipients():
    info = get_notice_email_recipients()
    return jsonify({
        "success": True,
        "data": info
    })

@app.route('/notices/create', methods=['POST'])
@roles_required('super_admin', 'billing_admin', 'president', 'secretary', 'treasurer', 'caretaker')
def notices_create():
    user = session.get('user', {})
    title = request.form.get('title', '').strip()
    content = request.form.get('content', '').strip()
    category = request.form.get('category', 'GENERAL').strip().upper()
    priority = request.form.get('priority', 'NORMAL').strip().upper()
    is_pinned = 1 if request.form.get('is_pinned') == '1' else 0
    do_broadcast = (request.form.get('do_broadcast') == '1')
    do_whatsapp = (request.form.get('do_whatsapp') == '1')

    # Meeting Type Sub-Category resolution
    meeting_type_opt = request.form.get('meeting_type', '').strip()
    custom_meeting_type = request.form.get('custom_meeting_type', '').strip()
    meeting_date_raw = request.form.get('meeting_date', '').strip()
    if category == 'AGM_MEETING':
        if meeting_type_opt == 'CUSTOM':
            meeting_type = custom_meeting_type or 'Meeting'
        else:
            meeting_type = meeting_type_opt or 'AGM'
        meeting_date = meeting_date_raw or None
    else:
        meeting_type = None
        meeting_date = None

    if not title or not content:
        flash('Please provide both a Title and Content for the notice.', 'danger')
        return redirect(url_for('notices_list'))

    caller_role = request.form.get('caller_role', '').strip()
    custom_posted_by = request.form.get('posted_by', '').strip()
    custom_posted_by_role = request.form.get('posted_by_role', '').strip()

    official_presets = {
        'Treasurer': ('Mr. Swapnadeep Ganguly', 'Treasurer'),
        'President': ('Dr. Asit Kumar Bera', 'President'),
        'Secretary': ('Mr. Somenath Halder', 'Secretary'),
        'Caretaker': ('Mr. Sanjoy Chakraborty', 'Caretaker'),
        'Executive Committee': ('Executive Committee', 'Executive Committee')
    }

    if caller_role in official_presets and not custom_posted_by:
        posted_by, posted_by_role = official_presets[caller_role]
    elif custom_posted_by:
        posted_by = custom_posted_by
        posted_by_role = custom_posted_by_role or caller_role or 'Committee Official'
    else:
        posted_by = user.get('name') or user.get('username') or 'Executive Committee'
        posted_by_role = caller_role or user.get('role', 'Committee Official').replace('_', ' ').title()
    
    try:
        notice_id = execute_db(
            """INSERT INTO tbl_notices (title, content, category, meeting_type, meeting_date, priority, is_pinned, posted_by, posted_by_role, status)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'ACTIVE')""",
            (title, content, category, meeting_type, meeting_date, priority, is_pinned, posted_by, posted_by_role)
        )
        
        notice_dict = {
            'id': notice_id,
            'title': title,
            'content': content,
            'category': category,
            'meeting_type': meeting_type,
            'meeting_date': meeting_date,
            'priority': priority,
            'posted_by': posted_by,
            'posted_by_role': posted_by_role
        }

        broadcast_msg = ""
        if do_broadcast:
            res = broadcast_notice_email(notice_dict, author_name=posted_by)
            broadcast_msg += f" • Email dispatched to {res.get('recipients_count', 'all')} inboxes."
            
        if do_whatsapp:
            base_url = get_app_base_url()
            wa_text = format_notice_whatsapp_message(notice_dict, base_url=base_url)
            log_whatsapp_dispatch('ALL_RESIDENTS', 'Broadcast / Society Group', title, 'NOTICE_BROADCAST', wa_text, 'LINK_GENERATED', sent_by=posted_by)
            broadcast_msg += " • WhatsApp Broadcast draft created."
            
        log_activity('NOTICE_PUBLISHED', f"Published official notice #{notice_id}: '{title}' by {posted_by} ({posted_by_role})")
        flash(f"📢 Official notice '{title}' published by {posted_by} ({posted_by_role}) successfully!{broadcast_msg}", 'success')
    except Exception as e:
        flash(f"Error publishing notice: {e}", 'danger')
        
    return redirect(url_for('notices_list'))

@app.route('/notices/<int:notice_id>/edit', methods=['POST'])
@roles_required('super_admin', 'billing_admin', 'president', 'secretary', 'treasurer', 'caretaker')
def notices_edit(notice_id):
    title = request.form.get('title', '').strip()
    content = request.form.get('content', '').strip()
    category = request.form.get('category', 'GENERAL').strip().upper()
    priority = request.form.get('priority', 'NORMAL').strip().upper()
    status = request.form.get('status', 'ACTIVE').strip().upper()
    is_pinned = 1 if request.form.get('is_pinned') == '1' else 0

    # Meeting Type Sub-Category resolution
    meeting_type_opt = request.form.get('meeting_type', '').strip()
    custom_meeting_type = request.form.get('custom_meeting_type', '').strip()
    meeting_date_raw = request.form.get('meeting_date', '').strip()
    if category == 'AGM_MEETING':
        if meeting_type_opt == 'CUSTOM':
            meeting_type = custom_meeting_type or 'Meeting'
        else:
            meeting_type = meeting_type_opt or 'AGM'
        meeting_date = meeting_date_raw or None
    else:
        meeting_type = None
        meeting_date = None
    
    caller_role = request.form.get('caller_role', '').strip()
    custom_posted_by = request.form.get('posted_by', '').strip()
    custom_posted_by_role = request.form.get('posted_by_role', '').strip()

    official_presets = {
        'Treasurer': ('Mr. Swapnadeep Ganguly', 'Treasurer'),
        'President': ('Dr. Asit Kumar Bera', 'President'),
        'Secretary': ('Mr. Somenath Halder', 'Secretary'),
        'Caretaker': ('Mr. Sanjoy Chakraborty', 'Caretaker'),
        'Executive Committee': ('Executive Committee', 'Executive Committee')
    }

    if caller_role in official_presets and not custom_posted_by:
        posted_by, posted_by_role = official_presets[caller_role]
    elif custom_posted_by:
        posted_by = custom_posted_by
        posted_by_role = custom_posted_by_role or caller_role or 'Committee Official'
    else:
        posted_by = None
        posted_by_role = None

    if not title or not content:
        flash('Please provide both a Title and Content for the notice.', 'danger')
        return redirect(url_for('notices_list'))
        
    try:
        if posted_by and posted_by_role:
            execute_db(
                """UPDATE tbl_notices 
                   SET title = %s, content = %s, category = %s, meeting_type = %s, meeting_date = %s, priority = %s, is_pinned = %s, status = %s,
                       posted_by = %s, posted_by_role = %s, updated_at = CURRENT_TIMESTAMP
                   WHERE id = %s""",
                (title, content, category, meeting_type, meeting_date, priority, is_pinned, status, posted_by, posted_by_role, notice_id)
            )
        else:
            execute_db(
                """UPDATE tbl_notices 
                   SET title = %s, content = %s, category = %s, meeting_type = %s, meeting_date = %s, priority = %s, is_pinned = %s, status = %s, updated_at = CURRENT_TIMESTAMP
                   WHERE id = %s""",
                (title, content, category, meeting_type, meeting_date, priority, is_pinned, status, notice_id)
            )
        log_activity('NOTICE_UPDATED', f"Updated official notice #{notice_id}: '{title}'")
        flash(f"Notice #{notice_id} updated successfully.", 'success')
    except Exception as e:
        flash(f"Error updating notice: {e}", 'danger')
        
    return redirect(url_for('notices_list'))

@app.route('/notices/<int:notice_id>/toggle-pin', methods=['POST'])
@roles_required('super_admin', 'billing_admin', 'president', 'secretary', 'treasurer', 'caretaker')
def notices_toggle_pin(notice_id):
    try:
        notice = query_db("SELECT is_pinned, title FROM tbl_notices WHERE id = %s", (notice_id,), one=True)
        if notice:
            new_pin = 0 if notice['is_pinned'] else 1
            execute_db("UPDATE tbl_notices SET is_pinned = %s WHERE id = %s", (new_pin, notice_id))
            status_text = "pinned to dashboard" if new_pin else "unpinned"
            flash(f"Notice '{notice['title']}' is now {status_text}.", 'info')
        else:
            flash("Notice not found.", 'danger')
    except Exception as e:
        flash(f"Error updating pin state: {e}", 'danger')
    return redirect(url_for('notices_list'))

@app.route('/notices/<int:notice_id>/delete', methods=['POST'])
@roles_required('super_admin', 'billing_admin', 'president', 'secretary', 'treasurer', 'caretaker')
def notices_delete(notice_id):
    try:
        execute_db("DELETE FROM tbl_notices WHERE id = %s", (notice_id,))
        log_activity('NOTICE_DELETED', f"Deleted notice #{notice_id}")
        flash(f"Notice #{notice_id} was removed successfully.", 'info')
    except Exception as e:
        flash(f"Error deleting notice: {e}", 'danger')
    return redirect(url_for('notices_list'))

@app.route('/notices/<int:notice_id>/broadcast', methods=['POST'])
@roles_required('super_admin', 'billing_admin', 'president', 'secretary', 'treasurer', 'caretaker')
def notices_broadcast(notice_id):
    try:
        notice = query_db("SELECT * FROM tbl_notices WHERE id = %s", (notice_id,), one=True)
        if not notice:
            flash("Notice not found.", 'danger')
            return redirect(url_for('notices_list'))
        user = session.get('user', {})
        res = broadcast_notice_email(notice, author_name=user.get('name'))
        log_activity('NOTICE_BROADCAST', f"Broadcast notice #{notice_id} ('{notice['title']}') to resident emails")
        flash(f"📢 {res.get('message', 'Notice broadcast sent successfully!')}", 'success')
    except Exception as e:
        flash(f"Error broadcasting notice: {e}", 'danger')
    return redirect(url_for('notices_list'))

@app.route('/notices/<int:notice_id>/whatsapp-broadcast', methods=['GET', 'POST'])
@login_required
def notices_whatsapp_broadcast(notice_id):
    user = session.get('user', {})
    is_admin = bool(user.get('is_admin') or user.get('role') in ADMIN_ROLES)
    is_ajax = bool(
        request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 
        request.is_json or 
        'application/json' in request.headers.get('Accept', '')
    )
    
    notice = query_db("SELECT * FROM tbl_notices WHERE id = %s", (notice_id,), one=True)
    if not notice:
        if is_ajax:
            return jsonify({"success": False, "message": "Notice not found."}), 404
        flash("Notice not found.", 'danger')
        return redirect(url_for('notices_list'))
        
    base_url = get_app_base_url()
    formatted_msg = format_notice_whatsapp_message(notice, base_url=base_url)
    
    custom_phone = request.args.get('phone') or (request.get_json(silent=True) or {}).get('phone') or request.form.get('phone')
    direct_url = build_whatsapp_url(custom_phone, formatted_msg)
    
    log_whatsapp_dispatch(
        recipient_flat='ALL_RESIDENTS' if not custom_phone else 'INDIVIDUAL',
        recipient_phone=custom_phone or 'Broadcast / Society Group',
        recipient_name=notice.get('title', ''),
        message_type='NOTICE_BROADCAST',
        message_content=formatted_msg,
        status='LINK_GENERATED',
        sent_by=user.get('name') or user.get('username') or 'Admin'
    )
    
    log_activity('WHATSAPP_NOTICE', f"Generated WhatsApp broadcast link for Notice #{notice_id}: '{notice['title']}'")
    
    if is_ajax:
        return jsonify({
            "success": True,
            "notice_id": notice_id,
            "title": notice['title'],
            "direct_url": direct_url,
            "message_text": formatted_msg
        }), 200
        
    return redirect(direct_url)

# --- Universal WhatsApp Live Preview & Quick Chat API ---
@app.route('/api/whatsapp/preview')
@login_required
def api_whatsapp_preview():
    item_type = request.args.get('type', '').strip().lower() # 'receipt', 'penalty', 'notice', 'custom'
    item_id = request.args.get('id', '').strip()
    flat_no = request.args.get('flat', '').strip()
    base_url = get_app_base_url()
    
    if item_type == 'receipt' and item_id:
        receipt = query_db("SELECT * FROM tbl_receipts WHERE receipt_no = %s", (item_id,), one=True)
        if not receipt:
            return jsonify({'success': False, 'message': 'Receipt not found'}), 404
        member_info = query_db("SELECT * FROM tbl_membership WHERE flat_no = %s", (receipt['flat_no'],), one=True)
        contact_info = query_db("SELECT * FROM tbl_mbr_cntct WHERE flat_no = %s", (receipt['flat_no'],), one=True)
        msg = format_receipt_whatsapp_message(receipt, member_info, contact_info, base_url=base_url)
        phone = (contact_info.get('mobile_num_1') or contact_info.get('mobile_num_2')) if contact_info else ''
        return jsonify({
            'success': True,
            'message_text': msg,
            'phone': phone,
            'clean_phone': normalize_whatsapp_phone(phone),
            'direct_url': build_whatsapp_url(phone, msg)
        })
        
    elif item_type == 'penalty' and flat_no:
        member = query_db("SELECT * FROM tbl_membership WHERE flat_no = %s", (flat_no,), one=True)
        contact = query_db("SELECT * FROM tbl_mbr_cntct WHERE flat_no = %s", (flat_no,), one=True)
        calc = calculate_flat_penalty(flat_no, member=member)
        msg = format_dues_reminder_whatsapp_message(calc, contact_info=contact, base_url=base_url)
        phone = (contact.get('mobile_num_1') or contact.get('mobile_num_2')) if contact else ''
        return jsonify({
            'success': True,
            'message_text': msg,
            'phone': phone,
            'clean_phone': normalize_whatsapp_phone(phone),
            'direct_url': build_whatsapp_url(phone, msg)
        })
        
    elif item_type == 'notice' and item_id:
        notice = query_db("SELECT * FROM tbl_notices WHERE id = %s", (item_id,), one=True)
        if not notice:
            return jsonify({'success': False, 'message': 'Notice not found'}), 404
        msg = format_notice_whatsapp_message(notice, base_url=base_url)
        return jsonify({
            'success': True,
            'message_text': msg,
            'phone': '',
            'direct_url': build_whatsapp_url('', msg)
        })
        
    return jsonify({'success': False, 'message': 'Invalid preview parameters'}), 400

@app.route('/admin/whatsapp-logs')
@roles_required('super_admin', 'billing_admin', 'president', 'secretary', 'treasurer', 'caretaker')
def admin_whatsapp_logs():
    logs = query_db("SELECT * FROM tbl_whatsapp_logs ORDER BY id DESC LIMIT 150") or []
    return jsonify({
        "success": True,
        "count": len(logs),
        "logs": logs
    })

@app.route('/notices/<int:notice_id>/view')
@login_required
def notices_view(notice_id):
    notice = query_db("SELECT * FROM tbl_notices WHERE id = %s", (notice_id,), one=True)
    if not notice:
        abort(404, description="Notice not found")
    return render_template('notice_single.html', notice=notice)

if __name__ == '__main__':
    init_db()
    print("Starting SDDRA Billing & Residents' Association Web Portal on http://127.0.0.1:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)
