# REO Dashboard Authentication System

## Overview

The REO Dashboard uses a **lightweight email-based OTP (One-Time Password) authentication system** to control access. This gatekeeps access provides secure, token-free authentication without modifying the existing dashboard generation logic.

## 🏗️ Architecture

```
User Request
     │
     ▼
┌─────────────────────┐
│   auth_gate.py      │  ←── Bottle.py Web Server (Port 8080)
│  (Auth Gateway)     │
└──────────┬──────────┘
           │
    [Check Cookie]
           │
     ┌─────┴─────┐
     │           │
Valid Cookie  No Cookie
     │           │
     ▼           ▼
Serve         Serve
index.html    login.html
  (Dashboard)   (Login)
                  │
            [User Login Flow]
                  │
            ┌─────┴─────┐
            │           │
      Email Entry   OTP Entry
            │           │
            ▼           ▼
      [Whitelist]  [Verify Code]
      [Send OTP]   [Set Cookie]
            │           │
            └─────┬─────┘
                  │
                  ▼
            Redirect to /
         (Serve Dashboard)
```

### Key Components

1. **auth_gate.py** - Authentication gateway server
2. **login.html** - Login page UI
3. **allowed_people.txt** - Email whitelist
4. **index.html** - Your existing dashboard (unchanged)
5. **generate_dashboard.py** - Your existing script (unchanged)

## ✨ Features

### Security Features
- ✅ **Email Whitelist**: Only authorized emails can access
- ✅ **Wildcard Domains**: Support `*@domain.com` patterns
- ✅ **OTP Authentication**: 6-digit one-time codes
- ✅ **Time-Limited OTPs**: Codes expire after 10 minutes
- ✅ **Signed Cookies**: Tamper-proof session tokens
- ✅ **7-Day Sessions**: Users stay logged in for a week
- ✅ **Rate Limiting**: Max 5 OTP requests per hour per email
- ✅ **Audit Logging**: All auth events logged to console
- ✅ **Secure Cookies**: HTTP-only, Secure, SameSite=Strict

### User Experience
- 🎯 **Two-Step Login**: Email → OTP verification
- 📧 **HTML Email**: Beautiful formatted OTP emails
- 🔄 **Auto-Redirect**: Seamless access after authentication
- 📱 **Mobile-Friendly**: Responsive login page
- ⚡ **Fast**: In-memory storage for speed
- 🎨 **Branded UI**: Matches dashboard design

## 📦 Installation

### Step 1: Install Dependencies

Add new dependencies to your environment:

```bash
pip3 install bottle
```

Or update `requirements.txt` and reinstall:

```bash
pip3 install -r requirements.txt
```

### Step 2: Configure Email Sending

Add SMTP configuration to your `.env` file:

```bash
# Authentication Configuration
AUTH_COOKIE_SECRET=your_random_secret_key_here_change_this

# SMTP Email Configuration
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM=your-email@gmail.com

# Dashboard URL (for email links)
DASHBOARD_URL=https://dashboards.thegraph.foundation/reo/
```

#### Gmail Setup (Recommended)

1. Enable 2-Factor Authentication on your Google account
2. Go to [Google App Passwords](https://myaccount.google.com/apppasswords)
3. Create an "App Password" for "Mail"
4. Use that 16-character password as `SMTP_PASSWORD`

#### Alternative SMTP Providers

**SendGrid:**
```bash
SMTP_SERVER=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USER=apikey
SMTP_PASSWORD=your_sendgrid_api_key
```

**AWS SES:**
```bash
SMTP_SERVER=email-smtp.us-east-1.amazonaws.com
SMTP_PORT=587
SMTP_USER=your_ses_smtp_username
SMTP_PASSWORD=your_ses_smtp_password
```

**Mailgun:**
```bash
SMTP_SERVER=smtp.mailgun.org
SMTP_PORT=587
SMTP_USER=postmaster@your-domain.mailgun.org
SMTP_PASSWORD=your_mailgun_smtp_password
```

### Step 3: Configure Email Whitelist

Edit `allowed_people.txt` to add authorized emails:

```bash
# Individual emails
yaniv@edgeandnode.com
admin@example.com

# Wildcard domains (all emails from these domains)
*@thegraph.foundation
*@edgeandnode.com
```

**Whitelist Format:**
- One email/pattern per line
- Lines starting with `#` are comments
- Empty lines are ignored
- Email matching is case-insensitive
- Supports exact emails: `user@domain.com`
- Supports wildcard domains: `*@domain.com`

### Step 4: Generate Cookie Secret

Generate a secure random secret for cookie signing:

```bash
python3 -c "import os; print(os.urandom(32).hex())"
```

Copy the output and set it as `AUTH_COOKIE_SECRET` in `.env`.

### Step 5: Test the System

Run the authentication gateway:

```bash
cd /home/graph/ftpbox/reo
python3 auth_gate.py
```

You should see:
```
============================================================
🔐 REO Dashboard Authentication Gateway
============================================================
📧 Loaded 3 email patterns from whitelist

🚀 Starting server...
   URL: http://localhost:8080
   Cookie expiry: 7 days
   OTP expiry: 10 minutes

Press Ctrl+C to stop
============================================================
```

Visit `http://localhost:8080` to test the login flow.

## 🚀 Deployment

### Production Deployment with Systemd

Create a systemd service for the authentication gateway:

#### 1. Create Service File

```bash
sudo nano /etc/systemd/system/reo_auth.service
```

Add the following content:

```ini
[Unit]
Description=REO Dashboard Authentication Gateway
After=network.target

[Service]
Type=simple
User=graph
WorkingDirectory=/home/graph/ftpbox/reo
ExecStart=/usr/bin/python3 /home/graph/ftpbox/reo/auth_gate.py
Restart=always
RestartSec=10
StandardOutput=append:/home/graph/ftpbox/reo/logs/auth_gateway.log
StandardError=append:/home/graph/ftpbox/reo/logs/auth_gateway.log

# Load environment variables
EnvironmentFile=/home/graph/ftpbox/reo/.env

[Install]
WantedBy=multi-user.target
```

#### 2. Enable and Start Service

```bash
# Create logs directory if it doesn't exist
mkdir -p /home/graph/ftpbox/reo/logs

# Reload systemd
sudo systemctl daemon-reload

# Enable service (start on boot)
sudo systemctl enable reo_auth.service

# Start service
sudo systemctl start reo_auth.service

# Check status
sudo systemctl status reo_auth.service

# View logs
tail -f /home/graph/ftpbox/reo/logs/auth_gateway.log
```

#### 3. Management Commands

```bash
# Restart after code changes
sudo systemctl restart reo_auth.service

# Stop service
sudo systemctl stop reo_auth.service

# View real-time logs
sudo journalctl -u reo_auth.service -f

# View recent logs
sudo journalctl -u reo_auth.service -n 50
```

### Nginx Reverse Proxy (Recommended for Production)

Configure Nginx to proxy requests to the auth gateway:

```nginx
server {
    listen 80;
    server_name dashboards.thegraph.foundation;
    
    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name dashboards.thegraph.foundation;
    
    # SSL Configuration
    ssl_certificate /etc/letsencrypt/live/dashboards.thegraph.foundation/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/dashboards.thegraph.foundation/privkey.pem;
    
    # Proxy to auth gateway
    location /reo/ {
        proxy_pass http://127.0.0.1:8080/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Important: preserve cookies
        proxy_cookie_path / /reo/;
    }
}
```

Reload Nginx:
```bash
sudo nginx -t
sudo systemctl reload nginx
```

### SSL/TLS Setup with Let's Encrypt

```bash
# Install certbot
sudo apt install certbot python3-certbot-nginx

# Get certificate
sudo certbot --nginx -d dashboards.thegraph.foundation

# Auto-renewal (certbot sets this up automatically)
sudo certbot renew --dry-run
```

## 🔐 How It Works

### Login Flow

1. **User visits dashboard** → `https://dashboards.thegraph.foundation/reo/`

2. **Auth gateway checks cookie**:
   - Valid cookie? → Serve `index.html` (dashboard)
   - No/invalid cookie? → Serve `login.html` (login page)

3. **User enters email**:
   - JavaScript sends POST to `/request-otp`
   - Server checks email against whitelist
   - If authorized: generate 6-digit OTP
   - Send OTP via email
   - Return success message

4. **User enters OTP code**:
   - JavaScript sends POST to `/verify-otp`
   - Server verifies code and expiry
   - If valid: create signed session token
   - Set secure 7-day cookie
   - Return success → JavaScript redirects to `/`

5. **User accesses dashboard**:
   - Auth gateway sees valid cookie
   - Serves `index.html` directly
   - User stays logged in for 7 days

### Session Management

**Cookie Format:**
```
email:timestamp:signature
```

**Example:**
```
user@example.com:1730696509:a3f5b2c8d1e4f7...
```

**Signature Verification:**
```python
signature = HMAC-SHA256(cookie_secret, "email:timestamp")
```

**Cookie Security:**
- `HttpOnly`: Cannot be accessed by JavaScript
- `Secure`: Only sent over HTTPS
- `SameSite=Strict`: CSRF protection
- `Max-Age=604800`: 7 days (7 * 24 * 60 * 60 seconds)

### OTP Storage

OTPs are stored in-memory (RAM):

```python
{
    "user@example.com": {
        "code": "123456",
        "expires": 1730697109  # Unix timestamp
    }
}
```

**Why in-memory?**
- ✅ Fast (no disk I/O)
- ✅ Simple (no database needed)
- ✅ Secure (cleared on restart)
- ✅ Short-lived (10-minute expiry)

**Trade-off:**
- ❌ OTPs lost on server restart (acceptable - user can request new one)

### Rate Limiting

Protection against OTP spam:

```python
{
    "user@example.com": [1730696509, 1730696709, ...]
}
```

**Limits:**
- Max **5 OTP requests** per email
- Within a **1-hour window**
- Old timestamps automatically cleaned up

## 🛠️ Configuration Options

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AUTH_COOKIE_SECRET` | Random | Secret key for signing cookies (CHANGE THIS!) |
| `SMTP_SERVER` | `smtp.gmail.com` | SMTP server hostname |
| `SMTP_PORT` | `587` | SMTP server port (587 for TLS, 465 for SSL) |
| `SMTP_USER` | (required) | SMTP username/email |
| `SMTP_PASSWORD` | (required) | SMTP password or app password |
| `SMTP_FROM` | Same as `SMTP_USER` | "From" address in emails |
| `DASHBOARD_URL` | Local URL | Dashboard URL for email links |

### Customization

**Change Cookie Expiry:**
```python
# In auth_gate.py
COOKIE_MAX_AGE = 14 * 24 * 60 * 60  # 14 days instead of 7
```

**Change OTP Expiry:**
```python
# In auth_gate.py
OTP_EXPIRY = 15 * 60  # 15 minutes instead of 10
```

**Change Rate Limits:**
```python
# In auth_gate.py
RATE_LIMIT_WINDOW = 2 * 60 * 60  # 2 hours
RATE_LIMIT_MAX_REQUESTS = 10  # 10 requests per window
```

**Customize Email Template:**
Edit the `send_otp_email()` function in `auth_gate.py` to modify email content and styling.

## 🔍 Monitoring & Logs

### Authentication Events

All authentication events are logged to console/log file:

```
✅ [2025-11-04 10:30:45 UTC] OTP_SENT: user@example.com - Code: 123456
✅ [2025-11-04 10:32:18 UTC] LOGIN_SUCCESS: user@example.com - Session created
❌ [2025-11-04 10:45:23 UTC] OTP_VERIFY: hacker@bad.com - Invalid code
✅ [2025-11-04 18:22:09 UTC] LOGOUT: user@example.com - Session destroyed
```

### Log Events

| Event | Success | Description |
|-------|---------|-------------|
| `OTP_REQUEST` | ✅ / ❌ | User requested OTP code |
| `OTP_SENT` | ✅ | OTP email sent successfully |
| `OTP_SEND_FAILED` | ❌ | Failed to send OTP email |
| `OTP_VERIFY` | ✅ / ❌ | User attempted to verify OTP |
| `LOGIN_SUCCESS` | ✅ | User logged in successfully |
| `LOGOUT` | ✅ | User logged out |

### View Logs

```bash
# Systemd service logs
sudo journalctl -u reo_auth.service -f

# Log file (if using systemd with log output)
tail -f /home/graph/ftpbox/reo/logs/auth_gateway.log

# Search for specific email
sudo journalctl -u reo_auth.service | grep "user@example.com"

# Show only errors
sudo journalctl -u reo_auth.service | grep "❌"

# Show login events
sudo journalctl -u reo_auth.service | grep "LOGIN_SUCCESS"
```

## 🐛 Troubleshooting

### Common Issues

#### 1. "Failed to send email"

**Cause:** SMTP configuration incorrect or blocked

**Solutions:**
- Verify `SMTP_USER` and `SMTP_PASSWORD` are correct
- For Gmail: use App Password, not regular password
- Check if SMTP port is correct (587 for TLS, 465 for SSL)
- Test SMTP connection manually:
```bash
python3 -c "import smtplib; smtplib.SMTP('smtp.gmail.com', 587).starttls()"
```

#### 2. "Email not authorized"

**Cause:** Email not in whitelist

**Solutions:**
- Add email to `allowed_people.txt`
- Check for typos in email address
- Ensure whitelist file has correct format
- Restart auth gateway after modifying whitelist

#### 3. Cookie not working / User redirected to login

**Cause:** Cookie security settings or proxy issues

**Solutions:**
- Ensure `Secure` flag is only set for HTTPS
- Check Nginx proxy preserves cookies
- Verify `AUTH_COOKIE_SECRET` is set and consistent
- Clear browser cookies and try again

#### 4. "Code expired"

**Cause:** User took longer than 10 minutes

**Solution:** Request a new code (this is normal behavior)

#### 5. Auth gateway not starting

**Cause:** Port already in use or missing dependencies

**Solutions:**
```bash
# Check if port 8080 is in use
sudo lsof -i :8080

# Kill process using port
sudo kill -9 <PID>

# Verify dependencies installed
pip3 list | grep bottle
```

### Debug Mode

Enable debug mode for detailed error messages:

```python
# In auth_gate.py, change the last line:
app.run(host='0.0.0.0', port=8080, debug=True, reloader=True)
```

**⚠️ WARNING:** Only use debug mode during development. Disable for production!

## 🔒 Security Best Practices

### DO:
- ✅ Use strong `AUTH_COOKIE_SECRET` (at least 32 random bytes)
- ✅ Use HTTPS in production (configure SSL/TLS)
- ✅ Use App Passwords for Gmail (not regular password)
- ✅ Regularly review `allowed_people.txt`
- ✅ Monitor auth logs for suspicious activity
- ✅ Keep whitelist file private (not in git)
- ✅ Use firewall to restrict port 8080 access (only from Nginx)

### DON'T:
- ❌ Don't commit `.env` file to git
- ❌ Don't share `AUTH_COOKIE_SECRET`
- ❌ Don't disable HTTPS in production
- ❌ Don't use debug mode in production
- ❌ Don't ignore failed login attempts
- ❌ Don't make whitelist file publicly accessible

## 📝 File Structure

```
/home/graph/ftpbox/reo/
├── auth_gate.py                 # NEW: Authentication gateway
├── login.html                   # NEW: Login page
├── allowed_people.txt           # NEW: Email whitelist
├── generate_dashboard.py        # UNCHANGED: Dashboard generator
├── index.html                   # UNCHANGED: Dashboard (auto-generated)
├── active_indexers.json         # UNCHANGED: Dashboard data
├── .env                         # UPDATED: Add auth config
└── logs/
    └── auth_gateway.log         # NEW: Auth logs
```

## 🔄 Maintaining Your System

### Regular Maintenance Tasks

#### Weekly:
- Review authentication logs for suspicious activity
- Check email delivery success rate

#### Monthly:
- Review and update `allowed_people.txt`
- Rotate logs if needed
- Verify SSL certificate expiry

#### As Needed:
- Add/remove authorized users
- Update whitelist domains
- Restart service after configuration changes

### Updating Whitelist

```bash
# Edit whitelist
nano /home/graph/ftpbox/reo/allowed_people.txt

# Restart service (whitelist is loaded on each request, so this is optional)
sudo systemctl restart reo_auth.service
```

### Rotating Cookie Secret

If you need to invalidate all sessions:

```bash
# Generate new secret
python3 -c "import os; print(os.urandom(32).hex())"

# Update .env
nano /home/graph/ftpbox/reo/.env

# Restart service
sudo systemctl restart reo_auth.service
```

**⚠️ Note:** This will log out all users immediately.

## 🆘 Support

If you encounter issues not covered in this guide:

1. Check the logs: `sudo journalctl -u reo_auth.service -f`
2. Verify configuration: Review `.env` and `allowed_people.txt`
3. Test SMTP: Manually test email sending
4. Review Nginx config: Ensure proper proxying
5. Contact administrator: [@pdiomede on X](https://x.com/pdiomede)

## 📚 Additional Resources

- [Bottle.py Documentation](https://bottlepy.org/docs/dev/)
- [Let's Encrypt SSL Guide](https://letsencrypt.org/getting-started/)
- [Gmail App Passwords](https://support.google.com/accounts/answer/185833)
- [GIP-0079 Proposal](https://forum.thegraph.com/t/gip-0079-indexer-rewards-eligibility-oracle/6734)

---

**Version:** 1.0.0  
**Last Updated:** November 4, 2025  
**Author:** [@pdiomede](https://x.com/pdiomede)

