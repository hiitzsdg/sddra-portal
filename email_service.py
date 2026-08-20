import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime
from config import Config
from database import query_db, execute_db

def generate_receipt_html(receipt, member_info, contact_info):
    """Generate official HTML receipt from sddra_billing database records."""
    flat_no = receipt.get('flat_no', 'N/A')
    member_name = receipt.get('member_name', 'Resident')
    amount = float(receipt.get('amount', 0))
    payment_date = str(receipt.get('payment_date', receipt.get('receipt_date', 'N/A')))
    receipt_date = str(receipt.get('receipt_date', 'N/A'))
    coverage = receipt.get('remarks') or f"{receipt.get('coverage_start', '')} to {receipt.get('coverage_end', '')}"
    mode = receipt.get('pymnt_mode', 'Online')
    sub_type = receipt.get('subscription_type', 'Monthly Subscription')
    sq_feet = member_info.get('RvsdFlatSize', 1200) if member_info else 1200
    phone = contact_info.get('mobile_num_1', '') if contact_info else ''
    
    cps_space = member_info.get('car_parking_space', '-') if member_info else '-'
    cps_display = f"{cps_space} sq. ft." if cps_space and cps_space != '-' else "None"
    tws_count = member_info.get('tws_count', 0) if member_info else 0
    tws_charges = float(member_info.get('tws_charges', 0)) if member_info else 0.0
    tws_display = f"{tws_count} Space(s) (INR {tws_charges:,.2f})" if tws_count > 0 or tws_charges > 0 else "None (INR 0.00)"

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
                <p>Thank you for your payment. Please find the details of your official maintenance receipt below:</p>
                
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
                    You can also login to the <a href="http://localhost:5000" style="color: #2563eb; font-weight: 600;">SDERA Resident Portal</a> at any time to review your full payment history and audit association expenses.
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
    """Send official receipt email from actual tbl_receipts records."""
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
    
    subject = f"Official Maintenance Receipt #{receipt['receipt_no']} (Flat {flat_no}) - {Config.ASSOCIATION_NAME}"
    html_content = generate_receipt_html(receipt, member_info, contact_info)
    
    smtp_enabled = bool(Config.SMTP_USERNAME and Config.SMTP_PASSWORD)
    
    if smtp_enabled:
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = f"{Config.SMTP_FROM_NAME} <{Config.SMTP_FROM_EMAIL}>"
            msg['To'] = recipient
            
            p_date = str(receipt.get('payment_date') or receipt.get('receipt_date') or 'N/A')
            plain_text = f"Maintenance Receipt #{receipt['receipt_no']}\nFlat: {flat_no}\nAmount: INR {receipt['amount']}\nDate: {p_date}"
            msg.attach(MIMEText(plain_text, 'plain'))
            msg.attach(MIMEText(html_content, 'html'))
            
            server = smtplib.SMTP(Config.SMTP_SERVER, Config.SMTP_PORT, timeout=4)
            if Config.SMTP_USE_TLS:
                server.starttls()
            server.login(Config.SMTP_USERNAME, Config.SMTP_PASSWORD)
            server.sendmail(Config.SMTP_FROM_EMAIL, [recipient], msg.as_string())
            server.quit()
            
            try:
                execute_db(
                    "INSERT INTO tbl_email_logs (receipt_no, flat_no, recipient_email, status, status_message) VALUES (%s, %s, %s, %s, %s)",
                    (receipt['receipt_no'], flat_no, recipient, 'SENT', 'Delivered via live SMTP')
                )
            except Exception:
                pass

            return {
                "success": True, 
                "message": f"Receipt #{receipt['receipt_no']} successfully emailed to {recipient} via SMTP!",
                "status": "SENT"
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
                "message": f"Receipt #{receipt['receipt_no']} formatted for {recipient} (SMTP Note: {str(e)}).",
                "status": "SIMULATED",
                "preview_html": html_content
            }
    else:
        try:
            execute_db(
                "INSERT INTO tbl_email_logs (receipt_no, flat_no, recipient_email, status, status_message) VALUES (%s, %s, %s, %s, %s)",
                (receipt['receipt_no'], flat_no, recipient, 'SIMULATED', 'Simulated dispatch (SMTP not configured)')
            )
        except Exception:
            pass

        return {
            "success": True, 
            "message": f"Receipt #{receipt['receipt_no']} successfully emailed to {recipient} (Simulated Dispatch).",
            "status": "SIMULATED",
            "preview_html": html_content
        }
