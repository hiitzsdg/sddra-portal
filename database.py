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

_CACHED_MYSQL_CONN = None
_CACHED_SQLITE_CONN = None

def get_sqlite_connection():
    """Establish connection to local/serverless SQLite database with Row factory, custom functions, and path fallbacks."""
    global _CACHED_SQLITE_CONN
    if _CACHED_SQLITE_CONN is not None:
        return _CACHED_SQLITE_CONN
    db_path = get_writable_sqlite_path()
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.create_function('DATE_FORMAT', 2, sqlite_date_format)
    _CACHED_SQLITE_CONN = conn
    return _CACHED_SQLITE_CONN

def get_mysql_connection():
    """Establish connection to MySQL / Cloud MySQL with connection keepalive and TLS session reuse."""
    global _CACHED_MYSQL_CONN
    if _CACHED_MYSQL_CONN is not None:
        try:
            _CACHED_MYSQL_CONN.ping(reconnect=True)
            return _CACHED_MYSQL_CONN
        except Exception:
            _CACHED_MYSQL_CONN = None

    conn_params = {
        'host': Config.DB_HOST,
        'port': Config.DB_PORT,
        'user': Config.DB_USER,
        'password': Config.DB_PASSWORD,
        'database': Config.DB_NAME,
        'charset': 'utf8mb4',
        'cursorclass': pymysql.cursors.DictCursor,
        'autocommit': True,
        'init_command': "SET time_zone='+05:30'",
        'connect_timeout': 10.0,
        'read_timeout': 10.0,
        'write_timeout': 10.0
    }
    use_ssl = Config.DB_SSL or any(cloud_dom in Config.DB_HOST.lower() for cloud_dom in ['tidb', 'aiven', 'planetscale', 'aws', 'rds', 'railway', 'supabase', 'neon'])
    if use_ssl:
        import ssl
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        conn_params['ssl'] = ctx
    _CACHED_MYSQL_CONN = pymysql.connect(**conn_params)
    return _CACHED_MYSQL_CONN

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
        _ENGINE_MODE = 'mysql'
        print(f"[DB Engine] Successfully initialized MySQL engine on {Config.DB_HOST}:{Config.DB_PORT}/{Config.DB_NAME}")
    except Exception as e:
        print(f"[DB Auto-Fallback] MySQL unavailable ({e}). Using bundled SQLite database: {Config.SQLITE_PATH}")
        _ENGINE_MODE = 'sqlite'

    return _ENGINE_MODE

def get_db():
    """Get or create request-scoped connection for low-latency query reuse."""
    engine = determine_engine()
    return get_sqlite_connection() if engine == 'sqlite' else get_mysql_connection()

def query_db(query, params=None, one=False):
    """Execute SELECT query and return dictionary results safely across MySQL & SQLite."""
    engine = determine_engine()
    
    if engine == 'sqlite':
        sqlite_query = re.sub(r'%s', '?', query)
        conn = get_db()
        cur = conn.cursor()
        if params:
            cur.execute(sqlite_query, params)
        else:
            cur.execute(sqlite_query)
        if one:
            row = cur.fetchone()
            return dict(row) if row else None
        return [dict(r) for r in cur.fetchall()]
    else:
        for attempt in range(2):
            try:
                conn = get_db()
                if hasattr(conn, 'ping'):
                    try:
                        conn.ping(reconnect=True)
                    except Exception:
                        pass
                with conn.cursor() as cur:
                    if params:
                        cur.execute(query, params)
                    else:
                        cur.execute(query)
                    if one:
                        return cur.fetchone()
                    return cur.fetchall()
            except Exception as e:
                print(f"[DB Query Error] Attempt {attempt+1} failed ({e}). Reconnecting...")
                try:
                    from flask import g, has_request_context
                    if has_request_context():
                        g.db_conn = get_mysql_connection()
                except Exception:
                    pass
                if attempt == 1:
                    raise e

def execute_db(query, params=None):
    """Execute INSERT, UPDATE, or DELETE query and return last insert id or affected rows."""
    engine = determine_engine()
    
    if engine == 'sqlite':
        sqlite_query = re.sub(r'%s', '?', query)
        conn = get_db()
        cur = conn.cursor()
        if params:
            cur.execute(sqlite_query, params)
        else:
            cur.execute(sqlite_query)
        conn.commit()
        return cur.lastrowid if cur.lastrowid else cur.rowcount
    else:
        for attempt in range(2):
            try:
                conn = get_db()
                if hasattr(conn, 'ping'):
                    try:
                        conn.ping(reconnect=True)
                    except Exception:
                        pass
                with conn.cursor() as cur:
                    if params:
                        cur.execute(query, params)
                    else:
                        cur.execute(query)
                    conn.commit()
                    return cur.lastrowid if cur.lastrowid else cur.rowcount
            except Exception as e:
                print(f"[DB Execute Error] Attempt {attempt+1} failed ({e}). Reconnecting...")
                try:
                    from flask import g, has_request_context
                    if has_request_context():
                        g.db_conn = get_mysql_connection()
                except Exception:
                    pass
                if attempt == 1:
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
        "Dear Residents,\n\nPlease be informed that annual chemical cleaning and pressure-washing of both Block A and Block B overhead and underground water reservoirs is scheduled for Sunday, August 30, from 8:00 AM to 3:00 PM.\n\n• Water supply will be temporarily interrupted during these hours.\n• Please store sufficient water in advance for morning household requirements.\n• Normal water supply will resume by 4:00 PM post-disinfection.\n\nFor any urgent queries, contact Caretaker Sanjoy Chakraborty (+91 80172 50621).",
        "WATER_SUPPLY",
        "URGENT",
        1,
        "Somenath Halder",
        "Secretary",
        None,
        None
    ),
    (
        "Notification: 18th Annual General Meeting (AGM 2026)",
        "Notice is hereby given that the 18th Annual General Meeting (AGM) of South Dumdum Enclave Residents' Association will be held on Sunday, September 14, at 6:30 PM at the Community Hall (Ground Floor).\n\nAgenda Items:\n1. Review & passing of FY 2025-26 Audited Accounts and Balance Sheet.\n2. Review of Reserve Sinking Fund and Building Repainting Plan.\n3. Proposal for Common Area Rooftop Solar Panel Installation.\n4. Election / Confirmation of Executive Committee for 2026-2028.\n\nAll flat owners are cordially requested to attend punctually.",
        "AGM_MEETING",
        "HIGH",
        1,
        "Dr. Asit Kumar Bera",
        "President",
        "AGM",
        "2026-09-14"
    ),
    (
        "Schindler Lift AMC Bi-Monthly Lubrication & Safety Check",
        "The routine bi-monthly comprehensive safety check and brake pad inspection by Schindler India engineers will be carried out this Thursday between 11:00 AM and 2:00 PM.\n\nEach lift will be paused individually for approximately 45 minutes to minimize resident inconvenience. Power backup generator will be on standby.",
        "MAINTENANCE",
        "NORMAL",
        0,
        "Swapnadeep Ganguly",
        "Treasurer",
        None,
        None
    ),
    (
        "Sharodotsav / Durga Puja 2026 Cultural Sub-Committee Formation",
        "With the festive season approaching, all interested residents and youth members are invited to join the SDERA Cultural Sub-Committee for organizing this year's Durga Puja, Bhog distribution, and evening cultural performances.\n\nPreliminary planning meetup: This Saturday at 7:00 PM in the Society Lounge. Your creative ideas and volunteer participation are warmly welcomed!",
        "EVENTS_FESTIVAL",
        "NORMAL",
        0,
        "Somenath Halder",
        "Secretary",
        None,
        None
    ),
    (
        "Updated Security Protocols & Caretaker Intercom Extensions",
        "To bolster perimeter safety and smooth visitor entry:\n\n• Night Delivery Protocol: All food (Swiggy/Zomato) and courier deliveries after 10:00 PM will require prior gate clearance via intercom.\n• Intercom Speed Dial: Guard Cabin (#100), Caretaker Office (#101).\n• Caretaker Mobile: +91 80172 50621.\n\nVisitors without resident verification will be requested to register their contact numbers at the main security desk.",
        "SECURITY",
        "NORMAL",
        0,
        "Sanjoy Chakraborty",
        "Caretaker",
        None,
        None
    )
]

def ensure_notices_table_sqlite():
    """Ensure tbl_notices table, seed notices, meeting_type and meeting_date columns, and name updates exist in SQLite."""
    conn = get_sqlite_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tbl_notices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title VARCHAR(255) NOT NULL,
                content TEXT NOT NULL,
                category VARCHAR(50) NOT NULL DEFAULT 'GENERAL',
                meeting_type VARCHAR(50) DEFAULT NULL,
                meeting_date VARCHAR(50) DEFAULT NULL,
                priority VARCHAR(20) NOT NULL DEFAULT 'NORMAL',
                is_pinned INTEGER NOT NULL DEFAULT 0,
                posted_by VARCHAR(100) NOT NULL,
                posted_by_role VARCHAR(50) NOT NULL DEFAULT 'Executive Committee',
                status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Migration: Ensure meeting_type and meeting_date columns exist
        try:
            cur.execute("PRAGMA table_info(tbl_notices);")
            cols = [col[1] for col in cur.fetchall()]
            if 'meeting_type' not in cols:
                cur.execute("ALTER TABLE tbl_notices ADD COLUMN meeting_type VARCHAR(50) DEFAULT NULL;")
            if 'meeting_date' not in cols:
                cur.execute("ALTER TABLE tbl_notices ADD COLUMN meeting_date VARCHAR(50) DEFAULT NULL;")
        except Exception:
            pass

        cur.execute("""
            CREATE TABLE IF NOT EXISTS tbl_activity_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                actor_username TEXT NOT NULL,
                actor_name TEXT,
                actor_role TEXT DEFAULT 'MEMBER',
                flat_no TEXT DEFAULT '-',
                action_type TEXT NOT NULL,
                description TEXT NOT NULL,
                ip_address TEXT DEFAULT '127.0.0.1',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS tbl_whatsapp_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recipient_flat TEXT DEFAULT '-',
                recipient_phone TEXT NOT NULL,
                recipient_name TEXT DEFAULT '',
                message_type TEXT NOT NULL DEFAULT 'GENERIC',
                message_content TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'LINK_GENERATED',
                error_message TEXT DEFAULT NULL,
                sent_by TEXT DEFAULT 'Admin',
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        cur.execute("SELECT COUNT(*) FROM tbl_activity_logs;")
        act_cnt = cur.fetchone()[0]
        if act_cnt == 0:
            try:
                from seed_data import SEED_ACTIVITY_LOGS
                for log_r in SEED_ACTIVITY_LOGS:
                    cur.execute("""
                        INSERT INTO tbl_activity_logs (actor_username, actor_name, actor_role, flat_no, action_type, description, ip_address, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                    """, (
                        log_r['actor_username'],
                        log_r['actor_name'],
                        log_r['actor_role'],
                        log_r['flat_no'],
                        log_r['action_type'],
                        log_r['description'],
                        log_r.get('ip_address', '127.0.0.1'),
                        log_r['created_at']
                    ))
            except Exception:
                pass

        cur.execute("SELECT COUNT(*) FROM tbl_notices;")
        count = cur.fetchone()[0]
        if count == 0:
            for item in SEED_NOTICES:
                if len(item) == 9:
                    title, content, cat, prio, pinned, by_name, by_role, m_type, m_date = item
                elif len(item) == 8:
                    title, content, cat, prio, pinned, by_name, by_role, m_type = item
                    m_date = '2026-09-14' if cat == 'AGM_MEETING' else None
                else:
                    title, content, cat, prio, pinned, by_name, by_role = item[:7]
                    m_type = 'AGM' if cat == 'AGM_MEETING' else None
                    m_date = '2026-09-14' if cat == 'AGM_MEETING' else None
                cur.execute("""
                    INSERT INTO tbl_notices (title, content, category, meeting_type, meeting_date, priority, is_pinned, posted_by, posted_by_role, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVE');
                """, (title, content, cat, m_type, m_date, prio, pinned, by_name, by_role))
            print(f"[DB Init] Seeded {len(SEED_NOTICES)} initial digital notices in SQLite.")
        else:
            # Update existing records with verified committee names & meeting_types & meeting_dates
            cur.execute("UPDATE tbl_notices SET posted_by = 'Somenath Halder' WHERE posted_by = 'Debasish Roy';")
            cur.execute("UPDATE tbl_notices SET posted_by = 'Dr. Asit Kumar Bera' WHERE posted_by = 'Subhashish Mukherjee';")
            cur.execute("UPDATE tbl_notices SET posted_by = 'Sanjoy Chakraborty' WHERE posted_by = 'Bikas Mondal';")
            cur.execute("UPDATE tbl_notices SET content = REPLACE(content, 'Debasish Roy', 'Somenath Halder');")
            cur.execute("UPDATE tbl_notices SET content = REPLACE(content, 'Subhashish Mukherjee', 'Dr. Asit Kumar Bera');")
            cur.execute("UPDATE tbl_notices SET content = REPLACE(content, 'Bikas Mondal', 'Sanjoy Chakraborty');")
            cur.execute("UPDATE tbl_notices SET meeting_type = 'AGM' WHERE category = 'AGM_MEETING' AND (meeting_type IS NULL OR meeting_type = '');")
            cur.execute("UPDATE tbl_notices SET meeting_date = '2026-09-14' WHERE category = 'AGM_MEETING' AND (meeting_date IS NULL OR meeting_date = '');")
            
        # Ensure password hashes in SQLite are valid
        sdera_h = hash_password('sdera@123')
        cur.execute("UPDATE tbl_membership SET password_hash = ? WHERE password_hash IS NULL OR password_hash = '' OR password_hash LIKE '$2b$12$HxNkW%';", (sdera_h,))
        
        committee_admins = [
            ('admin', hash_password('passwd'), 'billing_admin'),
            ('treasurer', sdera_h, 'treasurer'),
            ('president', sdera_h, 'president'),
            ('secretary', sdera_h, 'secretary'),
            ('caretaker', sdera_h, 'caretaker')
        ]
        for username, pwd_hash, role in committee_admins:
            cur.execute("SELECT * FROM tbl_admins WHERE LOWER(username) = LOWER(?);", (username,))
            existing = cur.fetchone()
            if not existing:
                cur.execute("INSERT INTO tbl_admins (username, password_hash, role) VALUES (?, ?, ?);", (username, pwd_hash, role))
            else:
                existing_hash = existing['password_hash'] if isinstance(existing, dict) or hasattr(existing, 'keys') else existing[2]
                if not verify_password('passwd' if username == 'admin' else 'sdera@123', existing_hash):
                    cur.execute("UPDATE tbl_admins SET password_hash = ?, role = ? WHERE LOWER(username) = LOWER(?);", (pwd_hash, role, username))

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
    """Ensure tbl_notices table, seed notices, meeting_type and meeting_date columns, and name updates exist in MySQL."""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tbl_notices (
                id INT AUTO_INCREMENT PRIMARY KEY,
                title VARCHAR(255) NOT NULL,
                content TEXT NOT NULL,
                category VARCHAR(50) NOT NULL DEFAULT 'GENERAL',
                meeting_type VARCHAR(50) DEFAULT NULL,
                meeting_date VARCHAR(50) DEFAULT NULL,
                priority VARCHAR(20) NOT NULL DEFAULT 'NORMAL',
                is_pinned TINYINT(1) NOT NULL DEFAULT 0,
                posted_by VARCHAR(100) NOT NULL,
                posted_by_role VARCHAR(50) NOT NULL DEFAULT 'Executive Committee',
                status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_category (category),
                INDEX idx_meeting_type (meeting_type),
                INDEX idx_priority (priority),
                INDEX idx_is_pinned (is_pinned),
                INDEX idx_status (status)
            ) ENGINE=InnoDB;
        """)

        # Migration: Ensure meeting_type and meeting_date columns exist
        try:
            cur.execute("SHOW COLUMNS FROM tbl_notices LIKE 'meeting_type';")
            if not cur.fetchone():
                cur.execute("ALTER TABLE tbl_notices ADD COLUMN meeting_type VARCHAR(50) DEFAULT NULL AFTER category;")
                cur.execute("ALTER TABLE tbl_notices ADD INDEX idx_meeting_type (meeting_type);")
            cur.execute("SHOW COLUMNS FROM tbl_notices LIKE 'meeting_date';")
            if not cur.fetchone():
                cur.execute("ALTER TABLE tbl_notices ADD COLUMN meeting_date VARCHAR(50) DEFAULT NULL AFTER meeting_type;")
        except Exception:
            pass

        cur.execute("SELECT COUNT(*) as cnt FROM tbl_notices;")
        row = cur.fetchone()
        count = row['cnt'] if isinstance(row, dict) else row[0]
        if count == 0:
            for item in SEED_NOTICES:
                if len(item) == 9:
                    title, content, cat, prio, pinned, by_name, by_role, m_type, m_date = item
                elif len(item) == 8:
                    title, content, cat, prio, pinned, by_name, by_role, m_type = item
                    m_date = '2026-09-14' if cat == 'AGM_MEETING' else None
                else:
                    title, content, cat, prio, pinned, by_name, by_role = item[:7]
                    m_type = 'AGM' if cat == 'AGM_MEETING' else None
                    m_date = '2026-09-14' if cat == 'AGM_MEETING' else None
                cur.execute("""
                    INSERT INTO tbl_notices (title, content, category, meeting_type, meeting_date, priority, is_pinned, posted_by, posted_by_role, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'ACTIVE');
                """, (title, content, cat, m_type, m_date, prio, pinned, by_name, by_role))
            print(f"[DB Init] Seeded {len(SEED_NOTICES)} initial digital notices in MySQL.")
        else:
            # Update existing records with verified committee names & meeting_types & meeting_dates
            cur.execute("UPDATE tbl_notices SET posted_by = 'Somenath Halder' WHERE posted_by = 'Debasish Roy';")
            cur.execute("UPDATE tbl_notices SET posted_by = 'Dr. Asit Kumar Bera' WHERE posted_by = 'Subhashish Mukherjee';")
            cur.execute("UPDATE tbl_notices SET posted_by = 'Sanjoy Chakraborty' WHERE posted_by = 'Bikas Mondal';")
            cur.execute("UPDATE tbl_notices SET content = REPLACE(content, 'Debasish Roy', 'Somenath Halder');")
            cur.execute("UPDATE tbl_notices SET content = REPLACE(content, 'Subhashish Mukherjee', 'Dr. Asit Kumar Bera');")
            cur.execute("UPDATE tbl_notices SET meeting_type = 'AGM' WHERE category = 'AGM_MEETING' AND (meeting_type IS NULL OR meeting_type = '');")
            cur.execute("UPDATE tbl_notices SET meeting_date = '2026-09-14' WHERE category = 'AGM_MEETING' AND (meeting_date IS NULL OR meeting_date = '');")
        try:
            cur.execute("UPDATE members SET name = 'Somenath Halder' WHERE name = 'Debasish Roy';")
            cur.execute("UPDATE members SET name = 'Dr. Asit Kumar Bera' WHERE name = 'Subhashish Mukherjee';")
            cur.execute("UPDATE members SET name = 'Sanjoy Chakraborty (Caretaker)' WHERE name LIKE '%Bikas Mondal%';")
        except Exception:
            pass

        conn.commit()

def ensure_mysql_schema(conn):
    """Automatically provision complete tables and structured records from bundled SQLite dataset to MySQL / TiDB Cloud."""
    with conn.cursor() as cur:
        # 1. Create tables if they do not exist
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tbl_membership (
                id INT AUTO_INCREMENT PRIMARY KEY,
                flat_no VARCHAR(20) NOT NULL UNIQUE,
                member_name VARCHAR(150) NOT NULL,
                RvsdFlatSize INT DEFAULT 0,
                car_parking_space VARCHAR(20) DEFAULT '-',
                cps_owner TINYINT(1) DEFAULT 0,
                tws_owner TINYINT(1) DEFAULT 0,
                tws_count INT DEFAULT 0,
                flat_charges DECIMAL(10,2) DEFAULT 1.55,
                common_expenses DECIMAL(10,2) DEFAULT 170.00,
                cps_charges DECIMAL(10,2) DEFAULT 0.00,
                tws_charges DECIMAL(10,2) DEFAULT 0.00,
                capital_fund DECIMAL(10,2) DEFAULT 0.21,
                monthly_charge DECIMAL(10,2) DEFAULT 0.00,
                password_hash VARCHAR(255) DEFAULT NULL
            ) ENGINE=InnoDB;
        """)
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tbl_mbr_cntct (
                flat_no VARCHAR(20) PRIMARY KEY,
                mobile_num_1 VARCHAR(50) DEFAULT NULL,
                mobile_num_2 VARCHAR(50) DEFAULT NULL,
                email_1 VARCHAR(100) DEFAULT NULL,
                email_2 VARCHAR(100) DEFAULT NULL
            ) ENGINE=InnoDB;
        """)
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tbl_receipts (
                receipt_no INT PRIMARY KEY,
                flat_no VARCHAR(20) NOT NULL,
                member_name VARCHAR(150) NOT NULL,
                amount DECIMAL(10,2) NOT NULL,
                pymnt_mode VARCHAR(50) DEFAULT 'Online',
                subscription_type VARCHAR(50) DEFAULT 'Monthly',
                remarks VARCHAR(255) DEFAULT NULL,
                payment_date VARCHAR(50) DEFAULT NULL,
                receipt_date VARCHAR(50) DEFAULT NULL,
                coverage_start VARCHAR(50) DEFAULT NULL,
                coverage_end VARCHAR(50) DEFAULT NULL,
                INDEX idx_flat (flat_no)
            ) ENGINE=InnoDB;
        """)
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tbl_expenses (
                voucher_no INT PRIMARY KEY,
                voucher_date VARCHAR(50) NOT NULL,
                expense_description TEXT NOT NULL,
                particulars VARCHAR(255) DEFAULT NULL,
                spl_head VARCHAR(100) DEFAULT NULL,
                payment_by VARCHAR(100) DEFAULT 'Estate Manager',
                amount DECIMAL(10,2) NOT NULL,
                created_at VARCHAR(50) DEFAULT NULL
            ) ENGINE=InnoDB;
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS tbl_admins (
                admin_id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(50) NOT NULL UNIQUE,
                password_hash VARCHAR(255) NOT NULL,
                role VARCHAR(50) NOT NULL DEFAULT 'super_admin',
                email VARCHAR(100) DEFAULT NULL,
                phone VARCHAR(50) DEFAULT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB;
        """)
        try:
            cur.execute("ALTER TABLE tbl_admins ADD COLUMN email VARCHAR(100) DEFAULT NULL;")
        except Exception:
            pass
        try:
            cur.execute("ALTER TABLE tbl_admins ADD COLUMN phone VARCHAR(50) DEFAULT NULL;")
        except Exception:
            pass

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
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            ) ENGINE=InnoDB;
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS tbl_activity_logs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                actor_username VARCHAR(50) NOT NULL,
                actor_name VARCHAR(150) DEFAULT NULL,
                actor_role VARCHAR(50) NOT NULL DEFAULT 'MEMBER',
                flat_no VARCHAR(20) DEFAULT '-',
                action_type VARCHAR(50) NOT NULL,
                description TEXT NOT NULL,
                ip_address VARCHAR(50) DEFAULT '127.0.0.1',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_actor (actor_username),
                INDEX idx_action (action_type),
                INDEX idx_flat (flat_no),
                INDEX idx_time (created_at)
            ) ENGINE=InnoDB;
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS tbl_whatsapp_logs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                recipient_flat VARCHAR(20) DEFAULT '-',
                recipient_phone VARCHAR(50) NOT NULL,
                recipient_name VARCHAR(150) DEFAULT '',
                message_type VARCHAR(50) NOT NULL DEFAULT 'GENERIC',
                message_content TEXT NOT NULL,
                status VARCHAR(50) NOT NULL DEFAULT 'LINK_GENERATED',
                error_message TEXT DEFAULT NULL,
                sent_by VARCHAR(100) DEFAULT 'Admin',
                sent_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_wa_flat (recipient_flat),
                INDEX idx_wa_type (message_type),
                INDEX idx_wa_time (sent_at)
            ) ENGINE=InnoDB;
        """)
        conn.commit()

        # Seed tbl_activity_logs if empty
        try:
            cur.execute("SELECT COUNT(*) as cnt FROM tbl_activity_logs;")
            r_act = cur.fetchone()
            act_cnt = r_act['cnt'] if isinstance(r_act, dict) else r_act[0]
            if act_cnt == 0:
                from seed_data import SEED_ACTIVITY_LOGS
                act_sql = """
                    INSERT INTO tbl_activity_logs (actor_username, actor_name, actor_role, flat_no, action_type, description, ip_address, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
                """
                act_vals = [
                    (
                        r['actor_username'],
                        r['actor_name'],
                        r['actor_role'],
                        r['flat_no'],
                        r['action_type'],
                        r['description'],
                        r.get('ip_address', '127.0.0.1'),
                        r['created_at']
                    ) for r in SEED_ACTIVITY_LOGS
                ]
                cur.executemany(act_sql, act_vals)
                conn.commit()
                print(f"[DB Init] Seeded {len(act_vals)} records into tbl_activity_logs.")
        except Exception as e_act:
            print(f"[DB Warning] Could not seed tbl_activity_logs: {e_act}")

        # 2. Check if tbl_membership has data
        cur.execute("SELECT COUNT(*) as cnt FROM tbl_membership;")
        row = cur.fetchone()
        mbr_count = row['cnt'] if isinstance(row, dict) else row[0]
        
        if mbr_count == 0:
            print(f"[DB Init] Populating TiDB Cloud tables from embedded seed dataset...")
            try:
                from seed_data import SEED_MEMBERSHIP, SEED_CONTACTS, SEED_RECEIPTS, SEED_EXPENSES, SEED_ADMINS, SEED_NOTICES, SEED_ACTIVITY_LOGS
                table_map = {
                    'tbl_membership': SEED_MEMBERSHIP,
                    'tbl_mbr_cntct': SEED_CONTACTS,
                    'tbl_receipts': SEED_RECEIPTS,
                    'tbl_expenses': SEED_EXPENSES,
                    'tbl_admins': SEED_ADMINS,
                    'tbl_notices': SEED_NOTICES,
                    'tbl_activity_logs': SEED_ACTIVITY_LOGS
                }
                
                for tbl, rows in table_map.items():
                    if rows:
                        try:
                            cols = [c for c in rows[0].keys() if not (tbl == 'tbl_membership' and c == 'monthly_charge')]
                            placeholders = ", ".join(["%s"] * len(cols))
                            col_names = ", ".join([f"`{c}`" for c in cols])
                            insert_sql = f"REPLACE INTO `{tbl}` ({col_names}) VALUES ({placeholders});"
                            val_list = [tuple(r.get(c) for c in cols) for r in rows]
                            cur.executemany(insert_sql, val_list)
                            print(f"[DB Init] Synced {len(val_list)} records into `{tbl}`.")
                        except Exception as e_sync:
                            print(f"[DB Warning] Error seeding `{tbl}`: {e_sync}")
                conn.commit()
            except Exception as ex_all:
                print(f"[DB Warning] Seed data load error: {ex_all}")

_INIT_DB_DONE = False
SDERA_HASH = '$2b$12$pUxg9hjJZPcG01LOx65fkOmpNwGznM6UCHP5EoQ4RH8//ZDyFWHMS'
PASSWD_HASH = '$2b$12$N7Lq1igJAuiprlykUoyqWuY9u6V7VSEFzmscm4rsAhL2j9JrQ0Sha'

def init_db(force=False):
    """
    Initialize database extensions and verify tables in sddra_billing / sddra.db.
    Completely non-destructive: preserves all 44 members, 190 receipts, and 81 expenses.
    Optimized for high performance and fast serverless cold starts.
    """
    global _INIT_DB_DONE, _ENGINE_MODE
    if _INIT_DB_DONE and not force:
        return

    engine = determine_engine()
    if engine == 'sqlite':
        ensure_notices_table_sqlite()
        _INIT_DB_DONE = True
        return

    try:
        conn = get_mysql_connection()
        try:
            with conn.cursor() as cur:
                # Provision missing tables and ensure extensions exist
                ensure_mysql_schema(conn)
                
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
                
                # Fast update of default hashes without dynamic bcrypt calculation
                cur.execute(
                    "UPDATE tbl_membership SET password_hash = %s WHERE password_hash IS NULL OR password_hash = '' OR password_hash LIKE %s;",
                    (SDERA_HASH, '$2b$12$HxNkW%')
                )
                
                # 2. Ensure committee admin accounts exist and have valid password hashes in tbl_admins
                committee_admins = [
                    ('admin', PASSWD_HASH, 'billing_admin'),
                    ('treasurer', SDERA_HASH, 'treasurer'),
                    ('president', SDERA_HASH, 'president'),
                    ('secretary', SDERA_HASH, 'secretary'),
                    ('caretaker', SDERA_HASH, 'caretaker')
                ]
                
                for username, pwd_hash, role in committee_admins:
                    cur.execute("SELECT * FROM tbl_admins WHERE LOWER(username) = LOWER(%s);", (username,))
                    existing = cur.fetchone()
                    if not existing:
                        cur.execute(
                            "INSERT INTO tbl_admins (username, password_hash, role) VALUES (%s, %s, %s);",
                            (username, pwd_hash, role)
                        )
                    elif existing.get('password_hash', '').startswith('$2b$12$HxNkW') or existing.get('password_hash', '').startswith('$2b$12$MA9Sw'):
                        cur.execute(
                            "UPDATE tbl_admins SET password_hash = %s, role = %s WHERE admin_id = %s;",
                            (pwd_hash, role, existing['admin_id'])
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
        _INIT_DB_DONE = True
    except Exception as e:
        print(f"[DB Warning] Could not connect to MySQL database ({e}). Switching to SQLite.")
        _ENGINE_MODE = 'sqlite'
        ensure_notices_table_sqlite()
        _INIT_DB_DONE = True

