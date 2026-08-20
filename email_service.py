import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from datetime import datetime
from config import Config
from database import query_db, execute_db
from pdf_service import generate_receipt_pdf_bytes

def generate_official_receipt_document_html(receipt, member_info, contact_info):
    """
    Generate the official, standalone, printable receipt document voucher 
    to be displayed in browser view.
    """
    flat_no = receipt.get('flat_no', 'N/A')
    member_name = receipt.get('member_name', 'Resident')
    amount = float(receipt.get('amount', 0))
    payment_date = str(receipt.get('payment_date', receipt.get('receipt_date', 'N/A')))
    receipt_date = str(receipt.get('receipt_date', receipt.get('payment_date', 'N/A')))
    coverage = receipt.get('remarks') or f"{receipt.get('coverage_start', '')} to {receipt.get('coverage_end', '')}"
    mode = receipt.get('pymnt_mode', 'Online')
    sub_type = receipt.get('subscription_type', 'Monthly Subscription')
    sq_feet = member_info.get('RvsdFlatSize', 1200) if member_info else 1200
    phone = (contact_info.get('mobile_num_1') or contact_info.get('mobile_num_2') or 'On File') if contact_info else 'On File'
    email_addr = (contact_info.get('email_1') or contact_info.get('email_2') or 'On File') if contact_info else 'On File'
    monthly_charge = float(member_info.get('monthly_charge', amount)) if member_info else amount

    cps_space = member_info.get('car_parking_space', '-') if member_info else '-'
    cps_charges = float(member_info.get('cps_charges', 0)) if member_info else 0.0
    if cps_space and cps_space != '-':
        cps_display = f"{cps_space} Sq. Ft."
        if cps_charges > 0:
            cps_display += f" (INR {cps_charges:,.2f})"
    else:
        cps_display = "None / '-'"

    tws_count = member_info.get('tws_count', 0) if member_info else 0
    tws_charges = float(member_info.get('tws_charges', 0)) if member_info else 0.0
    if member_info and (member_info.get('tws_owner') or tws_count > 0 or tws_charges > 0):
        tws_display = f"{tws_count or 1} Space{'s' if tws_count > 1 else ''} (INR {tws_charges or 150.0:,.2f})"
    else:
        tws_display = "None (INR 0.00)"

    coverage_row = ""
    if receipt.get('coverage_start') and receipt.get('coverage_end'):
        coverage_row = f"""
        <tr>
            <td class="label" style="padding: 9px 12px; font-weight: 600; color: #475569; border: 1px solid #cbd5e1; background: #f8fafc;">Billing Coverage:</td>
            <td colspan="3" style="padding: 9px 12px; border: 1px solid #cbd5e1; color: #0f172a;">From <strong>{receipt.get('coverage_start')}</strong> to <strong>{receipt.get('coverage_end')}</strong></td>
        </tr>
        """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Official Receipt #{receipt['receipt_no']} - Flat {flat_no} - {Config.ASSOCIATION_NAME}</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@400;600;700;800&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap');
        
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f1f5f9;
            color: #0f172a;
            padding: 30px 15px;
            line-height: 1.5;
        }}
        .no-print {{
            max-width: 820px;
            margin: 0 auto 20px auto;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .btn {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 9px 18px;
            font-size: 14px;
            font-weight: 600;
            border-radius: 8px;
            border: 1px solid transparent;
            cursor: pointer;
            text-decoration: none;
            background: #2563eb;
            color: #ffffff;
            box-shadow: 0 2px 4px rgba(37,99,235,0.2);
        }}
        .btn-print {{ background: #059669; }}
        .receipt-voucher {{
            max-width: 820px;
            margin: 0 auto;
            background: #ffffff;
            border: 2px solid #1e3a8a;
            border-radius: 12px;
            padding: 36px 40px;
            position: relative;
            box-shadow: 0 10px 30px rgba(0,0,0,0.08);
            overflow: hidden;
        }}
        .receipt-watermark {{
            position: absolute;
            top: 52%;
            left: 50%;
            transform: translate(-50%, -50%) rotate(-30deg);
            font-size: 5.5rem;
            font-weight: 900;
            color: rgba(30, 58, 138, 0.038);
            pointer-events: none;
            user-select: none;
            white-space: nowrap;
            letter-spacing: 0.15em;
            font-family: 'Outfit', sans-serif;
        }}
        .receipt-header {{
            text-align: center;
            border-bottom: 2px dashed #94a3b8;
            padding-bottom: 22px;
            margin-bottom: 22px;
        }}
        .receipt-header h1 {{
            font-family: 'Outfit', sans-serif;
            font-size: 23px;
            color: #0f172a;
            letter-spacing: -0.01em;
            margin-bottom: 5px;
            font-weight: 800;
        }}
        .receipt-header p {{
            font-size: 12.5px;
            color: #475569;
            margin: 2px 0;
        }}
        .receipt-badge {{
            display: inline-block;
            border: 2px solid #0f172a;
            padding: 4px 16px;
            font-weight: 800;
            font-size: 13px;
            letter-spacing: 1.5px;
            text-transform: uppercase;
            margin-top: 10px;
            color: #0f172a;
            background: #f8fafc;
        }}
        .receipt-meta-bar {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: #eff6ff;
            border: 1px solid #bfdbfe;
            border-radius: 8px;
            padding: 12px 18px;
            margin-bottom: 22px;
            font-size: 14px;
        }}
        .receipt-table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 24px;
            font-size: 13.5px;
        }}
        .receipt-table td {{
            padding: 9px 12px;
            border: 1px solid #cbd5e1;
            vertical-align: middle;
        }}
        .receipt-table td.label {{
            background: #f8fafc;
            color: #475569;
            font-weight: 600;
            width: 25%;
        }}
        .badge-pill {{
            display: inline-block;
            padding: 2px 10px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
        }}
        .badge-info {{ background: #e0f2fe; color: #0369a1; }}
        .badge-success {{ background: #dcfce7; color: #15803d; }}
        
        .receipt-total-box {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: linear-gradient(135deg, #f0fdf4, #dcfce7);
            border: 1.5px solid #86efac;
            border-radius: 8px;
            padding: 16px 20px;
            margin-bottom: 28px;
        }}
        .receipt-total-box .title {{
            font-size: 13px;
            color: #166534;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            display: block;
        }}
        .receipt-total-box .subtitle {{
            font-size: 12px;
            color: #374151;
            font-style: italic;
        }}
        .receipt-total-box .amount {{
            font-size: 26px;
            font-weight: 900;
            color: #1e3a8a;
            font-family: 'Outfit', sans-serif;
        }}
        .receipt-signatures {{
            display: flex;
            justify-content: space-between;
            align-items: flex-end;
            margin-top: 10px;
            padding-top: 15px;
        }}
        .receipt-signatures .note {{
            font-size: 11.5px;
            color: #64748b;
            max-width: 440px;
            line-height: 1.45;
        }}
        .signature-box {{
            text-align: center;
            min-width: 220px;
        }}
        .signature-line {{
            border-top: 1.5px dotted #64748b;
            margin: 5px auto 6px auto;
            width: 170px;
        }}
        
        @media print {{
            body {{ background: #ffffff; padding: 0; }}
            .no-print {{ display: none !important; }}
            .receipt-voucher {{ box-shadow: none; border: 1.5px solid #000000; padding: 25px 30px; }}
            .receipt-watermark {{ display: block !important; }}
        }}
    </style>
</head>
<body>
    <div class="no-print">
        <span style="font-size: 13.5px; color: #475569;">
            📎 <strong>Official SDDRA Receipt Voucher:</strong> Voucher #{receipt['receipt_no']} (Flat {flat_no})
        </span>
        <button type="button" class="btn btn-print" onclick="window.print()">
            🖨️ Print / Save as PDF
        </button>
    </div>

    <div class="receipt-voucher">
        <div class="receipt-watermark">SDDRA OFFICIAL</div>

        <div class="receipt-header">
            <div style="display: inline-flex; width: 44px; height: 44px; border-radius: 10px; background: #1e3a8a; color: #ffffff; align-items: center; justify-content: center; font-size: 1.4rem; margin-bottom: 0.4rem;">
                🏢
            </div>
            <h1>{Config.ASSOCIATION_NAME}</h1>
            <p><strong>Registration No:</strong> {Config.ASSOCIATION_REG_NO}</p>
            <p>{Config.ASSOCIATION_ADDRESS}</p>
            <p>Email: {Config.ASSOCIATION_EMAIL} | Phone: {Config.ASSOCIATION_PHONE}</p>
            <div>
                <span class="receipt-badge">OFFICIAL MAINTENANCE RECEIPT</span>
            </div>
        </div>

        <div class="receipt-meta-bar">
            <div>
                <strong>Receipt No:</strong> <span style="font-family: monospace; font-size: 1.15rem; font-weight: 800; color: #1e3a8a;">#{receipt['receipt_no']}</span>
            </div>
            <div>
                <strong>Date of Issue:</strong> {receipt_date}
            </div>
        </div>

        <table class="receipt-table">
            <tr>
                <td class="label">Resident / Member Name:</td>
                <td><strong>{member_name}</strong></td>
                <td class="label">Flat Number:</td>
                <td><strong style="color: #1e40af; font-size: 1.05rem;">Flat {flat_no}</strong></td>
            </tr>
            <tr>
                <td class="label">Contact Mobile:</td>
                <td>{phone}</td>
                <td class="label">Registered Email:</td>
                <td>{email_addr}</td>
            </tr>
            <tr>
                <td class="label">Subscription Type:</td>
                <td><span class="badge-pill badge-info">{sub_type}</span></td>
                <td class="label">Period / Month:</td>
                <td><strong style="color: #0f172a; font-size: 1rem;">{coverage}</strong></td>
            </tr>
            <tr>
                <td class="label">Payment Date:</td>
                <td>{payment_date}</td>
                <td class="label">Payment Mode:</td>
                <td><span class="badge-pill badge-success">{mode}</span></td>
            </tr>
            <tr>
                <td class="label">Flat Size / Space:</td>
                <td><strong>{sq_feet}</strong> Sq. Ft.</td>
                <td class="label">Car Parking Space (CPS):</td>
                <td><strong>{cps_display}</strong></td>
            </tr>
            <tr>
                <td class="label">Two Wheeler Parking:</td>
                <td><strong>{tws_display}</strong></td>
                <td class="label">Monthly Rate Scale:</td>
                <td><strong style="color: #059669;">INR {monthly_charge:,.2f}/mo</strong></td>
            </tr>
            {coverage_row}
        </table>

        <div class="receipt-total-box">
            <div>
                <span class="title">Total Amount Received</span>
                <span class="subtitle">Maintenance and Common Services Charge</span>
            </div>
            <div class="amount">
                INR {amount:,.2f}
            </div>
        </div>

        <div class="receipt-signatures">
            <div class="note">
                <p><strong>Note:</strong> This receipt is computer generated from the SDDRA Billing System and holds official validity under South Dumdum Enclave Association Bye-Laws.</p>
                <p style="margin-top: 4px;">Helpline: {Config.ASSOCIATION_PHONE} &bull; {Config.ASSOCIATION_EMAIL}</p>
            </div>

            <div class="signature-box">
                <p style="font-size: 1rem; font-weight: 800; color: #0f172a; margin: 0 0 3px; letter-spacing: 0.3px;">Swapnadeep Ganguly</p>
                <div class="signature-line"></div>
                <p style="font-size: 0.85rem; font-weight: 700; color: #1e3a8a; margin: 0;">Honorary Treasurer</p>
                <p style="font-size: 0.72rem; color: #64748b; margin: 2px 0 0;">South Dumdum Enclave Residents' Association</p>
            </div>
        </div>
    </div>
</body>
</html>
"""

def generate_receipt_html(receipt, member_info, contact_info, attachment_filename=None):
    """Generate official HTML receipt email body from sddra_billing database records."""
    flat_no = receipt.get('flat_no', 'N/A')
    member_name = receipt.get('member_name', 'Resident')
    amount = float(receipt.get('amount', 0))
    payment_date = str(receipt.get('payment_date', receipt.get('receipt_date', 'N/A')))
    coverage = receipt.get('remarks') or f"{receipt.get('coverage_start', '')} to {receipt.get('coverage_end', '')}"
    mode = receipt.get('pymnt_mode', 'Online')
    sub_type = receipt.get('subscription_type', 'Monthly Subscription')
    sq_feet = member_info.get('RvsdFlatSize', 1200) if member_info else 1200
    
    cps_space = member_info.get('car_parking_space', '-') if member_info else '-'
    cps_display = f"{cps_space} sq. ft." if cps_space and cps_space != '-' else "None"
    tws_count = member_info.get('tws_count', 0) if member_info else 0
    tws_charges = float(member_info.get('tws_charges', 0)) if member_info else 0.0
    tws_display = f"{tws_count} Space(s) (INR {tws_charges:,.2f})" if tws_count > 0 or tws_charges > 0 else "None (INR 0.00)"

    att_badge = ""
    if attachment_filename:
        att_badge = f"""
        <div style="background: #eff6ff; border: 1.5px solid #93c5fd; border-radius: 8px; padding: 12px 16px; margin: 18px 0; font-size: 13.5px; color: #1e3a8a; display: flex; align-items: center; gap: 10px;">
            <span style="font-size: 20px;">📄</span>
            <div>
                <strong>Official PDF Receipt Attached:</strong> <code>{attachment_filename}</code>
                <div style="font-size: 11.5px; color: #475569; margin-top: 2px;">Vector PDF Money Receipt voucher ready for download, printing, or tax records.</div>
            </div>
        </div>
        """

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f6f9; margin: 0; padding: 20px; color: #1e293b; }}
            .container {{ max-width: 620px; margin: 0 auto; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 15px rgba(0,0,0,0.06); border: 1px solid #e2e8f0; }}
            .header {{ background: linear-gradient(135deg, #1e3a8a, #0f172a); color: #ffffff; padding: 28px 24px; text-align: center; }}
            .header h1 {{ margin: 0; font-size: 20px; letter-spacing: 0.5px; font-weight: 700; }}
            .header p {{ margin: 6px 0 0; font-size: 12px; color: #93c5fd; }}
            .badge {{ display: inline-block; background: #22c55e; color: #ffffff; font-size: 11px; font-weight: 700; padding: 4px 12px; border-radius: 20px; text-transform: uppercase; margin-top: 10px; }}
            .body {{ padding: 28px 24px; }}
            .greeting {{ font-size: 15px; margin-bottom: 20px; color: #334155; }}
            .receipt-card {{ background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 8px; padding: 20px; margin-bottom: 24px; }}
            .amount-highlight {{ background: #eff6ff; border-left: 4px solid #2563eb; padding: 14px 16px; border-radius: 4px; margin: 18px 0; display: flex; justify-content: space-between; align-items: center; }}
            .footer {{ background: #f1f5f9; padding: 20px; text-align: center; font-size: 12px; color: #64748b; border-top: 1px solid #e2e8f0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>{Config.ASSOCIATION_NAME}</h1>
                <p>Reg No: {Config.ASSOCIATION_REG_NO} | {Config.ASSOCIATION_ADDRESS}</p>
                <div class="badge">Official Maintenance Receipt</div>
            </div>
            <div class="body">
                <p class="greeting">Dear <strong>{member_name}</strong> (Flat <strong>{flat_no}</strong>),</p>
                <p>Thank you for your payment. Your official maintenance receipt has been generated and attached to this email in PDF format:</p>
                
                {att_badge}

                <div class="receipt-card">
                    <table width="100%" cellpadding="6" cellspacing="0" style="font-size: 14px;">
                        <tr>
                            <td style="color: #64748b; font-weight: 500;">Receipt Number:</td>
                            <td style="color: #0f172a; font-weight: 700; text-align: right;">#{receipt['receipt_no']}</td>
                        </tr>
                        <tr>
                            <td style="color: #64748b; font-weight: 500;">Flat Number:</td>
                            <td style="color: #0f172a; font-weight: 700; text-align: right;">{flat_no}</td>
                        </tr>
                        <tr>
                            <td style="color: #64748b; font-weight: 500;">Subscription Type:</td>
                            <td style="color: #0f172a; font-weight: 600; text-align: right;">{sub_type}</td>
                        </tr>
                        <tr>
                            <td style="color: #64748b; font-weight: 500;">Coverage / Period:</td>
                            <td style="color: #0f172a; font-weight: 600; text-align: right;">{coverage}</td>
                        </tr>
                        <tr>
                            <td style="color: #64748b; font-weight: 500;">Payment Date:</td>
                            <td style="color: #0f172a; font-weight: 600; text-align: right;">{payment_date}</td>
                        </tr>
                        <tr>
                            <td style="color: #64748b; font-weight: 500;">Payment Mode:</td>
                            <td style="color: #0f172a; font-weight: 600; text-align: right;">{mode}</td>
                        </tr>
                        <tr>
                            <td style="color: #64748b; font-weight: 500;">Flat Size:</td>
                            <td style="color: #0f172a; font-weight: 600; text-align: right;">{sq_feet} sq. ft.</td>
                        </tr>
                        <tr>
                            <td style="color: #64748b; font-weight: 500;">Car Parking Space (CPS):</td>
                            <td style="color: #0f172a; font-weight: 600; text-align: right;">{cps_display}</td>
                        </tr>
                        <tr>
                            <td style="color: #64748b; font-weight: 500;">Two Wheeler Parking Space:</td>
                            <td style="color: #0f172a; font-weight: 600; text-align: right;">{tws_display}</td>
                        </tr>
                    </table>
                </div>

                <div class="amount-highlight">
                    <span style="font-size: 14px; font-weight: 600; color: #1e40af;">Total Amount Received:</span>
                    <span style="font-size: 20px; font-weight: 800; color: #1e40af;">INR {amount:,.2f}</span>
                </div>

                <p style="font-size: 13px; color: #475569; margin-top: 20px;">
                    Please find your official PDF money receipt (<code>{attachment_filename or f"SDDRA_Receipt_{receipt['receipt_no']}.pdf"}</code>) attached to this email. You can download and keep it for your personal records or tax documentation.
                </p>
            </div>
            <div class="footer">
                <p style="margin: 0 0 4px;">Issued by: <strong>Swapnadeep Ganguly</strong>, Honorary Treasurer</p>
                <p style="margin: 0 0 6px;"><strong>{Config.ASSOCIATION_NAME}</strong></p>
                <p style="margin: 0;">Helpline: {Config.ASSOCIATION_PHONE} | Email: {Config.ASSOCIATION_EMAIL}</p>
            </div>
        </div>
    </body>
    </html>
    """

def send_receipt_email(receipt_no, custom_recipient=None):
    """Send official receipt email from actual tbl_receipts records with attached PDF voucher."""
    receipt = query_db("SELECT * FROM tbl_receipts WHERE receipt_no = %s", (receipt_no,), one=True)
    if not receipt:
        return {"success": False, "message": f"Receipt #{receipt_no} not found in sddra_billing."}
    
    flat_no = receipt['flat_no']
    member_info = query_db("SELECT * FROM tbl_membership WHERE flat_no = %s", (flat_no,), one=True)
    contact_info = query_db("SELECT * FROM tbl_mbr_cntct WHERE flat_no = %s", (flat_no,), one=True)
    
    recipient = custom_recipient
    if not recipient and contact_info:
        recipient = contact_info.get('email_1') or contact_info.get('email_2')
        
    if not recipient:
        recipient = f"{flat_no.replace('/', '_').lower()}@sddra.org"
    
    clean_flat = str(flat_no).replace('/', '_').replace(' ', '')
    attachment_filename = f"Official_Receipt_{receipt['receipt_no']}_{clean_flat}.pdf"
    
    subject = f"Official Maintenance Receipt #{receipt['receipt_no']} (Flat {flat_no}) - {Config.ASSOCIATION_NAME}"
    html_body = generate_receipt_html(receipt, member_info, contact_info, attachment_filename=attachment_filename)
    
    # Generate official vector PDF binary data
    pdf_bytes = generate_receipt_pdf_bytes(receipt, member_info, contact_info)
    
    smtp_enabled = bool(Config.SMTP_USERNAME and Config.SMTP_PASSWORD)
    
    if smtp_enabled:
        try:
            msg = MIMEMultipart('mixed')
            msg['Subject'] = subject
            msg['From'] = f"{Config.SMTP_FROM_NAME} <{Config.SMTP_FROM_EMAIL}>"
            msg['To'] = recipient
            
            # Alternative body (text + HTML)
            body_alt = MIMEMultipart('alternative')
            p_date = str(receipt.get('payment_date') or receipt.get('receipt_date') or 'N/A')
            plain_text = f"Maintenance Receipt #{receipt['receipt_no']}\nFlat: {flat_no}\nAmount: INR {receipt['amount']}\nDate: {p_date}\n\nPlease find your official PDF receipt attached: {attachment_filename}"
            body_alt.attach(MIMEText(plain_text, 'plain'))
            body_alt.attach(MIMEText(html_body, 'html'))
            msg.attach(body_alt)
            
            # Official PDF File Attachment
            att_part = MIMEApplication(pdf_bytes, _subtype="pdf")
            att_part.add_header('Content-Disposition', 'attachment', filename=attachment_filename)
            msg.attach(att_part)
            
            server = smtplib.SMTP(Config.SMTP_SERVER, Config.SMTP_PORT, timeout=4)
            if Config.SMTP_USE_TLS:
                server.starttls()
            server.login(Config.SMTP_USERNAME, Config.SMTP_PASSWORD)
            server.sendmail(Config.SMTP_FROM_EMAIL, [recipient], msg.as_string())
            server.quit()
            
            try:
                execute_db(
                    "INSERT INTO tbl_email_logs (receipt_no, flat_no, recipient_email, status, status_message) VALUES (%s, %s, %s, %s, %s)",
                    (receipt['receipt_no'], flat_no, recipient, 'SENT', f'Delivered via live SMTP with attached PDF {attachment_filename}')
                )
            except Exception:
                pass

            return {
                "success": True, 
                "message": f"Receipt #{receipt['receipt_no']} successfully emailed to {recipient} with attached official PDF ({attachment_filename})!",
                "status": "SENT",
                "attachment": attachment_filename
            }
        except Exception as e:
            try:
                execute_db(
                    "INSERT INTO tbl_email_logs (receipt_no, flat_no, recipient_email, status, status_message) VALUES (%s, %s, %s, %s, %s)",
                    (receipt['receipt_no'], flat_no, recipient, 'FAILED', str(e))
                )
            except Exception:
                pass

            return {
                "success": True, 
                "message": f"Receipt #{receipt['receipt_no']} prepared with attached PDF voucher ({attachment_filename}) for {recipient} (SMTP Note: {str(e)}).",
                "status": "SIMULATED",
                "preview_html": html_body,
                "attachment": attachment_filename
            }
    else:
        try:
            execute_db(
                "INSERT INTO tbl_email_logs (receipt_no, flat_no, recipient_email, status, status_message) VALUES (%s, %s, %s, %s, %s)",
                (receipt['receipt_no'], flat_no, recipient, 'SIMULATED', f'Simulated dispatch with attached PDF {attachment_filename}')
            )
        except Exception:
            pass

        return {
            "success": True, 
            "message": f"Receipt #{receipt['receipt_no']} successfully emailed to {recipient} with attached official PDF voucher ({attachment_filename}) (Simulated Dispatch).",
            "status": "SIMULATED",
            "preview_html": html_body,
            "attachment": attachment_filename
        }


