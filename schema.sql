-- South Dumdum Enclave Residents' Association (SDERA)
-- Database Schema for MySQL 8.0+

CREATE DATABASE IF NOT EXISTS south_dumdum_enclave CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE south_dumdum_enclave;

-- Table: Members (Residents, Executive Committee, Caretakers)
CREATE TABLE IF NOT EXISTS members (
    id INT AUTO_INCREMENT PRIMARY KEY,
    flat_number VARCHAR(20) NOT NULL UNIQUE,
    block VARCHAR(10) NOT NULL DEFAULT 'A',
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100) NOT NULL,
    phone VARCHAR(20) NOT NULL,
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role ENUM('MEMBER', 'CARETAKER', 'TREASURER', 'SECRETARY', 'PRESIDENT') NOT NULL DEFAULT 'MEMBER',
    sq_feet INT DEFAULT 1200,
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_role (role),
    INDEX idx_flat (flat_number),
    INDEX idx_username (username)
) ENGINE=InnoDB;

-- Table: Maintenance Receipts
CREATE TABLE IF NOT EXISTS receipts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    receipt_no VARCHAR(50) NOT NULL UNIQUE,
    member_id INT NOT NULL,
    amount DECIMAL(10, 2) NOT NULL,
    period_month VARCHAR(20) NOT NULL,
    period_year INT NOT NULL,
    payment_date DATE NOT NULL,
    payment_mode ENUM('CASH', 'UPI', 'NEFT', 'CHEQUE', 'NET_BANKING') NOT NULL DEFAULT 'UPI',
    transaction_ref VARCHAR(100) DEFAULT NULL,
    notes TEXT DEFAULT NULL,
    created_by INT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (member_id) REFERENCES members(id) ON DELETE CASCADE,
    FOREIGN KEY (created_by) REFERENCES members(id),
    INDEX idx_member_id (member_id),
    INDEX idx_period (period_year, period_month),
    INDEX idx_receipt_no (receipt_no)
) ENGINE=InnoDB;

-- Table: Association Expenses
CREATE TABLE IF NOT EXISTS expenses (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(150) NOT NULL,
    category ENUM('ELECTRICITY', 'SECURITY', 'CLEANING', 'LIFT_MAINTENANCE', 'GARDENING', 'REPAIRS', 'GENERATOR', 'WATER_SUPPLY', 'LEGAL_ADMIN', 'EVENTS', 'OTHER') NOT NULL DEFAULT 'OTHER',
    amount DECIMAL(10, 2) NOT NULL,
    expense_date DATE NOT NULL,
    vendor_name VARCHAR(100) NOT NULL,
    bill_invoice_no VARCHAR(100) DEFAULT NULL,
    payment_mode ENUM('CASH', 'UPI', 'NEFT', 'CHEQUE', 'NET_BANKING') NOT NULL DEFAULT 'NEFT',
    recorded_by INT NOT NULL,
    notes TEXT DEFAULT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (recorded_by) REFERENCES members(id),
    INDEX idx_category (category),
    INDEX idx_expense_date (expense_date)
) ENGINE=InnoDB;

-- Table: Email Log (For tracking receipt emails sent to residents)
CREATE TABLE IF NOT EXISTS email_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    receipt_id INT NOT NULL,
    member_id INT NOT NULL,
    recipient_email VARCHAR(100) NOT NULL,
    status ENUM('SENT', 'FAILED', 'SIMULATED') NOT NULL DEFAULT 'SENT',
    status_message TEXT DEFAULT NULL,
    sent_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (receipt_id) REFERENCES receipts(id) ON DELETE CASCADE,
    FOREIGN KEY (member_id) REFERENCES members(id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- Table: Digital Notice Board
CREATE TABLE IF NOT EXISTS tbl_notices (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    category VARCHAR(50) NOT NULL DEFAULT 'GENERAL',
    meeting_type VARCHAR(50) DEFAULT NULL,
    priority VARCHAR(20) NOT NULL DEFAULT 'NORMAL',
    is_pinned TINYINT(1) NOT NULL DEFAULT 0,
    posted_by VARCHAR(100) NOT NULL,
    posted_by_role VARCHAR(50) NOT NULL DEFAULT 'Executive Committee',
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_category (category),
    INDEX idx_meeting_type (meeting_type),
    INDEX idx_priority (priority),
    INDEX idx_is_pinned (is_pinned),
    INDEX idx_status (status)
) ENGINE=InnoDB;

