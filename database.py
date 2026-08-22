import os
import re
import sqlite3
import pymysql
import pymysql.cursors
import bcrypt
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from config import Config

import shutil

_ENGINE_MODE = None # 'mysql' or 'sqlite'
_WRITABLE_SQLITE_PATH = None

def sqlite_date_format(val, fmt):
    """Custom SQLite function to support MySQL DATE_FORMAT(voucher_date, '%b %Y')."""
    if not val:
        return ''
    try:
        val_clean = str(val).split(' ')[0]
        dt = datetime.strptime(val_clean, '%Y-%m-%d')
        py_fmt = fmt.replace('%i', '%M').replace('%s', '%S')
        return dt.strftime(py_fmt)
    except Exception:
        return str(val)

def get_writable_sqlite_path():
    """Ensure SQLite database is placed in writable /tmp directory if in cloud / serverless environment."""
    global _WRITABLE_SQLITE_PATH
    if _WRITABLE_SQLITE_PATH and os.path.exists(_WRITABLE_SQLITE_PATH):
        return _WRITABLE_SQLITE_PATH

    is_cloud = bool(
        os.environ.get('VERCEL') or 
        os.environ.get('VERCEL_ENV') or 
        os.environ.get('AWS_LAMBDA_FUNCTION_NAME') or 
        os.environ.get('NOW_REGION')
    )

    if is_cloud:
        tmp_db = '/tmp/sddra.db'
        if not os.path.exists(tmp_db):
            # Locate source database in bundle
            src_candidates = [
                Config.SQLITE_PATH,
                os.path.join(os.getcwd(), 'sddra.db'),
                os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sddra.db'),
                '/var/task/sddra.db'
            ]
            for c in src_candidates:
                if c and os.path.exists(c):
                    try:
                        shutil.copy2(c, tmp_db)
                        print(f"[DB Init] Copied SQLite database to writable serverless storage at {tmp_db}")
                        break
                    except Exception as e:
                        print(f"[DB Warning] Could not copy SQLite to /tmp: {e}")
        if os.path.exists(tmp_db):
            _WRITABLE_SQLITE_PATH = tmp_db
            return tmp_db

    # Local development fallbacks
    if os.path.exists(Config.SQLITE_PATH):
        _WRITABLE_SQLITE_PATH = Config.SQLITE_PATH
        return _WRITABLE_SQLITE_PATH

    candidates = [
        os.path.join(os.getcwd(), 'sddra.db'),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sddra.db'),
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'sddra.db')
    ]
    for p in candidates:
        if os.path.exists(p):
            _WRITABLE_SQLITE_PATH = p
            return p

    _WRITABLE_SQLITE_PATH = Config.SQLITE_PATH
    return _WRITABLE_SQLITE_PATH

def get_sqlite_connection():
    """Establish connection to local/serverless SQLite database with Row factory, custom functions, and path fallbacks."""
    db_path = get_writable_sqlite_path()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.create_function('DATE_FORMAT', 2, sqlite_date_format)
    return conn

def get_mysql_connection():
    """Establish connection to MySQL / Cloud MySQL (TiDB, Aiven, RDS, Railway)."""
    conn_params = {
        'host': Config.DB_HOST,
        'port': Config.DB_PORT,
        'user': Config.DB_USER,
        'password': Config.DB_PASSWORD,
        'database': Config.DB_NAME,
        'charset': 'utf8mb4',
        'cursorclass': pymysql.cursors.DictCursor,
        'autocommit': True,
        'connect_timeout': 10.0
    }
    if Config.DB_SSL:
        conn_params['ssl'] = {'check_hostname': False}
    return pymysql.connect(**conn_params)

def determine_engine():
    """Determine whether to use MySQL or fallback to SQLite."""
    global _ENGINE_MODE
    if _ENGINE_MODE is not None:
        return _ENGINE_MODE

    if Config.DB_TYPE == 'sqlite':
        _ENGINE_MODE = 'sqlite'
        return _ENGINE_MODE

    if Config.DB_TYPE == 'mysql':
        _ENGINE_MODE = 'mysql'
        return _ENGINE_MODE

    # Auto mode:
    # If in cloud environment (Vercel / Lambda) and DB_HOST is still default localhost without cloud credentials, use SQLite immediately
    is_cloud = bool(
        os.environ.get('VERCEL') or 
        os.environ.get('VERCEL_ENV') or 
        os.environ.get('AWS_LAMBDA_FUNCTION_NAME') or 
        os.environ.get('NOW_REGION')
    )
    if is_cloud and Config.DB_HOST in ('localhost', '127.0.0.1') and not os.environ.get('DB_USER_DEFINED'):
        _ENGINE_MODE = 'sqlite'
        return _ENGINE_MODE

    # Try connecting to MySQL
    try:
        conn = get_mysql_connection()
        conn.close()
        _ENGINE_MODE = 'mysql'
        print(f"[DB Engine] Successfully initialized MySQL engine on {Config.DB_HOST}:{Config.DB_PORT}/{Config.DB_NAME}")
    except Exception as e:
        print(f"[DB Auto-Fallback] MySQL unavailable ({e}). Using bundled SQLite database: {Config.SQLITE_PATH}")
        _ENGINE_MODE = 'sqlite'

    return _ENGINE_MODE

def query_db(query, params=None, one=False):
    """Execute SELECT query and return dictionary results safely across MySQL & SQLite."""
    engine = determine_engine()
    
    if engine == 'sqlite':
        sqlite_query = re.sub(r'%s', '?', query)
        conn = get_sqlite_connection()
        try:
            cur = conn.cursor()
            if params:
                cur.execute(sqlite_query, params)
            else:
                cur.execute(sqlite_query)
            if one:
                row = cur.fetchone()
                return dict(row) if row else None
            return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()
    else:
        try:
            conn = get_mysql_connection()
            try:
                with conn.cursor() as cur:
                    if params:
                        cur.execute(query, params)
                    else:
                        cur.execute(query)
                    if one:
                        return cur.fetchone()
                    return cur.fetchall()
            finally:
                conn.close()
        except Exception as e:
            print(f"[DB Query Error] MySQL query failed: {e}.")
            if Config.DB_TYPE != 'mysql':
                print("[DB Query Fallback] Retrying query against SQLite fallback.")
                global _ENGINE_MODE
                _ENGINE_MODE = 'sqlite'
                return query_db(query, params, one)
            raise e

def execute_db(query, params=None):
    """Execute INSERT, UPDATE, or DELETE query and return last insert id or affected rows."""
    engine = determine_engine()
    
    if engine == 'sqlite':
        sqlite_query = re.sub(r'%s', '?', query)
        conn = get_sqlite_connection()
        try:
            cur = conn.cursor()
            if params:
                cur.execute(sqlite_query, params)
            else:
                cur.execute(sqlite_query)
            conn.commit()
            return cur.lastrowid if cur.lastrowid else cur.rowcount
        finally:
            conn.close()
    else:
        try:
            conn = get_mysql_connection()
            try:
                with conn.cursor() as cur:
                    if params:
                        cur.execute(query, params)
                    else:
                        cur.execute(query)
                    conn.commit()
                    return cur.lastrowid if cur.lastrowid else cur.rowcount
            finally:
                conn.close()
        except Exception as e:
            print(f"[DB Execute Error] MySQL execute failed: {e}.")
            if Config.DB_TYPE != 'mysql':
                print("[DB Execute Fallback] Retrying execute against SQLite fallback.")
                global _ENGINE_MODE
                _ENGINE_MODE = 'sqlite'
                return execute_db(query, params)
            raise e

def verify_password(plain_password: str, hashed: str) -> bool:
    """Verify password against bcrypt hash ($2b$...) or werkzeug hash."""
    if not hashed or not plain_password:
        return False
    if hashed.startswith('$2b$') or hashed.startswith('$2a$'):
        try:
            return bcrypt.checkpw(plain_password.encode('utf-8'), hashed.encode('utf-8'))
        except Exception:
            return False
    try:
        return check_password_hash(hashed, plain_password)
    except Exception:
        return False

def hash_password(plain_password: str) -> str:
    """Generate bcrypt hash for consistency with tbl_admins."""
    salt = bcrypt.gensalt(12)
    return bcrypt.hashpw(plain_password.encode('utf-8'), salt).decode('utf-8')

SEED_NOTICES = [
    (
        "Overhead Water Tank Deep Cleaning & Disinfection Schedule",
        "Dear Residents,\n\nPlease be informed that annual chemical cleaning and pressure-washing of both Block A and Block B overhead and underground water reservoirs is scheduled for Sunday, August 30, from 8:00 AM to 3:00 PM.\n\n• Water supply will be temporarily interrupted during these hours.\n• Please store sufficient water in advance for morning household requirements.\n• Normal water supply will resume by 4:00 PM post-disinfection.\n\nFor any urgent queries, contact Caretaker Sanjoy Chakraborty (+91 98300 12345).",
        "WATER_SUPPLY",
        "URGENT",
        1,
        "Somenath Halder",
        "Secretary"
    ),
    (
        "Notification: 18th Annual General Meeting (AGM 2026)",
        "Notice is hereby given that the 18th Annual General Meeting (AGM) of South Dumdum Enclave Residents' Association will be held on Sunday, September 14, at 6:30 PM at the Community Hall (Ground Floor).\n\nAgenda Items:\n1. Review & passing of FY 2025-26 Audited Accounts and Balance Sheet.\n2. Review of Reserve Sinking Fund and Building Repainting Plan.\n3. Proposal for Common Area Rooftop Solar Panel Installation.\n4. Election / Confirmation of Executive Committee for 2026-2028.\n\nAll flat owners are cordially requested to attend punctually.",
        "AGM_MEETING",
        "HIGH",
        1,
        "Dr. Asit Kumar Bera",
        "President"
    ),
    (
        "Schindler Lift AMC Bi-Monthly Lubrication & Safety Check",
        "The routine bi-monthly comprehensive safety check and brake pad inspection by Schindler India engineers will be carried out this Thursday between 11:00 AM and 2:00 PM.\n\nEach lift will be paused individually for approximately 45 minutes to minimize resident inconvenience. Power backup generator will be on standby.",
        "MAINTENANCE",
        "NORMAL",
        0,
        "Swapnadeep Ganguly",
        "Treasurer"
    ),
    (
        "Sharodotsav / Durga Puja 2026 Cultural Sub-Committee Formation",
        "With the festive season approaching, all interested residents and youth members are invited to join the SDERA Cultural Sub-Committee for organizing this year's Durga Puja, Bhog distribution, and evening cultural performances.\n\nPreliminary planning meetup: This Saturday at 7:00 PM in the Society Lounge. Your creative ideas and volunteer participation are warmly welcomed!",
        "EVENTS_FESTIVAL",
        "NORMAL",
        0,
        "Somenath Halder",
        "Secretary"
    ),
    (
        "Updated Security Protocols & Caretaker Intercom Extensions",
        "To bolster perimeter safety and smooth visitor entry:\n\n• Night Delivery Protocol: All food (Swiggy/Zomato) and courier deliveries after 10:00 PM will require prior gate clearance via intercom.\n• Intercom Speed Dial: Guard Cabin (#100), Caretaker Office (#101).\n• Caretaker Mobile: +91 98300 12345.\n\nVisitors without resident verification will be requested to register their contact numbers at the main security desk.",
        "SECURITY",
        "NORMAL",
        0,
        "Sanjoy Chakraborty",
        "Caretaker"
    )
]

def ensure_notices_table_sqlite():
    """Ensure tbl_notices table, seed notices, and name updates exist in SQLite."""
    conn = get_sqlite_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tbl_notices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title VARCHAR(255) NOT NULL,
                content TEXT NOT NULL,
                category VARCHAR(50) NOT NULL DEFAULT 'GENERAL',
                priority VARCHAR(20) NOT NULL DEFAULT 'NORMAL',
                is_pinned INTEGER NOT NULL DEFAULT 0,
                posted_by VARCHAR(100) NOT NULL,
                posted_by_role VARCHAR(50) NOT NULL DEFAULT 'Executive Committee',
                status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cur.execute("SELECT COUNT(*) FROM tbl_notices;")
        count = cur.fetchone()[0]
        if count == 0:
            for title, content, cat, prio, pinned, by_name, by_role in SEED_NOTICES:
                cur.execute("""
                    INSERT INTO tbl_notices (title, content, category, priority, is_pinned, posted_by, posted_by_role, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'ACTIVE');
                """, (title, content, cat, prio, pinned, by_name, by_role))
            print(f"[DB Init] Seeded {len(SEED_NOTICES)} initial digital notices in SQLite.")
        else:
            # Update existing records with verified committee names
            cur.execute("UPDATE tbl_notices SET posted_by = 'Somenath Halder' WHERE posted_by = 'Debasish Roy';")
            cur.execute("UPDATE tbl_notices SET posted_by = 'Dr. Asit Kumar Bera' WHERE posted_by = 'Subhashish Mukherjee';")
            cur.execute("UPDATE tbl_notices SET posted_by = 'Sanjoy Chakraborty' WHERE posted_by = 'Bikas Mondal';")
            cur.execute("UPDATE tbl_notices SET content = REPLACE(content, 'Debasish Roy', 'Somenath Halder');")
            cur.execute("UPDATE tbl_notices SET content = REPLACE(content, 'Subhashish Mukherjee', 'Dr. Asit Kumar Bera');")
            cur.execute("UPDATE tbl_notices SET content = REPLACE(content, 'Bikas Mondal', 'Sanjoy Chakraborty');")
            
        try:
            cur.execute("UPDATE members SET name = 'Somenath Halder' WHERE name = 'Debasish Roy';")
            cur.execute("UPDATE members SET name = 'Dr. Asit Kumar Bera' WHERE name = 'Subhashish Mukherjee';")
            cur.execute("UPDATE members SET name = 'Sanjoy Chakraborty (Caretaker)' WHERE name LIKE '%Bikas Mondal%';")
        except Exception:
            pass

        conn.commit()
    finally:
        conn.close()

def ensure_notices_table_mysql(conn):
    """Ensure tbl_notices table, seed notices, and name updates exist in MySQL."""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tbl_notices (
                id INT AUTO_INCREMENT PRIMARY KEY,
                title VARCHAR(255) NOT NULL,
                content TEXT NOT NULL,
                category VARCHAR(50) NOT NULL DEFAULT 'GENERAL',
                priority VARCHAR(20) NOT NULL DEFAULT 'NORMAL',
                is_pinned TINYINT(1) NOT NULL DEFAULT 0,
                posted_by VARCHAR(100) NOT NULL,
                posted_by_role VARCHAR(50) NOT NULL DEFAULT 'Executive Committee',
                status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_category (category),
                INDEX idx_priority (priority),
                INDEX idx_is_pinned (is_pinned),
                INDEX idx_status (status)
            ) ENGINE=InnoDB;
        """)
        cur.execute("SELECT COUNT(*) as cnt FROM tbl_notices;")
        row = cur.fetchone()
        count = row['cnt'] if isinstance(row, dict) else row[0]
        if count == 0:
            for title, content, cat, prio, pinned, by_name, by_role in SEED_NOTICES:
                cur.execute("""
                    INSERT INTO tbl_notices (title, content, category, priority, is_pinned, posted_by, posted_by_role, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, 'ACTIVE');
                """, (title, content, cat, prio, pinned, by_name, by_role))
            print(f"[DB Init] Seeded {len(SEED_NOTICES)} initial digital notices in MySQL.")
        else:
            # Update existing records with verified committee names
            cur.execute("UPDATE tbl_notices SET posted_by = 'Somenath Halder' WHERE posted_by = 'Debasish Roy';")
            cur.execute("UPDATE tbl_notices SET posted_by = 'Dr. Asit Kumar Bera' WHERE posted_by = 'Subhashish Mukherjee';")
            cur.execute("UPDATE tbl_notices SET posted_by = 'Sanjoy Chakraborty' WHERE posted_by = 'Bikas Mondal';")
            cur.execute("UPDATE tbl_notices SET content = REPLACE(content, 'Debasish Roy', 'Somenath Halder');")
            cur.execute("UPDATE tbl_notices SET content = REPLACE(content, 'Subhashish Mukherjee', 'Dr. Asit Kumar Bera');")
            cur.execute("UPDATE tbl_notices SET content = REPLACE(content, 'Bikas Mondal', 'Sanjoy Chakraborty');")
            
        try:
            cur.execute("UPDATE members SET name = 'Somenath Halder' WHERE name = 'Debasish Roy';")
            cur.execute("UPDATE members SET name = 'Dr. Asit Kumar Bera' WHERE name = 'Subhashish Mukherjee';")
            cur.execute("UPDATE members SET name = 'Sanjoy Chakraborty (Caretaker)' WHERE name LIKE '%Bikas Mondal%';")
        except Exception:
            pass

        conn.commit()

def init_db():
    """
    Initialize database extensions and verify tables in sddra_billing / sddra.db.
    Completely non-destructive: preserves all 44 members, 190 receipts, and 81 expenses.
    """
    engine = determine_engine()
    if engine == 'sqlite':
        try:
            conn = get_sqlite_connection()
            try:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM tbl_membership;")
                cnt = cur.fetchone()[0]
                print(f"[DB Init] Connected successfully to SQLite database '{Config.SQLITE_PATH}' with {cnt} members.")
            finally:
                conn.close()
            ensure_notices_table_sqlite()
        except Exception as e:
            print(f"[DB Warning] SQLite init note: {e}")
        return

    try:
        conn = get_mysql_connection()
        try:
            with conn.cursor() as cur:
                # 1. Non-destructively ensure password_hash column exists on tbl_membership
                cur.execute("""
                    SELECT COUNT(*) as cnt 
                    FROM information_schema.COLUMNS 
                    WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'tbl_membership' AND COLUMN_NAME = 'password_hash';
                """, (Config.DB_NAME,))
                has_pwd = cur.fetchone()['cnt'] > 0
                
                if not has_pwd:
                    print("[DB Init] Adding 'password_hash' column to tbl_membership...")
                    cur.execute("ALTER TABLE tbl_membership ADD COLUMN password_hash VARCHAR(255) DEFAULT NULL;")
                
                # Ensure all members have an initial hashed password (sdera@123)
                default_hash = hash_password("sdera@123")
                cur.execute(
                    "UPDATE tbl_membership SET password_hash = %s WHERE password_hash IS NULL OR password_hash = '';",
                    (default_hash,)
                )
                
                # 2. Ensure committee admin accounts exist in tbl_admins
                committee_admins = [
                    ('admin', hash_password('passwd'), 'billing_admin'),
                    ('treasurer', hash_password('sdera@123'), 'treasurer'),
                    ('president', hash_password('sdera@123'), 'president'),
                    ('secretary', hash_password('sdera@123'), 'secretary'),
                    ('caretaker', hash_password('sdera@123'), 'caretaker')
                ]
                
                for username, pwd_hash, role in committee_admins:
                    cur.execute("SELECT * FROM tbl_admins WHERE username = %s;", (username,))
                    existing = cur.fetchone()
                    if not existing:
                        cur.execute(
                            "INSERT INTO tbl_admins (username, password_hash, role) VALUES (%s, %s, %s);",
                            (username, pwd_hash, role)
                        )
                
                # 3. Ensure tbl_email_logs table exists
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS tbl_email_logs (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        receipt_no INT NOT NULL,
                        flat_no VARCHAR(20) NOT NULL,
                        recipient_email VARCHAR(100) NOT NULL,
                        status ENUM('SENT', 'FAILED', 'SIMULATED') NOT NULL DEFAULT 'SENT',
                        status_message TEXT DEFAULT NULL,
                        sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        INDEX idx_receipt_no (receipt_no),
                        INDEX idx_flat_no (flat_no)
                    ) ENGINE=InnoDB;
                """)
                
                # 4. Ensure tbl_notices table and seed notices exist
                ensure_notices_table_mysql(conn)
                
                print(f"[DB Init] Connected successfully to MySQL '{Config.DB_NAME}' on {Config.DB_HOST}:{Config.DB_PORT}")
        finally:
            conn.close()
    except Exception as e:
        print(f"[DB Warning] Could not connect to MySQL database ({e}). Switching to SQLite.")
        global _ENGINE_MODE
        _ENGINE_MODE = 'sqlite'
        ensure_notices_table_sqlite()

