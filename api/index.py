import sys
import os

# Add parent project root to Python search path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app import app

# Expose WSGI application callable for Vercel Serverless
app.debug = False
handler = app
