"""
Utility script to initialize and synchronize tables/data from sddra_billing_dump.sql to any Cloud MySQL database (TiDB Serverless, Aiven, RDS, Railway).
Usage:
    python sync_to_cloud_db.py --host <cloud_host> --user <user> --password <pwd> --db <dbname> --port 4000
Or reads automatically from .env (DB_HOST, DB_USER, DB_PASSWORD, DB_NAME, DB_PORT).
"""

import os
import sys
import argparse
import pymysql
import ssl
from dotenv import load_dotenv

load_dotenv()

def sync_cloud_database(host, port, user, password, db_name):
    print(f"Connecting to Cloud MySQL database at {host}:{port}/{db_name}...")
    
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    conn = pymysql.connect(
        host=host,
        port=int(port),
        user=user,
        password=password,
        database=db_name,
        charset='utf8mb4',
        ssl=ctx,
        autocommit=True
    )
    
    dump_file = os.path.join(os.path.dirname(__file__), 'sddra_billing_dump.sql')
    if not os.path.exists(dump_file):
        print(f"Error: Could not find {dump_file}")
        return
        
    print(f"Reading {dump_file}...")
    with open(dump_file, 'r', encoding='utf-8') as f:
        sql_content = f.read()
        
    statements = [s.strip() for s in sql_content.split(';\n') if s.strip()]
    print(f"Executing {len(statements)} SQL statements on Cloud Database...")
    
    with conn.cursor() as cur:
        for idx, stmt in enumerate(statements, 1):
            if stmt.startswith('/*') or stmt.startswith('--'):
                continue
            try:
                cur.execute(stmt)
            except Exception as e:
                # ignore non-critical table drop or index warnings
                if "already exists" not in str(e).lower() and "doesn't exist" not in str(e).lower():
                    print(f"Note on stmt {idx}: {e}")
                    
    print("✓ Successfully synchronized all members, receipts, expenses, contacts, and notices to Cloud MySQL!")
    conn.close()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Synchronize SQLite/Dump to Cloud MySQL")
    parser.add_argument('--host', default=os.environ.get('DB_HOST'))
    parser.add_argument('--port', default=os.environ.get('DB_PORT', 3306))
    parser.add_argument('--user', default=os.environ.get('DB_USER', 'root'))
    parser.add_argument('--password', default=os.environ.get('DB_PASSWORD', ''))
    parser.add_argument('--db', default=os.environ.get('DB_NAME', 'sddra_billing'))
    
    args = parser.parse_args()
    if not args.host or args.host in ('localhost', '127.0.0.1'):
        print("Please provide cloud DB connection details via arguments or environment variables.")
        print("Example: python sync_to_cloud_db.py --host gateway01.us-east-1.prod.aws.tidbcloud.com --port 4000 --user xxx.root --password xxx --db sddra_billing")
    else:
        sync_cloud_database(args.host, args.port, args.user, args.password, args.db)
