import os
import urllib.parse
from dotenv import load_dotenv

load_dotenv()

# Parse standard Cloud MySQL connection strings (DATABASE_URL, MYSQL_URL, TIDB_URL)
_db_url = os.environ.get('DATABASE_URL') or os.environ.get('MYSQL_URL') or os.environ.get('TIDB_URL') or os.environ.get('JAWSDB_URL')
_parsed_host = None
_parsed_port = None
_parsed_user = None
_parsed_password = None
_parsed_name = None

if _db_url:
    try:
        norm_url = _db_url
        if norm_url.startswith('mysql2://'):
            norm_url = 'mysql://' + norm_url[9:]
        _url = urllib.parse.urlparse(norm_url)
        _parsed_host = _url.hostname
        _parsed_port = _url.port
        _parsed_user = urllib.parse.unquote(_url.username) if _url.username else None
        _parsed_password = urllib.parse.unquote(_url.password) if _url.password else None
        _path = _url.path.lstrip('/')
        if '?' in _path:
            _path = _path.split('?')[0]
        _parsed_name = _path if _path else None
    except Exception as _e:
        print(f"[Config Note] Could not parse database URL: {_e}")

_RESOLVED_HOST = (
    _parsed_host or 
    os.environ.get('TIDB_HOST') or 
    os.environ.get('MYSQL_HOST') or 
    os.environ.get('MYSQLHOST') or 
    os.environ.get('DB_HOST', 'localhost')
)

_RESOLVED_PORT = int(
    _parsed_port or 
    os.environ.get('TIDB_PORT') or 
    os.environ.get('MYSQL_PORT') or 
    os.environ.get('MYSQLPORT') or 
    os.environ.get('DB_PORT', 4000 if ('tidb' in str(_RESOLVED_HOST).lower()) else 3306)
)

_RESOLVED_USER = (
    _parsed_user or 
    os.environ.get('TIDB_USER') or 
    os.environ.get('MYSQL_USER') or 
    os.environ.get('MYSQLUSER') or 
    os.environ.get('DB_USER', 'root')
)

_RESOLVED_PASSWORD = (
    _parsed_password or 
    os.environ.get('TIDB_PASSWORD') or 
    os.environ.get('MYSQL_PASSWORD') or 
    os.environ.get('MYSQLPASSWORD') or 
    os.environ.get('DB_PASSWORD', 'passwd')
)

_RESOLVED_NAME = (
    _parsed_name or 
    os.environ.get('TIDB_DATABASE') or 
    os.environ.get('TIDB_DB_NAME') or 
    os.environ.get('MYSQL_DATABASE') or 
    os.environ.get('MYSQLDATABASE') or 
    os.environ.get('DB_NAME', 'sddra_billing')
)

_host_lower = str(_RESOLVED_HOST).lower()
_is_cloud_db = any(k in _host_lower for k in ['tidb', 'aiven', 'planetscale', 'aws', 'rds', 'railway', 'supabase', 'neon'])
_RESOLVED_SSL = (
    _is_cloud_db or 
    os.environ.get('DB_SSL', 'False').lower() in ('true', '1', 't') or 
    os.environ.get('TIDB_ENABLE_SSL', 'False').lower() in ('true', '1', 't') or
    os.environ.get('MYSQL_SSL', 'False').lower() in ('true', '1', 't')
)

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'sddra-billing-portal-secret-key-2026')
    
    # Database Configuration (Supports TiDB Cloud Serverless, Aiven, AWS RDS, Railway, MySQL, and SQLite fallback)
    DB_TYPE = os.environ.get('DB_TYPE', 'auto').lower() # 'auto', 'mysql', 'sqlite'
    DB_HOST = _RESOLVED_HOST
    DB_PORT = _RESOLVED_PORT
    DB_USER = _RESOLVED_USER
    DB_PASSWORD = _RESOLVED_PASSWORD
    DB_NAME = _RESOLVED_NAME
    DB_SSL = _RESOLVED_SSL
    
    SQLITE_PATH = os.environ.get('SQLITE_PATH', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sddra.db'))
    
    # SMTP Email Configuration
    SMTP_SERVER = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
    SMTP_PORT = int(os.environ.get('SMTP_PORT', 587))
    SMTP_USE_TLS = os.environ.get('SMTP_USE_TLS', 'True').lower() in ('true', '1', 't')
    SMTP_USERNAME = os.environ.get('SMTP_USERNAME', '')
    SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD', '')
    SMTP_FROM_EMAIL = os.environ.get('SMTP_FROM_EMAIL', 'sddenclave@gmail.com')
    SMTP_FROM_NAME = os.environ.get('SMTP_FROM_NAME', "South Dumdum Enclave Residents' Association")
    
    # Association Information
    ASSOCIATION_NAME = "SOUTH DUMDUM ENCLAVE RESIDENTS' ASSOCIATION"
    ASSOCIATION_REG_NO = "Regd. No. 08A, Dated: 12.04.2016"
    ASSOCIATION_ADDRESS = "62 RN GUHA ROAD, DUMDUM, KOLKATA – 700028"
    ASSOCIATION_EMAIL = "sddenclave@gmail.com"
    ASSOCIATION_PHONE = "+91-801-725-0621"
