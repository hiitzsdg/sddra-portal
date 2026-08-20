import io
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from config import Config

def _draw_page_decorations(canvas_obj, doc):
    """Draw official border and background watermark on the PDF canvas."""
    canvas_obj.saveState()
    width, height = A4
    
    # Outer Border (Navy)
    canvas_obj.setStrokeColor(colors.HexColor('#1E3A8A'))
    canvas_obj.setLineWidth(1.5)
    canvas_obj.roundRect(24, 24, width - 48, height - 48, 8, stroke=1, fill=0)
    
    # Inner Fine Border (Slate)
    canvas_obj.setStrokeColor(colors.HexColor('#94A3B8'))
    canvas_obj.setLineWidth(0.5)
    canvas_obj.roundRect(28, 28, width - 56, height - 56, 6, stroke=1, fill=0)
    
    # Watermark
    canvas_obj.translate(width / 2.0, height / 2.0)
    canvas_obj.rotate(32)
    canvas_obj.setFont("Helvetica-Bold", 44)
    canvas_obj.setFillColor(colors.HexColor('#1E3A8A'), alpha=0.038)
    canvas_obj.drawCentredString(0, 0, "SDDRA OFFICIAL")
    
    canvas_obj.restoreState()

def generate_receipt_pdf_bytes(receipt, member_info=None, contact_info=None):
    """
    Generate an official, high-resolution, vector PDF Money Receipt voucher
    as in-memory bytes for email attachment and direct browser download.
    """
    buffer = io.BytesIO()
    
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36
    )
    
    styles = getSampleStyleSheet()
    
    # Custom Styles
    header_title_style = ParagraphStyle(
        'ReceiptHeaderTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=15,
        leading=18,
        textColor=colors.HexColor('#1E3A8A'),
        alignment=1
    )
    
    header_sub_style = ParagraphStyle(
        'ReceiptHeaderSub',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor('#475569'),
        alignment=1
    )
    
    badge_style = ParagraphStyle(
        'ReceiptBadge',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9.5,
        leading=12,
        textColor=colors.HexColor('#0F172A'),
        alignment=1
    )
    
    cell_label_style = ParagraphStyle(
        'ReceiptCellLabel',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor('#475569')
    )
    
    cell_value_style = ParagraphStyle(
        'ReceiptCellValue',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor('#0F172A')
    )
    
    cell_value_bold = ParagraphStyle(
        'ReceiptCellValueBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=11,
        textColor=colors.HexColor('#1E3A8A')
    )
    
    # Extract metadata & format values
    receipt = receipt or {}
    member_info = member_info or {}
    contact_info = contact_info or {}
    
    flat_no = str(receipt.get('flat_no') or member_info.get('flat_no') or 'N/A')
    member_name = receipt.get('member_name') or member_info.get('member_name') or 'Resident'
    try:
        amount = float(receipt.get('amount') or 0)
    except (ValueError, TypeError):
        amount = 0.0
        
    payment_date = str(receipt.get('payment_date') or receipt.get('receipt_date') or 'N/A')
    receipt_date = str(receipt.get('receipt_date') or receipt.get('payment_date') or datetime.now().strftime('%Y-%m-%d'))
    coverage = receipt.get('remarks') or f"{receipt.get('coverage_start', '')} to {receipt.get('coverage_end', '')}".strip() or 'Monthly Maintenance'
    mode = receipt.get('pymnt_mode') or 'Online / NetBanking'
    sub_type = receipt.get('subscription_type') or 'Monthly Subscription'
    sq_feet = member_info.get('RvsdFlatSize') or 1200
    phone = (contact_info.get('mobile_num_1') or contact_info.get('mobile_num_2') or 'On File')
    email_addr = (contact_info.get('email_1') or contact_info.get('email_2') or 'On File')
    
    try:
        monthly_charge = float(member_info.get('monthly_charge') or amount)
    except (ValueError, TypeError):
        monthly_charge = amount
    
    cps_space = member_info.get('car_parking_space', '-')
    try:
        cps_charges = float(member_info.get('cps_charges') or 0)
    except (ValueError, TypeError):
        cps_charges = 0.0
        
    if cps_space and str(cps_space).strip() != '-':
        cps_display = f"{cps_space} Sq. Ft."
        if cps_charges > 0:
            cps_display += f" (INR {cps_charges:,.2f})"
    else:
        cps_display = "None / '-'"

    try:
        tws_count = int(member_info.get('tws_count') or 0)
    except (ValueError, TypeError):
        tws_count = 0
        
    try:
        tws_charges = float(member_info.get('tws_charges') or 0)
    except (ValueError, TypeError):
        tws_charges = 0.0
        
    if member_info.get('tws_owner') or tws_count > 0 or tws_charges > 0:
        tws_display = f"{tws_count or 1} Space{'s' if tws_count > 1 else ''} (INR {tws_charges or 150.0:,.2f})"
    else:
        tws_display = "None (INR 0.00)"

    elements = []
    
    # 1. Header Section
    elements.append(Paragraph(Config.ASSOCIATION_NAME.upper(), header_title_style))
    elements.append(Spacer(1, 3))
    elements.append(Paragraph(f"Registration No: <b>{Config.ASSOCIATION_REG_NO}</b> &bull; {Config.ASSOCIATION_ADDRESS}", header_sub_style))
    elements.append(Paragraph(f"Email: {Config.ASSOCIATION_EMAIL} &bull; Phone: {Config.ASSOCIATION_PHONE}", header_sub_style))
    elements.append(Spacer(1, 6))
    
    # 2. Official Badge
    badge_table = Table([[Paragraph("OFFICIAL MAINTENANCE RECEIPT", badge_style)]], colWidths=[240])
    badge_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F8FAFC')),
        ('BOX', (0,0), (-1,-1), 1.2, colors.HexColor('#0F172A')),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
    ]))
    elements.append(badge_table)
    elements.append(Spacer(1, 8))
    
    # 3. Meta Bar (Receipt # and Date of Issue)
    meta_data = [
        [
            Paragraph(f"<b>Receipt No:</b> <font color='#1E3A8A' size=10><b>#{receipt.get('receipt_no', 'N/A')}</b></font>", cell_value_style),
            Paragraph(f"<b>Date of Issue:</b> {receipt_date}", cell_value_style)
        ]
    ]
    meta_table = Table(meta_data, colWidths=[260, 260])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#EFF6FF')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#BFDBFE')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING', (0,0), (-1,-1), 10),
        ('RIGHTPADDING', (0,0), (-1,-1), 10),
    ]))
    elements.append(meta_table)
    elements.append(Spacer(1, 8))
    
    # 4. Detailed Grid Table
    details_data = [
        [
            Paragraph("Resident Name:", cell_label_style),
            Paragraph(f"<b>{member_name}</b>", cell_value_style),
            Paragraph("Flat Number:", cell_label_style),
            Paragraph(f"<b>Flat {flat_no}</b>", cell_value_bold),
        ],
        [
            Paragraph("Contact Mobile:", cell_label_style),
            Paragraph(phone, cell_value_style),
            Paragraph("Registered Email:", cell_label_style),
            Paragraph(email_addr, cell_value_style),
        ],
        [
            Paragraph("Subscription Type:", cell_label_style),
            Paragraph(f"<b>{sub_type}</b>", cell_value_style),
            Paragraph("Period / Month:", cell_label_style),
            Paragraph(f"<b>{coverage}</b>", cell_value_style),
        ],
        [
            Paragraph("Payment Date:", cell_label_style),
            Paragraph(payment_date, cell_value_style),
            Paragraph("Payment Mode:", cell_label_style),
            Paragraph(f"<b>{mode}</b>", cell_value_style),
        ],
        [
            Paragraph("Flat Size / Area:", cell_label_style),
            Paragraph(f"{sq_feet} Sq. Ft.", cell_value_style),
            Paragraph("Car Parking (CPS):", cell_label_style),
            Paragraph(cps_display, cell_value_style),
        ],
        [
            Paragraph("Two Wheeler Parking:", cell_label_style),
            Paragraph(tws_display, cell_value_style),
            Paragraph("Monthly Rate Scale:", cell_label_style),
            Paragraph(f"INR {monthly_charge:,.2f}/mo", cell_value_style),
        ]
    ]
    
    if receipt.get('coverage_start') and receipt.get('coverage_end'):
        details_data.append([
            Paragraph("Billing Coverage:", cell_label_style),
            Paragraph(f"From <b>{receipt.get('coverage_start')}</b> to <b>{receipt.get('coverage_end')}</b>", cell_value_style),
            "",
            ""
        ])
    
    col_w = [110, 150, 110, 150]
    grid_table = Table(details_data, colWidths=col_w)
    grid_style = [
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('BACKGROUND', (0,0), (0,-1), colors.HexColor('#F8FAFC')),
        ('BACKGROUND', (2,0), (2,-1), colors.HexColor('#F8FAFC')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
    ]
    if len(details_data) > 6:
        grid_style.append(('SPAN', (1, 6), (3, 6)))
        
    grid_table.setStyle(TableStyle(grid_style))
    elements.append(grid_table)
    elements.append(Spacer(1, 8))
    
    # 5. Total Amount Box
    total_data = [
        [
            Paragraph("<b><font color='#166534' size=9.5>TOTAL AMOUNT RECEIVED</font></b><br/><font color='#475569' size=7.5><i>Maintenance &amp; Common Services Charge</i></font>", cell_value_style),
            Paragraph(f"<b><font color='#1E3A8A' size=15>INR {amount:,.2f}</font></b>", ParagraphStyle('Amt', parent=styles['Normal'], alignment=2))
        ]
    ]
    total_table = Table(total_data, colWidths=[320, 200])
    total_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#DCFCE7')),
        ('BOX', (0,0), (-1,-1), 1.2, colors.HexColor('#86EFAC')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 7),
        ('BOTTOMPADDING', (0,0), (-1,-1), 7),
        ('LEFTPADDING', (0,0), (-1,-1), 12),
        ('RIGHTPADDING', (0,0), (-1,-1), 12),
    ]))
    elements.append(total_table)
    elements.append(Spacer(1, 10))
    
    # 6. Signatures and Disclaimer Section
    note_p = Paragraph(
        f"<b>Note:</b> This receipt is computer-generated from the SDDRA Billing System and holds official validity under South Dumdum Enclave Association Bye-Laws.<br/><font color='#64748B' size=7.5>Helpline: {Config.ASSOCIATION_PHONE} &bull; Email: {Config.ASSOCIATION_EMAIL}</font>",
        ParagraphStyle('Note', parent=styles['Normal'], fontSize=7.5, leading=9.5, textColor=colors.HexColor('#475569'))
    )
    
    sig_p = Paragraph(
        "<font size=9><b>Swapnadeep Ganguly</b></font><br/>"
        "<font size=7.5 color='#1E3A8A'><b>Honorary Treasurer</b></font><br/>"
        f"<font size=6.5 color='#64748B'>{Config.ASSOCIATION_NAME}</font>",
        ParagraphStyle('Sig', parent=styles['Normal'], alignment=1, leading=9)
    )
    
    footer_data = [
        [note_p, sig_p]
    ]
    footer_table = Table(footer_data, colWidths=[340, 180])
    footer_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'BOTTOM'),
        ('LINEABOVE', (1,0), (1,0), 0.8, colors.HexColor('#64748B')),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
    ]))
    elements.append(footer_table)
    
    doc.build(elements, onFirstPage=_draw_page_decorations)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
