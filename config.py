import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'sddra-billing-portal-secret-key-2026')
    
    # Database Configuration (Supports Cloud MySQL e.g. TiDB/Aiven/AWS/Railway and bundled SQLite fallback)
    DB_TYPE = os.environ.get('DB_TYPE', 'auto').lower() # 'auto', 'mysql', 'sqlite'
    DB_HOST = os.environ.get('DB_HOST', 'localhost')
    DB_PORT = int(os.environ.get('DB_PORT', 3306))
    DB_USER = os.environ.get('DB_USER', 'root')
    DB_PASSWORD = os.environ.get('DB_PASSWORD', 'passwd')
    DB_NAME = os.environ.get('DB_NAME', 'sddra_billing')
    DB_SSL = os.environ.get('DB_SSL', 'False').lower() in ('true', '1', 't')
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
    ASSOCIATION_NAME = "South Dumdum Enclave Residents' Association"
    ASSOCIATION_REG_NO = "08A, Dated: 12.04.2016"
    ASSOCIATION_ADDRESS = "62 RN Guha Road, Dumdum Kolkata 700028"
    ASSOCIATION_EMAIL = "sddenclave@gmail.com"
    ASSOCIATION_PHONE = "+91-801-725-0621"
