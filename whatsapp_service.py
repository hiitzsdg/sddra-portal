import re
import urllib.parse
import json
import urllib.request
import urllib.error
from datetime import datetime
from config import Config
from database import query_db, execute_db

def normalize_whatsapp_phone(phone_raw, default_country=None):
    """
    Sanitize and format phone number into E.164 digits without leading '+' or special chars.
    Handles Indian mobile formats:
      - '+91-801-725-0621' -> '918017250621'
      - '09830012345' -> '919830012345'
      - '9830012345' -> '919830012345'
      - '919830012345' -> '919830012345'
    """
    if not phone_raw:
        return ''
    
    country = str(default_country or getattr(Config, 'WHATSAPP_DEFAULT_COUNTRY_CODE', '91')).strip()
    
    # Strip all non-digit characters
    digits = re.sub(r'\D', '', str(phone_raw))
    
    if not digits:
        return ''
        
    # If starts with leading 0 (e.g. 09830012345 in India), strip leading 0
    if digits.startswith('0') and len(digits) == 11:
        digits = digits[1:]
        
    # If 10 digits standard mobile number, prepend country code
    if len(digits) == 10:
        digits = country + digits
    elif len(digits) == 12 and digits.startswith(country):
        pass # Already standard 12-digit e.g. 919830012345
    elif digits.startswith('00'):
        digits = digits[2:]
        
    return digits

def build_whatsapp_url(phone_raw, message_text):
    """
    Generate standard universal WhatsApp Web / App deep-link (wa.me).
    Works seamlessly on Desktop, iOS, and Android.
    """
    clean_phone = normalize_whatsapp_phone(phone_raw)
    encoded_text = urllib.parse.quote(message_text or '')
    
    if clean_phone:
        return f"https://wa.me/{clean_phone}?text={encoded_text}"
    else:
        # Broadcast/Share link without target phone
        return f"https://api.whatsapp.com/send?text={encoded_text}"

def format_receipt_whatsapp_message(receipt, member_info=None, contact_info=None, base_url=""):
    """
    Generate clean, professional WhatsApp receipt confirmation in WhatsApp Markdown.
    """
    raw_rcpt_no = str(receipt.get('receipt_no', 'N/A'))
    formatted_rcpt = f"SDERA_{raw_rcpt_no}" if not raw_rcpt_no.startswith('SDERA_') else raw_rcpt_no
    member_name = receipt.get('member_name') or (member_info.get('member_name') if member_info else 'Resident')
    flat_no = receipt.get('flat_no', 'N/A')
    amount = float(receipt.get('amount', 0.0) or 0.0)
    payment_date = str(receipt.get('payment_date') or receipt.get('receipt_date') or datetime.now().strftime('%Y-%m-%d'))
    mode = str(receipt.get('pymnt_mode', 'Online UPI'))
    period = receipt.get('remarks') or f"{receipt.get('coverage_start', '')} to {receipt.get('coverage_end', '')}" or 'Monthly Maintenance'
    sub_type = receipt.get('subscription_type', 'Monthly Subscription')
    
    if not base_url:
        base_url = "http://127.0.0.1:5000"
    base_url = base_url.rstrip('/')
    
    receipt_view_url = f"{base_url}/receipts/{raw_rcpt_no}"
    receipt_pdf_url = f"{base_url}/receipts/{raw_rcpt_no}/pdf"

    msg = (
        f"🏛️ *{Config.ASSOCIATION_NAME}*\n"
        f"📜 *OFFICIAL PAYMENT RECEIPT*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🧾 *Receipt No:* `{formatted_rcpt}`\n"
        f"👤 *Resident Name:* {member_name}\n"
        f"🏠 *Flat Number:* Flat {flat_no}\n"
        f"💰 *Amount Received:* ₹ {amount:,.2f}\n"
        f"📅 *Payment Date:* {payment_date}\n"
        f"💳 *Payment Mode:* {mode}\n"
        f"📂 *Subscription:* {sub_type}\n"
        f"🗓️ *Period / Remarks:* {period}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📄 *Download Official PDF Voucher:*\n"
        f"{receipt_pdf_url}\n\n"
        f"🌐 *View Digital Receipt:* {receipt_view_url}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"_Thank you for your prompt payment towards society maintenance!_\n"
        f"📞 *Office Support:* {Config.ASSOCIATION_PHONE}"
    )
    return msg

def format_dues_reminder_whatsapp_message(calc, contact_info=None, base_url=""):
    """
    Generate clear, transparent WhatsApp overdue dues & penalty reminder.
    """
    flat_no = calc.get('flat_no', '-')
    member_name = calc.get('member_name', 'Resident')
    overdue_months = int(calc.get('overdue_months', 0))
    monthly_charge = float(calc.get('monthly_charge', 0.0))
    base_due = float(calc.get('base_due', 0.0))
    penalty_amount = float(calc.get('penalty_amount', 0.0))
    total_due = float(calc.get('total_due', 0.0))
    as_of_full = calc.get('as_of_full') or calc.get('as_of_display') or datetime.now().strftime('%B %Y')
    last_covered = calc.get('coverage_display') or 'None'
    
    if not base_url:
        base_url = "http://127.0.0.1:5000"
    base_url = base_url.rstrip('/')
    
    portal_url = f"{base_url}/dashboard"

    msg = (
        f"🏛️ *{Config.ASSOCIATION_NAME}*\n"
        f"⚠️ *MAINTENANCE DUES & LATE FEE NOTICE*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 *Resident Name:* {member_name}\n"
        f"🏠 *Unit:* Flat {flat_no}\n"
        f"📅 *Calculated As Of:* {as_of_full}\n"
        f"🗓️ *Last Paid Coverage:* {last_covered}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 *Dues Breakdown:*\n"
        f"• *Overdue Period:* {overdue_months} Month{'s' if overdue_months > 1 else ''}\n"
        f"• *Monthly Tariff:* ₹ {monthly_charge:,.2f}\n"
        f"• *Base Maintenance Due:* ₹ {base_due:,.2f}\n"
        f"• *Late Penalty Accrued:* ₹ {penalty_amount:,.2f}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔴 *TOTAL OUTSTANDING PAYABLE:* *₹ {total_due:,.2f}*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💳 *Quick Payment Options:*\n"
        f"• *UPI ID:* `sddra.association@icici`\n"
        f"• *Bank:* State Bank of India | *A/C:* `38290192831` | *IFSC:* `SBIN0001234`\n"
        f"• *Portal:* {portal_url}\n\n"
        f"_Kindly clear the outstanding dues to avoid further progressive late penalties (N*(N+1)/2 * ₹100)._\n\n"
        f"📞 *Enquiries / Clarifications:* {Config.ASSOCIATION_PHONE} ({Config.ASSOCIATION_EMAIL})"
    )
    return msg

def format_notice_whatsapp_message(notice, base_url=""):
    """
    Generate formatted official circular broadcast for WhatsApp society distribution.
    """
    notice_id = notice.get('id', '')
    title = notice.get('title', 'Official Circular')
    content = notice.get('content', '')
    category = notice.get('category', 'GENERAL').replace('_', ' ').title()
    priority = notice.get('priority', 'NORMAL').upper()
    posted_by = notice.get('posted_by', 'Executive Committee')
    posted_by_role = notice.get('posted_by_role', 'Committee Official')
    date_str = str(notice.get('created_at', datetime.now().strftime('%Y-%m-%d')))[:10]
    
    prio_emoji = "🚨 *URGENT ALERT*" if priority == 'URGENT' else ("⚡ *HIGH PRIORITY*" if priority == 'HIGH' else "📢 *OFFICIAL NOTICE*")
    
    if not base_url:
        base_url = "http://127.0.0.1:5000"
    base_url = base_url.rstrip('/')
    
    notice_url = f"{base_url}/notices/{notice_id}/view" if notice_id else f"{base_url}/notices"

    # Truncate content for WhatsApp preview if very long
    content_clean = content.strip()
    if len(content_clean) > 500:
        content_preview = content_clean[:490] + "...\n_(Continued in official document link below)_"
    else:
        content_preview = content_clean

    msg = (
        f"🏛️ *{Config.ASSOCIATION_NAME}*\n"
        f"{prio_emoji}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 *{title}*\n"
        f"📂 *Category:* {category} | 📅 *Date:* {date_str}\n"
        f"✍️ *Issued By:* {posted_by} ({posted_by_role})\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{content_preview}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔗 *Read Full Circular & Letterhead Document:*\n"
        f"{notice_url}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"_{Config.ASSOCIATION_NAME} • Dum Dum, Kolkata_"
    )
    return msg

def log_whatsapp_dispatch(recipient_flat, recipient_phone, recipient_name, message_type, message_content, status, error_message=None, sent_by='System'):
    """
    Record an entry in tbl_whatsapp_logs.
    """
    try:
        execute_db(
            """INSERT INTO tbl_whatsapp_logs (recipient_flat, recipient_phone, recipient_name, message_type, message_content, status, error_message, sent_by, sent_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                recipient_flat or '-',
                recipient_phone or '',
                recipient_name or '',
                message_type or 'GENERIC',
                message_content or '',
                status or 'LINK_GENERATED',
                error_message,
                sent_by or 'System',
                datetime.now()
            )
        )
    except Exception as e:
        print(f"[WhatsApp Service] Could not write audit log: {e}")

def send_whatsapp_message(phone_raw, message_text, msg_type='GENERIC', recipient_flat='-', recipient_name='', sent_by='System', base_url=""):
    """
    Dispatch WhatsApp message via Meta Cloud API / Twilio if configured, or generate instant wa.me link.
    Logs the action into tbl_whatsapp_logs.
    """
    clean_phone = normalize_whatsapp_phone(phone_raw)
    direct_url = build_whatsapp_url(phone_raw, message_text)
    
    # 1. Check if Meta WhatsApp Cloud API is configured
    api_token = getattr(Config, 'WHATSAPP_API_TOKEN', '')
    phone_number_id = getattr(Config, 'WHATSAPP_PHONE_NUMBER_ID', '')
    
    if api_token and phone_number_id and clean_phone:
        try:
            url = f"https://graph.facebook.com/v19.0/{phone_number_id}/messages"
            headers = {
                "Authorization": f"Bearer {api_token}",
                "Content-Type": "application/json"
            }
            payload = {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": clean_phone,
                "type": "text",
                "text": {"preview_url": True, "body": message_text}
            }
            req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                resp_data = json.loads(resp.read().decode('utf-8'))
                log_whatsapp_dispatch(recipient_flat, clean_phone, recipient_name, msg_type, message_text, 'DISPATCHED_API', sent_by=sent_by)
                return {
                    "success": True,
                    "mode": "api",
                    "provider": "meta_cloud_api",
                    "direct_url": direct_url,
                    "response": resp_data,
                    "message": f"WhatsApp message successfully dispatched to +{clean_phone} via Meta Cloud API."
                }
        except Exception as err:
            err_msg = str(err)
            log_whatsapp_dispatch(recipient_flat, clean_phone, recipient_name, msg_type, message_text, 'API_FAILED', error_message=err_msg, sent_by=sent_by)
            return {
                "success": False,
                "mode": "direct_link",
                "direct_url": direct_url,
                "error": err_msg,
                "message": f"API dispatch failed ({err_msg}). Falling back to instant WhatsApp link."
            }

    # 2. Check if Twilio is configured
    twilio_sid = getattr(Config, 'TWILIO_ACCOUNT_SID', '')
    twilio_token = getattr(Config, 'TWILIO_AUTH_TOKEN', '')
    twilio_from = getattr(Config, 'TWILIO_WHATSAPP_NUMBER', '')
    
    if twilio_sid and twilio_token and twilio_from and clean_phone:
        try:
            # Twilio dispatch via urllib basic auth
            import base64
            url = f"https://api.twilio.com/2010-04-01/Accounts/{twilio_sid}/Messages.json"
            auth_str = f"{twilio_sid}:{twilio_token}"
            b64_auth = base64.b64encode(auth_str.encode('utf-8')).decode('utf-8')
            headers = {
                "Authorization": f"Basic {b64_auth}",
                "Content-Type": "application/x-www-form-urlencoded"
            }
            post_data = urllib.parse.urlencode({
                "From": twilio_from if twilio_from.startswith('whatsapp:') else f"whatsapp:{twilio_from}",
                "To": f"whatsapp:+{clean_phone}",
                "Body": message_text
            }).encode('utf-8')
            req = urllib.request.Request(url, data=post_data, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                resp_data = json.loads(resp.read().decode('utf-8'))
                log_whatsapp_dispatch(recipient_flat, clean_phone, recipient_name, msg_type, message_text, 'DISPATCHED_API', sent_by=sent_by)
                return {
                    "success": True,
                    "mode": "api",
                    "provider": "twilio",
                    "direct_url": direct_url,
                    "response": resp_data,
                    "message": f"WhatsApp message successfully dispatched to +{clean_phone} via Twilio."
                }
        except Exception as err:
            err_msg = str(err)
            log_whatsapp_dispatch(recipient_flat, clean_phone, recipient_name, msg_type, message_text, 'API_FAILED', error_message=err_msg, sent_by=sent_by)

    # 3. Default: Instant One-Click wa.me Direct Link
    log_whatsapp_dispatch(recipient_flat, clean_phone or 'Direct Link', recipient_name, msg_type, message_text, 'LINK_GENERATED', sent_by=sent_by)
    return {
        "success": True,
        "mode": "direct_link",
        "direct_url": direct_url,
        "phone": clean_phone,
        "message": "WhatsApp direct message link ready."
    }

def get_whatsapp_committee_contacts():
    """
    Fetch official WhatsApp helplines for society committee and caretaker.
    """
    contacts = [
        {
            "role": "Caretaker / Estate Office",
            "name": "Mr. Sanjoy Chakraborty",
            "phone": getattr(Config, 'CARETAKER_PHONE', '+91-983-000-1122'),
            "clean_phone": normalize_whatsapp_phone(getattr(Config, 'CARETAKER_PHONE', '9830001122')),
            "purpose": "Maintenance queries, emergency water/lift issues, gate passes",
            "icon": "🔧"
        },
        {
            "role": "General Secretary",
            "name": "Mr. Somenath Halder",
            "phone": getattr(Config, 'SECRETARY_PHONE', '+91-983-111-2233'),
            "clean_phone": normalize_whatsapp_phone(getattr(Config, 'SECRETARY_PHONE', '9831112233')),
            "purpose": "Administrative requests, AGM items, official circulars",
            "icon": "📜"
        },
        {
            "role": "Treasurer",
            "name": "Mr. Swapnadeep Ganguly",
            "phone": getattr(Config, 'TREASURER_PHONE', '+91-801-725-0621'),
            "clean_phone": normalize_whatsapp_phone(getattr(Config, 'TREASURER_PHONE', '8017250621')),
            "purpose": "Subscription billing, receipt verification, online payment queries",
            "icon": "💰"
        },
        {
            "role": "President",
            "name": "Dr. Asit Kumar Bera",
            "phone": getattr(Config, 'PRESIDENT_PHONE', '+91-983-222-3344'),
            "clean_phone": normalize_whatsapp_phone(getattr(Config, 'PRESIDENT_PHONE', '9832223344')),
            "purpose": "Association policy, disputes, resident welfare",
            "icon": "🏛️"
        }
    ]
    
    for c in contacts:
        prefill_text = f"Hello {c['name']} ({c['role']}), I am contacting you from South Dumdum Enclave regarding..."
        c['direct_url'] = build_whatsapp_url(c['clean_phone'], prefill_text)
        
    return contacts
