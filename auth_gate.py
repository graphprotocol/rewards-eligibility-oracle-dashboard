#!/usr/bin/env python3
"""
REO Dashboard Authentication Gateway
====================================
Lightweight authentication layer for the REO Dashboard.
Uses email-based OTP authentication with 7-day session cookies.
"""

import os
import json
import hmac
import hashlib
import random
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from pathlib import Path
from bottle import Bottle, request, response, static_file, redirect, abort
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
COOKIE_SECRET = os.getenv('AUTH_COOKIE_SECRET', os.urandom(32).hex())
COOKIE_NAME = 'reo_auth_session'
COOKIE_MAX_AGE = 7 * 24 * 60 * 60  # 7 days in seconds
OTP_EXPIRY = 10 * 60  # 10 minutes in seconds
SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
SMTP_USER = os.getenv('SMTP_USER', '')
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD', '')
SMTP_FROM = os.getenv('SMTP_FROM', SMTP_USER)
DASHBOARD_URL = os.getenv('DASHBOARD_URL', 'https://dashboards.thegraph.foundation/reo/')

# Rate limiting (in-memory, simple)
rate_limit_store = {}  # {email: [timestamp1, timestamp2, ...]}
RATE_LIMIT_WINDOW = 60 * 60  # 1 hour
RATE_LIMIT_MAX_REQUESTS = 5  # Max 5 OTP requests per hour

# OTP storage (in-memory)
otp_store = {}  # {email: {'code': '123456', 'expires': timestamp}}

# Session storage (in-memory)
session_store = set()  # Set of valid session tokens

# Initialize Bottle app
app = Bottle()

# ============================================================================
# Helper Functions
# ============================================================================

def load_whitelist():
    """Load email whitelist from allowed_people.txt"""
    # Use absolute path for production deployment
    whitelist_file = Path('/var/www/reo-config/allowed_people.txt')
    if not whitelist_file.exists():
        print("⚠️  WARNING: allowed_people.txt not found! Creating example file...")
        with open(whitelist_file, 'w') as f:
            f.write("# Email whitelist - one email/pattern per line\n")
            f.write("# Examples:\n")
            f.write("# yaniv@edgeandnode.com\n")
            f.write("# *@thegraph.foundation\n")
            f.write("# *@edgeandnode.com\n")
        return []
    
    whitelist = []
    with open(whitelist_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                whitelist.append(line.lower())
    return whitelist

def is_email_allowed(email):
    """Check if email matches whitelist (supports wildcards)"""
    email = email.lower().strip()
    whitelist = load_whitelist()
    
    for pattern in whitelist:
        if pattern.startswith('*@'):
            # Wildcard domain match
            domain = pattern[2:]
            if email.endswith('@' + domain):
                return True
        elif email == pattern:
            # Exact match
            return True
    
    return False

def check_rate_limit(email):
    """Check if email has exceeded rate limit"""
    now = time.time()
    email = email.lower()
    
    # Clean old entries
    if email in rate_limit_store:
        rate_limit_store[email] = [
            ts for ts in rate_limit_store[email] 
            if now - ts < RATE_LIMIT_WINDOW
        ]
    
    # Check limit
    if email in rate_limit_store:
        if len(rate_limit_store[email]) >= RATE_LIMIT_MAX_REQUESTS:
            return False
    
    # Add new request
    if email not in rate_limit_store:
        rate_limit_store[email] = []
    rate_limit_store[email].append(now)
    
    return True

def generate_otp():
    """Generate 6-digit OTP code"""
    return ''.join([str(random.randint(0, 9)) for _ in range(6)])

def send_otp_email(email, otp_code):
    """Send OTP code via email"""
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = 'Your REO Dashboard Login Code'
        msg['From'] = SMTP_FROM
        msg['To'] = email
        
        # Create email body
        text = f"""
REO Dashboard - One-Time Password

Your login code is: {otp_code}

This code will expire in 10 minutes.

If you didn't request this code, please ignore this email.

---
The Graph Protocol - Rewards Eligibility Oracle Dashboard
{DASHBOARD_URL}
"""
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f4f4f4; margin: 0; padding: 20px; }}
        .container {{ max-width: 600px; margin: 0 auto; background-color: #ffffff; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        .header {{ text-align: center; margin-bottom: 30px; }}
        .logo {{ font-size: 24px; font-weight: bold; color: #6B46C1; }}
        .otp-code {{ background-color: #f0e7ff; border: 2px solid #6B46C1; border-radius: 8px; padding: 20px; text-align: center; margin: 20px 0; }}
        .code {{ font-size: 32px; font-weight: bold; color: #6B46C1; letter-spacing: 5px; }}
        .info {{ color: #666; font-size: 14px; margin: 20px 0; }}
        .footer {{ color: #999; font-size: 12px; margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee; text-align: center; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="logo">🔐 REO Dashboard</div>
        </div>
        <h2 style="color: #333;">Your Login Code</h2>
        <p>Use this one-time password to access the REO Dashboard:</p>
        <div class="otp-code">
            <div class="code">{otp_code}</div>
        </div>
        <p class="info">⏱️ This code will expire in <strong>10 minutes</strong>.</p>
        <p class="info">If you didn't request this code, please ignore this email.</p>
        <div class="footer">
            <p><strong>The Graph Protocol</strong></p>
            <p>Rewards Eligibility Oracle Dashboard</p>
            <p><a href="{DASHBOARD_URL}" style="color: #6B46C1;">{DASHBOARD_URL}</a></p>
        </div>
    </div>
</body>
</html>
"""
        
        part1 = MIMEText(text, 'plain')
        part2 = MIMEText(html, 'html')
        msg.attach(part1)
        msg.attach(part2)
        
        # Send email
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
        
        return True
    except Exception as e:
        print(f"❌ Error sending email: {e}")
        return False

def create_session_token(email):
    """Create signed session token"""
    timestamp = int(time.time())
    data = f"{email}:{timestamp}"
    signature = hmac.new(
        COOKIE_SECRET.encode(),
        data.encode(),
        hashlib.sha256
    ).hexdigest()
    return f"{data}:{signature}"

def verify_session_token(token):
    """Verify and extract email from session token"""
    try:
        parts = token.split(':')
        if len(parts) != 3:
            return None
        
        email, timestamp, signature = parts
        data = f"{email}:{timestamp}"
        
        # Verify signature
        expected_signature = hmac.new(
            COOKIE_SECRET.encode(),
            data.encode(),
            hashlib.sha256
        ).hexdigest()
        
        if not hmac.compare_digest(signature, expected_signature):
            return None
        
        # Check if token is expired
        token_age = time.time() - int(timestamp)
        if token_age > COOKIE_MAX_AGE:
            return None
        
        # Check if token is in session store
        if token in session_store:
            return email
        
        return None
    except:
        return None

def log_auth_event(event_type, email, success=True, details=''):
    """Log authentication events"""
    timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
    status = '✅' if success else '❌'
    print(f"{status} [{timestamp}] {event_type}: {email} - {details}")

# ============================================================================
# Authentication Middleware
# ============================================================================

def check_auth():
    """Check if user is authenticated"""
    cookie_value = request.get_cookie(COOKIE_NAME)
    if cookie_value:
        email = verify_session_token(cookie_value)
        if email:
            return email
    return None

# ============================================================================
# Routes
# ============================================================================

@app.route('/')
def index():
    """Main route - serve dashboard or login page"""
    email = check_auth()
    
    if email:
        # User is authenticated - serve dashboard from web root
        return static_file('index.html', root='/var/www/iproot/reo')
    else:
        # User not authenticated - serve login page from web root
        return static_file('login.html', root='/var/www/iproot/reo')

@app.route('/static/<filepath:path>')
def serve_static(filepath):
    """Serve static files (images, etc.) from web root"""
    return static_file(filepath, root='/var/www/iproot/reo')

@app.route('/<filename:re:.*\.(png|jpg|jpeg|gif|ico|css|js)>')
def serve_assets(filename):
    """Serve image and asset files directly"""
    return static_file(filename, root='/var/www/iproot/reo')

@app.post('/request-otp')
def request_otp():
    """Request OTP code via email"""
    try:
        data = request.json
        email = data.get('email', '').strip().lower()
        
        # Validate email format
        if not email or '@' not in email:
            return {'success': False, 'message': 'Invalid email address'}
        
        # Check whitelist
        if not is_email_allowed(email):
            log_auth_event('OTP_REQUEST', email, False, 'Email not whitelisted')
            return {'success': False, 'message': 'Email not authorized. Please contact an administrator.'}
        
        # Check rate limit
        if not check_rate_limit(email):
            log_auth_event('OTP_REQUEST', email, False, 'Rate limit exceeded')
            return {'success': False, 'message': 'Too many requests. Please try again later.'}
        
        # Generate OTP
        otp_code = generate_otp()
        otp_store[email] = {
            'code': otp_code,
            'expires': time.time() + OTP_EXPIRY
        }
        
        # Send email
        if send_otp_email(email, otp_code):
            log_auth_event('OTP_SENT', email, True, f'Code: {otp_code}')
            return {'success': True, 'message': 'Check your email for the login code'}
        else:
            log_auth_event('OTP_SEND_FAILED', email, False, 'Email delivery failed')
            return {'success': False, 'message': 'Failed to send email. Please try again.'}
    
    except Exception as e:
        print(f"❌ Error in request_otp: {e}")
        return {'success': False, 'message': 'An error occurred. Please try again.'}

@app.post('/verify-otp')
def verify_otp():
    """Verify OTP code and create session"""
    try:
        data = request.json
        email = data.get('email', '').strip().lower()
        otp_code = data.get('code', '').strip()
        
        # Check if OTP exists
        if email not in otp_store:
            log_auth_event('OTP_VERIFY', email, False, 'No OTP found')
            return {'success': False, 'message': 'Invalid or expired code'}
        
        stored_otp = otp_store[email]
        
        # Check if OTP expired
        if time.time() > stored_otp['expires']:
            del otp_store[email]
            log_auth_event('OTP_VERIFY', email, False, 'OTP expired')
            return {'success': False, 'message': 'Code expired. Please request a new one.'}
        
        # Verify code
        if otp_code != stored_otp['code']:
            log_auth_event('OTP_VERIFY', email, False, 'Invalid code')
            return {'success': False, 'message': 'Invalid code. Please try again.'}
        
        # OTP valid - create session
        del otp_store[email]
        session_token = create_session_token(email)
        session_store.add(session_token)
        
        # Set cookie
        response.set_cookie(
            COOKIE_NAME,
            session_token,
            max_age=COOKIE_MAX_AGE,
            path='/',
            secure=True,
            httponly=True,
            samesite='Strict'
        )
        
        log_auth_event('LOGIN_SUCCESS', email, True, 'Session created')
        return {'success': True, 'message': 'Login successful'}
    
    except Exception as e:
        print(f"❌ Error in verify_otp: {e}")
        return {'success': False, 'message': 'An error occurred. Please try again.'}

@app.route('/logout')
def logout():
    """Logout and clear session"""
    cookie_value = request.get_cookie(COOKIE_NAME)
    if cookie_value:
        email = verify_session_token(cookie_value)
        if email:
            session_store.discard(cookie_value)
            log_auth_event('LOGOUT', email, True, 'Session destroyed')
    
    response.delete_cookie(COOKIE_NAME, path='/')
    redirect('/')

@app.route('/health')
def health():
    """Health check endpoint"""
    return {'status': 'ok', 'timestamp': datetime.utcnow().isoformat()}

# ============================================================================
# Main
# ============================================================================

if __name__ == '__main__':
    print("=" * 60)
    print("🔐 REO Dashboard Authentication Gateway")
    print("=" * 60)
    
    # Check configuration
    if not SMTP_USER or not SMTP_PASSWORD:
        print("⚠️  WARNING: SMTP credentials not configured!")
        print("   Set SMTP_USER and SMTP_PASSWORD in .env file")
        print()
    
    whitelist = load_whitelist()
    print(f"📧 Loaded {len(whitelist)} email patterns from whitelist")
    print()
    
    # Check if index.html exists in web root
    if not Path('/var/www/iproot/reo/index.html').exists():
        print("⚠️  WARNING: index.html not found in /var/www/iproot/reo/!")
        print("   Run generate_dashboard.py first to create the dashboard")
        print()
    
    # Check if login.html exists in web root
    if not Path('/var/www/iproot/reo/login.html').exists():
        print("⚠️  WARNING: login.html not found in /var/www/iproot/reo/!")
        print("   Login page is missing - authentication will not work")
        print()
    
    print("🚀 Starting server...")
    print(f"   URL: http://localhost:8080")
    print(f"   Cookie expiry: {COOKIE_MAX_AGE // 86400} days")
    print(f"   OTP expiry: {OTP_EXPIRY // 60} minutes")
    print()
    print("Press Ctrl+C to stop")
    print("=" * 60)
    
    app.run(host='0.0.0.0', port=8080, debug=False, reloader=False)

