# 🔐 GRUMP Dashboard - Authentication System

Complete authentication system for the GRUMP Dashboard using email-based OTP (One-Time Password) authentication.

## 📦 What's Included

This package contains everything you need to add secure authentication to your GRUMP Dashboard:

### Core Files (Required)
- **`auth_gate.py`** - Authentication gateway server (Bottle.py)
- **`login.html`** - Beautiful login page UI
- **`allowed_people.txt.example`** - Email whitelist template
- **`auth_gate.service`** - Systemd service file for production

### Configuration Files
- **`env.example`** - Environment variables template
- **`requirements.txt`** - Python dependencies

### Documentation
- **`QUICKSTART_AUTH.md`** - 10-minute setup guide
- **`AUTHENTICATION.md`** - Complete documentation
- **`README.md`** - This file

## 🎯 Features

### Security
- ✅ Email whitelist with wildcard domain support
- ✅ 6-digit OTP codes (expire in 10 minutes)
- ✅ Signed session cookies (7-day expiry)
- ✅ Rate limiting (5 requests/hour per email)
- ✅ HTTPS support with secure cookies
- ✅ Audit logging of all auth events

### User Experience
- 🎨 Beautiful, modern login UI
- 📧 HTML-formatted OTP emails
- 📱 Mobile-friendly design
- ⚡ Fast in-memory storage
- 🔄 Auto-redirect after login

## 📋 Directory Structure

After installation, your files should be organized like this:

```
/var/www/grump-config/          # Config directory
├── auth_gate.py                # Authentication gateway
├── allowed_people.txt          # Email whitelist
└── .env                        # Environment variables (SECRET!)

/var/www/iproot/grump/          # Web root (existing dashboard)
├── login.html                  # Login page (NEW)
├── index.html                  # Your dashboard (existing)
├── generate_dashboard.py       # Your script (existing)
└── logs/
    └── auth_gateway.log        # Auth logs (NEW)
```

## 🚀 Quick Start

### Option 1: Fast Setup (10 minutes)

Follow the [QUICKSTART_AUTH.md](QUICKSTART_AUTH.md) guide for a streamlined setup process.

### Option 2: Step-by-Step

#### 1. Create Directories

```bash
sudo mkdir -p /var/www/grump-config
sudo mkdir -p /var/www/iproot/grump/logs
sudo chown -R www-data:www-data /var/www/grump-config
sudo chown -R www-data:www-data /var/www/iproot/grump/logs
```

#### 2. Install Dependencies

```bash
pip3 install bottle python-dotenv
```

#### 3. Copy Files

```bash
# Copy to config directory
sudo cp auth_gate.py /var/www/grump-config/
sudo cp allowed_people.txt.example /var/www/grump-config/allowed_people.txt

# Copy to web root
sudo cp login.html /var/www/iproot/grump/

# Set permissions
sudo chmod 644 /var/www/grump-config/auth_gate.py
sudo chmod 644 /var/www/grump-config/allowed_people.txt
sudo chmod 644 /var/www/iproot/grump/login.html
```

#### 4. Configure Environment

```bash
# Copy environment template
sudo cp env.example /var/www/grump-config/.env

# Generate cookie secret
python3 -c "import os; print(os.urandom(32).hex())"

# Edit .env with your settings
sudo nano /var/www/grump-config/.env
```

Edit `.env` with your SMTP credentials:
```bash
AUTH_COOKIE_SECRET=<paste-generated-secret>
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM=your-email@gmail.com
DASHBOARD_URL=https://dashboards.thegraph.foundation/grump/
```

**Set secure permissions:**
```bash
sudo chmod 600 /var/www/grump-config/.env
sudo chown www-data:www-data /var/www/grump-config/.env
```

#### 5. Configure Whitelist

```bash
sudo nano /var/www/grump-config/allowed_people.txt
```

Add authorized emails:
```
# Individual emails
yaniv@edgeandnode.com
admin@example.com

# Wildcard domains
*@thegraph.foundation
*@edgeandnode.com
```

#### 6. Install Systemd Service

```bash
sudo cp auth_gate.service /etc/systemd/system/grump_auth.service
sudo systemctl daemon-reload
sudo systemctl enable grump_auth.service
sudo systemctl start grump_auth.service
sudo systemctl status grump_auth.service
```

#### 7. Configure Nginx

Add this location block to your Nginx config:

```nginx
location /grump/ {
    proxy_pass http://127.0.0.1:8081/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_cookie_path / /grump/;
}
```

Reload Nginx:
```bash
sudo nginx -t
sudo systemctl reload nginx
```

## 📧 Gmail Setup (Recommended)

To use Gmail as your SMTP provider:

1. **Enable 2-Factor Authentication** on your Google account
2. Go to **[Google App Passwords](https://myaccount.google.com/apppasswords)**
3. Create an App Password for "Mail"
4. Use the 16-character password as `SMTP_PASSWORD` in `.env`

**Note:** You must use an App Password, not your regular Gmail password!

## 🔧 File Modifications Needed

### Key Paths in `auth_gate.py`

All paths have been pre-configured for your GRUMP project:

```python
# Whitelist path (line 60)
whitelist_file = Path('/var/www/grump-config/allowed_people.txt')

# Web root paths (lines 273, 276, 281, 286)
root='/var/www/iproot/grump'

# Check paths (lines 415, 421)
Path('/var/www/iproot/grump/index.html')
Path('/var/www/iproot/grump/login.html')
```

### Port Configuration

The auth gateway runs on **port 8081** by default. You can change this in `auth_gate.py` (line 434):

```python
app.run(host='0.0.0.0', port=8081, debug=False, reloader=False)
```

## 🧪 Testing

### Local Testing (Before Production)

```bash
cd /var/www/grump-config
python3 auth_gate.py
```

Visit `http://localhost:8081` and test the login flow.

Press `Ctrl+C` to stop.

### Production Testing

After deploying to production:

1. Visit your dashboard URL: `https://dashboards.thegraph.foundation/grump/`
2. You should see the login page
3. Enter an authorized email
4. Check your email for the OTP code
5. Enter the code to login
6. You should be redirected to the dashboard

## 📊 Monitoring

### View Real-Time Logs

```bash
# Service logs
sudo journalctl -u grump_auth.service -f

# Log file
tail -f /var/www/iproot/grump/logs/auth_gateway.log
```

### Check Service Status

```bash
sudo systemctl status grump_auth.service
```

### Restart Service

```bash
sudo systemctl restart grump_auth.service
```

## 🔍 Log Output Examples

Successful login:
```
✅ [2025-11-05 10:30:45 UTC] OTP_SENT: user@example.com - Code: 123456
✅ [2025-11-05 10:32:18 UTC] LOGIN_SUCCESS: user@example.com - Session created
```

Failed attempts:
```
❌ [2025-11-05 10:45:23 UTC] OTP_REQUEST: hacker@bad.com - Email not whitelisted
❌ [2025-11-05 11:22:09 UTC] OTP_VERIFY: user@example.com - Invalid code
```

## 🔐 Security Checklist

Before going to production, ensure:

- [ ] Strong `AUTH_COOKIE_SECRET` generated (32+ random bytes)
- [ ] `.env` file has 600 permissions (read/write owner only)
- [ ] `.env` file owned by `www-data:www-data`
- [ ] HTTPS enabled (SSL/TLS certificate installed)
- [ ] Gmail App Password used (not regular password)
- [ ] Whitelist reviewed and up to date
- [ ] Port 8081 firewalled (only accessible from localhost)
- [ ] Nginx proxy configured correctly
- [ ] Cookies work correctly (test login flow)
- [ ] Logs being written to `/var/www/iproot/grump/logs/`

## 🛠️ Management Commands

### Update Whitelist

```bash
sudo nano /var/www/grump-config/allowed_people.txt
# Changes take effect immediately (no restart needed)
```

### Rotate Cookie Secret (logs out all users)

```bash
# Generate new secret
python3 -c "import os; print(os.urandom(32).hex())"

# Update .env
sudo nano /var/www/grump-config/.env

# Restart service
sudo systemctl restart grump_auth.service
```

### Update Auth Code

```bash
# Edit auth_gate.py
sudo nano /var/www/grump-config/auth_gate.py

# Restart service
sudo systemctl restart grump_auth.service
```

## 🐛 Common Issues & Solutions

### Issue: Email not sending

**Solutions:**
- Verify SMTP credentials in `.env`
- For Gmail: use App Password, not regular password
- Check firewall allows SMTP port (587)
- Test SMTP connection: `python3 -c "import smtplib; smtplib.SMTP('smtp.gmail.com', 587).starttls()"`

### Issue: "Email not authorized"

**Solutions:**
- Add email to `/var/www/grump-config/allowed_people.txt`
- Check for typos in email address
- Verify whitelist file format (one email per line)

### Issue: Cookie not working

**Solutions:**
- Ensure HTTPS is enabled in production
- Check Nginx proxy preserves cookies (`proxy_cookie_path / /grump/;`)
- Verify `AUTH_COOKIE_SECRET` is set in `.env`
- Clear browser cookies and try again

### Issue: Permission errors

**Solutions:**
```bash
sudo chown -R www-data:www-data /var/www/grump-config
sudo chown -R www-data:www-data /var/www/iproot/grump/logs
sudo chmod 600 /var/www/grump-config/.env
```

### Issue: Port already in use

**Solutions:**
```bash
# Check what's using port 8081
sudo lsof -i :8081

# Kill the process
sudo kill -9 <PID>

# Or change port in auth_gate.py
```

## 📚 Documentation

- **[QUICKSTART_AUTH.md](QUICKSTART_AUTH.md)** - Quick 10-minute setup
- **[AUTHENTICATION.md](AUTHENTICATION.md)** - Complete documentation with:
  - Detailed architecture explanation
  - Security features breakdown
  - Alternative SMTP providers
  - Advanced configuration
  - Troubleshooting guide
  - Maintenance procedures

## 🔄 Alternative SMTP Providers

Don't want to use Gmail? See [AUTHENTICATION.md](AUTHENTICATION.md) for setup instructions for:

- **SendGrid** - Popular email API service
- **AWS SES** - Amazon Simple Email Service
- **Mailgun** - Email API for developers
- **Any SMTP server** - Custom SMTP configuration

## 📝 Dependencies

```txt
bottle>=0.12.25
python-dotenv>=1.0.0
```

Python 3.7+ required.

## 🔗 Related Files in Your Project

This authentication system integrates with your existing GRUMP dashboard:

- Your existing `index.html` (dashboard) - **No changes needed**
- Your existing `generate_dashboard.py` - **No changes needed**
- Your existing data files - **No changes needed**

The authentication system acts as a gateway and doesn't modify your existing code!

## 🆘 Getting Help

1. **Check logs**: `sudo journalctl -u grump_auth.service -f`
2. **Review documentation**: See [AUTHENTICATION.md](AUTHENTICATION.md)
3. **Test SMTP**: Verify email sending works
4. **Check permissions**: Ensure correct file ownership
5. **Contact support**: [@pdiomede on X](https://x.com/pdiomede)

## 🎉 Success!

Once everything is set up, your GRUMP dashboard will be protected by:
- Email-based authentication
- OTP verification
- Session management
- Rate limiting
- Audit logging

Users will enjoy a seamless, secure login experience while you maintain full control over who can access your dashboard.

---

**Version:** 1.0.0  
**Last Updated:** November 5, 2025  
**Author:** [@pdiomede](https://x.com/pdiomede)  
**License:** MIT

For questions or issues, contact [@pdiomede on X](https://x.com/pdiomede)

