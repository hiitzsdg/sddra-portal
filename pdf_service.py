import io
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether
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
    canvas_obj.drawCentredString(0, 0, "SDERA OFFICIAL")
    
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
        fontSize=7.5,
        leading=9,
        textColor=colors.HexColor('#FFFFFF'),
        alignment=1
    )
    
    doc_title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=16,
        textColor=colors.HexColor('#0F172A'),
        alignment=1
    )
    
    cell_label_style = ParagraphStyle(
        'CellLabel',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor('#334155')
    )
    
    cell_value_style = ParagraphStyle(
        'CellValue',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#0F172A')
    )
    
    elements = []
    
    # 1. Header Section
    elements.append(Paragraph(Config.ASSOCIATION_NAME.upper(), header_title_style))
    elements.append(Spacer(1, 2))
    
    reg_pill = Table([[Paragraph(f"REGD. NO. {Config.ASSOCIATION_REG_NO}", badge_style)]], colWidths=[180])
    reg_pill.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#0F172A')),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 2),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
    ]))
    
    center_pill_table = Table([[reg_pill]], colWidths=[520])
    center_pill_table.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
    ]))
    elements.append(center_pill_table)
    elements.append(Spacer(1, 2))
    
    elements.append(Paragraph(Config.ASSOCIATION_ADDRESS.upper(), header_sub_style))
    elements.append(Spacer(1, 1))
    elements.append(Paragraph(f"Email: {Config.ASSOCIATION_EMAIL} &bull; Helpline: {Config.ASSOCIATION_PHONE}", header_sub_style))
    elements.append(Spacer(1, 6))
    
    # Divider line
    div_table = Table([[""]], colWidths=[520], rowHeights=[1.5])
    div_table.setStyle(TableStyle([
        ('LINEBELOW', (0,0), (-1,-1), 1.2, colors.HexColor('#1E3A8A')),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 0),
    ]))
    elements.append(div_table)
    elements.append(Spacer(1, 6))
    
    # 2. Document Banner
    elements.append(Paragraph("OFFICIAL MONEY RECEIPT", doc_title_style))
    elements.append(Spacer(1, 6))
    
    # 3. Meta Bar
    rcpt_no = receipt.get('receipt_no', '')
    rcpt_date = receipt.get('receipt_date', '')
    payment_date = receipt.get('payment_date', '') or rcpt_date
    flat_no = receipt.get('flat_no', '')
    member_name = receipt.get('member_name', '')
    remarks = receipt.get('remarks', '')
    amount = float(receipt.get('amount', 0))
    pymnt_mode = receipt.get('pymnt_mode', 'Online')
    sub_type = receipt.get('subscription_type', 'Monthly Subscription')
    
    meta_data = [
        [
            Paragraph(f"<b>Receipt No:</b> <font color='#1E3A8A'>SDERA_{rcpt_no}</font>", cell_label_style),
            Paragraph(f"<b>Date of Issue:</b> {rcpt_date}", ParagraphStyle('RightMeta', parent=cell_label_style, alignment=2))
        ]
    ]
    meta_table = Table(meta_data, colWidths=[260, 260])
    meta_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 2),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
    ]))
    elements.append(meta_table)
    elements.append(Spacer(1, 6))
    
    # 4. Details Grid
    details_data = [
        [
            Paragraph("Flat Number / Unit", cell_label_style),
            Paragraph(f"<b><font color='#1E3A8A' size=10>Flat {flat_no}</font></b>", cell_value_style),
            Paragraph("Resident Name", cell_label_style),
            Paragraph(f"<b>{member_name}</b>", cell_value_style)
        ],
        [
            Paragraph("Subscription Type", cell_label_style),
            Paragraph(str(sub_type), cell_value_style),
            Paragraph("Payment Mode", cell_label_style),
            Paragraph(f"<b>{pymnt_mode}</b>", cell_value_style)
        ],
        [
            Paragraph("Billing Month / Coverage", cell_label_style),
            Paragraph(f"<b><font color='#2563EB'>{remarks}</font></b>", cell_value_style),
            Paragraph("Payment Date", cell_label_style),
            Paragraph(str(payment_date), cell_value_style)
        ]
    ]
    
    if member_info:
        sq_ft = member_info.get('sq_feet') or member_info.get('RvsdFlatSize') or '-'
        parking = member_info.get('car_parking_space') or 'None'
        details_data.append([
            Paragraph("Flat Area (Super Built)", cell_label_style),
            Paragraph(f"{sq_ft} Sq. Ft.", cell_value_style),
            Paragraph("Parking Space", cell_label_style),
            Paragraph(f"{parking}", cell_value_style)
        ])
        
    if receipt.get('coverage_start') and receipt.get('coverage_end'):
        details_data.append([
            Paragraph("Accounting Period", cell_label_style),
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
        f"<b>Note:</b> This receipt is computer-generated from the SDERA Billing System and holds official validity under South Dumdum Enclave Association Bye-Laws.<br/><font color='#64748B' size=7.5>Helpline: {Config.ASSOCIATION_PHONE} &bull; Email: {Config.ASSOCIATION_EMAIL}</font>",
        ParagraphStyle('Note', parent=styles['Normal'], fontSize=7.5, leading=9.5, textColor=colors.HexColor('#64748B'))
    )
    
    sig_name = Paragraph(
        "<b><font size=9.5 color='#0F172A'>Swapnadeep Ganguly</font></b>", 
        ParagraphStyle('SigName', parent=styles['Normal'], alignment=1, leading=11)
    )
    sig_title = Paragraph(
        "<b><font size=8 color='#1E3A8A'>Honorary Treasurer</font></b><br/>"
        f"<font size=6.5 color='#64748B'>{Config.ASSOCIATION_NAME}</font>", 
        ParagraphStyle('SigTitle', parent=styles['Normal'], alignment=1, leading=9)
    )
    
    sig_box_table = Table([[sig_name], [sig_title]], colWidths=[175])
    sig_box_table.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('LINEBELOW', (0,0), (0,0), 0.8, colors.HexColor('#64748B')),
        ('TOPPADDING', (0,0), (-1,-1), 1),
        ('BOTTOMPADDING', (0,0), (0,0), 3),
        ('TOPPADDING', (0,1), (0,1), 3),
        ('BOTTOMPADDING', (0,1), (0,1), 1),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
    ]))
    
    footer_data = [
        [note_p, sig_box_table]
    ]
    footer_table = Table(footer_data, colWidths=[340, 180])
    footer_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'BOTTOM'),
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

def generate_expense_voucher_pdf_bytes(expense):
    """
    Generate an official, high-resolution vector PDF Expense Payment Voucher
    with Association letterhead, verification stamp, particulars, and disbursement breakdown.
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
    
    header_title_style = ParagraphStyle(
        'ExpHeaderTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=15,
        leading=18,
        textColor=colors.HexColor('#1E3A8A'),
        alignment=1
    )
    
    header_sub_style = ParagraphStyle(
        'ExpHeaderSub',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor('#475569'),
        alignment=1
    )
    
    badge_style = ParagraphStyle(
        'ExpBadge',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7.5,
        leading=9,
        textColor=colors.HexColor('#FFFFFF'),
        alignment=1
    )
    
    doc_title_style = ParagraphStyle(
        'ExpDocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=16,
        textColor=colors.HexColor('#0F172A'),
        alignment=1
    )
    
    cell_label_style = ParagraphStyle(
        'ExpCellLabel',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor('#334155')
    )
    
    cell_value_style = ParagraphStyle(
        'ExpCellValue',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#0F172A')
    )
    
    elements = []
    
    # 1. Header Section
    elements.append(Paragraph(Config.ASSOCIATION_NAME.upper(), header_title_style))
    elements.append(Spacer(1, 2))
    
    reg_pill = Table([[Paragraph(f"REGD. NO. {Config.ASSOCIATION_REG_NO}", badge_style)]], colWidths=[180])
    reg_pill.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#0F172A')),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 2),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
    ]))
    
    center_pill_table = Table([[reg_pill]], colWidths=[520])
    center_pill_table.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
    ]))
    elements.append(center_pill_table)
    elements.append(Spacer(1, 2))
    
    elements.append(Paragraph(Config.ASSOCIATION_ADDRESS.upper(), header_sub_style))
    elements.append(Spacer(1, 1))
    elements.append(Paragraph(f"Email: {Config.ASSOCIATION_EMAIL} &bull; Official Accounts Ledger", header_sub_style))
    elements.append(Spacer(1, 6))
    
    # Divider line
    div_table = Table([[""]], colWidths=[520], rowHeights=[1.5])
    div_table.setStyle(TableStyle([
        ('LINEBELOW', (0,0), (-1,-1), 1.2, colors.HexColor('#B91C1C')),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 0),
    ]))
    elements.append(div_table)
    elements.append(Spacer(1, 6))
    
    # 2. Document Banner
    elements.append(Paragraph("OFFICIAL EXPENSE PAYMENT VOUCHER", doc_title_style))
    elements.append(Spacer(1, 6))
    
    # 3. Meta Bar
    voucher_no = expense.get('voucher_no', '')
    voucher_date = str(expense.get('voucher_date', ''))[:10]
    description = expense.get('expense_description', '')
    particulars = expense.get('particulars', '') or 'Misc & Other Expenses'
    spl_head = expense.get('spl_head', '') or '-'
    payment_by = expense.get('payment_by', 'Online')
    amount = float(expense.get('amount', 0))
    
    meta_data = [
        [
            Paragraph(f"<b>Voucher No:</b> <font color='#B91C1C'>SDERA_EXP_{voucher_no}</font>", cell_label_style),
            Paragraph(f"<b>Expenditure Date:</b> {voucher_date}", ParagraphStyle('RightMeta', parent=cell_label_style, alignment=2))
        ]
    ]
    meta_table = Table(meta_data, colWidths=[260, 260])
    meta_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 2),
        ('BOTTOMPADDING', (0,0), (-1,-1), 2),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
    ]))
    elements.append(meta_table)
    elements.append(Spacer(1, 6))
    
    # 4. Details Grid
    details_data = [
        [
            Paragraph("Voucher Number", cell_label_style),
            Paragraph(f"<b><font color='#B91C1C' size=10>#{voucher_no}</font></b>", cell_value_style),
            Paragraph("Disbursement Date", cell_label_style),
            Paragraph(f"<b>{voucher_date}</b>", cell_value_style)
        ],
        [
            Paragraph("Account Particulars", cell_label_style),
            Paragraph(f"<b><font color='#1E3A8A'>{particulars}</font></b>", cell_value_style),
            Paragraph("Special Head", cell_label_style),
            Paragraph(f"{spl_head}", cell_value_style)
        ],
        [
            Paragraph("Payment Mode", cell_label_style),
            Paragraph(f"<b>{payment_by}</b>", cell_value_style),
            Paragraph("Accounting Status", cell_label_style),
            Paragraph("<b><font color='#15803D'>Disbursed &amp; Reconciled</font></b>", cell_value_style)
        ],
        [
            Paragraph("Description / Narration", cell_label_style),
            Paragraph(f"<b>{description}</b>", cell_value_style),
            "",
            ""
        ]
    ]
    
    col_w = [120, 140, 120, 140]
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
        ('SPAN', (1, 3), (3, 3))
    ]
    grid_table.setStyle(TableStyle(grid_style))
    elements.append(grid_table)
    elements.append(Spacer(1, 8))
    
    # 5. Total Outlay Amount Box
    total_data = [
        [
            Paragraph("<b><font color='#991B1B' size=9.5>TOTAL DISBURSED AMOUNT</font></b><br/><font color='#475569' size=7.5><i>Authorized Society Expenditure Voucher</i></font>", cell_value_style),
            Paragraph(f"<b><font color='#B91C1C' size=15>INR {amount:,.2f}</font></b>", ParagraphStyle('Amt', parent=styles['Normal'], alignment=2))
        ]
    ]
    total_table = Table(total_data, colWidths=[320, 200])
    total_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#FEE2E2')),
        ('BOX', (0,0), (-1,-1), 1.2, colors.HexColor('#F87171')),
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
        f"<b>Audit Note:</b> This expense payment voucher is generated from the official SDERA accounts register and verified against actual association payments.<br/><font color='#64748B' size=7.5>Helpline: {Config.ASSOCIATION_PHONE} &bull; Email: {Config.ASSOCIATION_EMAIL}</font>",
        ParagraphStyle('Note', parent=styles['Normal'], fontSize=7.5, leading=9.5, textColor=colors.HexColor('#64748B'))
    )
    
    sig_name = Paragraph(
        "<b><font size=9.5 color='#0F172A'>Honorary Treasurer</font></b>", 
        ParagraphStyle('SigName', parent=styles['Normal'], alignment=1, leading=11)
    )
    sig_title = Paragraph(
        "<b><font size=8 color='#1E3A8A'>Executive Committee</font></b><br/>"
        f"<font size=6.5 color='#64748B'>{Config.ASSOCIATION_NAME}</font>", 
        ParagraphStyle('SigTitle', parent=styles['Normal'], alignment=1, leading=9)
    )
    
    sig_box_table = Table([[sig_name], [sig_title]], colWidths=[175])
    sig_box_table.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('LINEBELOW', (0,0), (0,0), 0.8, colors.HexColor('#64748B')),
        ('TOPPADDING', (0,0), (-1,-1), 1),
        ('BOTTOMPADDING', (0,0), (0,0), 3),
        ('TOPPADDING', (0,1), (0,1), 3),
        ('BOTTOMPADDING', (0,1), (0,1), 1),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
    ]))
    
    footer_data = [
        [note_p, sig_box_table]
    ]
    footer_table = Table(footer_data, colWidths=[340, 180])
    footer_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'BOTTOM'),
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

def generate_all_expenses_book_pdf_bytes(expenses_list):
    """
    Generate an official, compiled Master Expense Voucher Book (Multi-Page PDF)
    containing an executive summary and all individual numbered vouchers.
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
    
    title_style = ParagraphStyle(
        'BookTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=colors.HexColor('#1E3A8A'),
        alignment=1
    )
    
    sub_style = ParagraphStyle(
        'BookSub',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#475569'),
        alignment=1
    )
    
    h2_style = ParagraphStyle(
        'BookH2',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=15,
        textColor=colors.HexColor('#0F172A')
    )
    
    cell_head_style = ParagraphStyle(
        'BookCellHead',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor('#FFFFFF')
    )
    
    cell_body_style = ParagraphStyle(
        'BookCellBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=10.5,
        textColor=colors.HexColor('#0F172A')
    )
    
    cell_amt_style = ParagraphStyle(
        'BookCellAmt',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor('#B91C1C'),
        alignment=2
    )

    elements = []
    
    # 1. Master Cover Page / Executive Summary
    elements.append(Paragraph(Config.ASSOCIATION_NAME.upper(), title_style))
    elements.append(Spacer(1, 4))
    elements.append(Paragraph("MASTER SOCIETY EXPENDITURE VOUCHER COMPENDIUM", ParagraphStyle('Comp', parent=title_style, fontSize=14, leading=17, textColor=colors.HexColor('#B91C1C'))))
    elements.append(Spacer(1, 4))
    elements.append(Paragraph(f"Official Accounting Register &bull; Regd. No. {Config.ASSOCIATION_REG_NO}", sub_style))
    elements.append(Spacer(1, 14))
    
    total_amount = sum(float(e.get('amount', 0)) for e in expenses_list)
    total_vouchers = len(expenses_list)
    
    summary_data = [
        [
            Paragraph("<b>Total Vouchers Compiled</b>", cell_body_style),
            Paragraph(f"<b>{total_vouchers} Vouchers</b>", cell_body_style),
            Paragraph("<b>Total Expenditure Incurred</b>", cell_body_style),
            Paragraph(f"<b><font color='#B91C1C'>INR {total_amount:,.2f}</font></b>", cell_body_style)
        ],
        [
            Paragraph("<b>Generated On</b>", cell_body_style),
            Paragraph(datetime.now().strftime('%d-%b-%Y %H:%M'), cell_body_style),
            Paragraph("<b>Audit Status</b>", cell_body_style),
            Paragraph("<b><font color='#15803D'>Verified &amp; Reconciled</font></b>", cell_body_style)
        ]
    ]
    summary_table = Table(summary_data, colWidths=[130, 130, 130, 130])
    summary_table.setStyle(TableStyle([
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F8FAFC')),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 16))
    
    elements.append(Paragraph("Complete Roster of Incurred Vouchers", h2_style))
    elements.append(Spacer(1, 6))
    
    # Table of all vouchers
    table_rows = [
        [
            Paragraph("Voucher #", cell_head_style),
            Paragraph("Date", cell_head_style),
            Paragraph("Particulars", cell_head_style),
            Paragraph("Special Head", cell_head_style),
            Paragraph("Description", cell_head_style),
            Paragraph("Mode", cell_head_style),
            Paragraph("Amount (INR)", cell_head_style)
        ]
    ]
    
    for e in expenses_list:
        v_no = f"#{e.get('voucher_no')}"
        v_date = str(e.get('voucher_date', ''))[:10]
        v_part = str(e.get('particulars', ''))
        v_spl = str(e.get('spl_head', '') or '-')
        v_desc = str(e.get('expense_description', ''))
        v_pay = str(e.get('payment_by', ''))
        v_amt = f"₹ {float(e.get('amount', 0)):,.2f}"
        
        table_rows.append([
            Paragraph(v_no, cell_body_style),
            Paragraph(v_date, cell_body_style),
            Paragraph(v_part, cell_body_style),
            Paragraph(v_spl, cell_body_style),
            Paragraph(v_desc, cell_body_style),
            Paragraph(v_pay, cell_body_style),
            Paragraph(v_amt, cell_amt_style)
        ])
        
    roster_table = Table(table_rows, colWidths=[55, 60, 95, 75, 130, 45, 60], repeatRows=1)
    roster_style = [
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1E3A8A')),
        ('GRID', (0,0), (-1,-1), 0.3, colors.HexColor('#E2E8F0')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 4),
        ('RIGHTPADDING', (0,0), (-1,-1), 4),
    ]
    
    for i in range(1, len(table_rows)):
        if i % 2 == 0:
            roster_style.append(('BACKGROUND', (0, i), (-1, i), colors.HexColor('#F8FAFC')))
            
    roster_table.setStyle(TableStyle(roster_style))
    elements.append(roster_table)
    
    doc.build(elements, onFirstPage=_draw_page_decorations, onLaterPages=_draw_page_decorations)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes
