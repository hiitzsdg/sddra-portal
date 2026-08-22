from database import execute_db

execute_db(
    """UPDATE tbl_expenses 
       SET expense_description = %s, particulars = %s, spl_head = %s, payment_by = %s, amount = %s, voucher_date = %s 
       WHERE voucher_no = 81""",
    ("Mobile recharge for security room - Aug'2026", "Misc & Other Expenses", "Security", "Online", 349.00, "2026-08-01")
)
print("Voucher 81 reset successfully.")
