import os
import pymysql
import pymysql.cursors
import bcrypt
from werkzeug.security import generate_password_hash, check_password_hash
from config import Config

def get_db_connection():
    """Establish connection to the MySQL database (supports both local and cloud databases)."""
    conn_params = {
        'host': Config.DB_HOST,
        'port': Config.DB_PORT,
        'user': Config.DB_USER,
        'password': Config.DB_PASSWORD,
        'database': Config.DB_NAME,
        'charset': 'utf8mb4',
        'cursorclass': pymysql.cursors.DictCursor,
        'autocommit': True,
        'connect_timeout': 10
    }
    
    if Config.DB_SSL:
        conn_params['ssl'] = {'ssl': {}}
        
    return pymysql.connect(**conn_params)

def query_db(query, params=None, one=False):
    """Execute SELECT query and return dictionary results safely."""
    conn = get_db_connection()
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

def execute_db(query, params=None):
    """Execute INSERT, UPDATE, or DELETE query and return last insert id or affected rows."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            if params:
                cur.execute(query, params)
            else:
                cur.execute(query)
            return cur.lastrowid
    finally:
        conn.close()

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

def init_db():
    """
    Initialize database extensions and verify tables in sddra_billing.
    Completely non-destructive: preserves all 44 members, 190 receipts, and 81 expenses.
    """
    try:
        conn = get_db_connection()
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
                
                print(f"[DB Init] Connected successfully to MySQL '{Config.DB_NAME}' on {Config.DB_HOST}:{Config.DB_PORT}")
        finally:
            conn.close()
    except Exception as e:
        print(f"[DB Warning] Could not connect to MySQL database ({e}).")
