import os
import sys
import argparse
from config import Config
from email_service import test_smtp_delivery

def main():
    parser = argparse.ArgumentParser(description="Test live SMTP email delivery and Gmail DKIM/SPF alignment.")
    parser.add_argument("--to", help="Target email address to receive test email", default=None)
    parser.add_argument("--user", help="Override SMTP username / email", default=None)
    parser.add_argument("--password", help="Override SMTP password (e.g. Google App Password)", default=None)
    args = parser.parse_args()

    if args.user:
        Config.SMTP_USERNAME = args.user
    if args.password:
        Config.SMTP_PASSWORD = args.password

    print("=" * 65)
    print(" [*] SDERA Live Email & SMTP Delivery Test")
    print("=" * 65)
    print(f"SMTP Server     : {Config.SMTP_SERVER}:{Config.SMTP_PORT}")
    print(f"TLS Enabled     : {Config.SMTP_USE_TLS}")
    print(f"SMTP Username   : {Config.SMTP_USERNAME or '(NOT SET - Check Vercel/env)'}")
    print(f"SMTP Password   : {'******** (configured)' if Config.SMTP_PASSWORD else '(NOT SET - Check Vercel/env)'}")
    print(f"From Name       : {Config.SMTP_FROM_NAME}")
    print(f"From Address    : {Config.SMTP_USERNAME or Config.SMTP_FROM_EMAIL}")
    print(f"Test Recipient  : {args.to or Config.SMTP_USERNAME or Config.SMTP_FROM_EMAIL}")
    print("=" * 65)
    print("\nExecuting diagnostic steps...\n")

    result = test_smtp_delivery(recipient_email=args.to)

    for step in result.get("steps", []):
        try:
            print(step)
        except UnicodeEncodeError:
            print(step.encode('ascii', 'replace').decode('ascii'))

    print("\n" + "=" * 65)
    if result.get("success"):
        print("[SUCCESS] Live email sent and accepted by SMTP server.")
        print("Check the recipient inbox / spam folder to verify receipt.")
        print("=" * 65)
        sys.exit(0)
    else:
        print("[FAILED] SMTP delivery could not complete.")
        if result.get("error"):
            print(f"Error Details: {result.get('error')}")
        print("=" * 65)
        sys.exit(1)

if __name__ == "__main__":
    main()
