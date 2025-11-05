# 🚀 Quick Start: GRUMP Authentication Setup

This is a quick 10-minute guide to get authentication running. For full documentation, see [AUTHENTICATION.md](AUTHENTICATION.md).

## Step 1: Create Directories

```bash
# Create config directory
sudo mkdir -p /var/www/grump-config

# Create logs directory
sudo mkdir -p /var/www/iproot/grump/logs

# Set permissions
sudo chown -R www-data:www-data /var/www/grump-config
sudo chown -R www-data:www-data /var/www/iproot/grump/logs
```

## Step 2: Install Dependencies

```bash
pip3 install bottle python-dotenv
```

## Step 3: Copy Files

```bash
# Copy authentication files to config directory
sudo cp auth_gate.py /var/www/grump-config/
sudo cp allowed_people.txt /var/www/grump-config/

# Copy login page to web root
sudo cp login.html /var/www/iproot/grump/

# Set permissions
sudo chmod 644 /var/www/grump-config/auth_gate.py
sudo chmod 644 /var/www/grump-config/allowed_people.txt
sudo chmod 644 /var/www/iproot/grump/login.html
```

## Step 4: Configure Email

Create `/var/www/grump-config/.env`:

```bash
# Authentication
AUTH_COOKIE_SECRET=$(python3 -c "import os; print(os.urandom(32).hex())")

# Gmail SMTP (use App Password, not regular password)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-16-char-app-password
SMTP_FROM=your-email@gmail.com

DASHBOARD_URL=https://dashboards.thegraph.foundation/grump/
```

Set secure permissions:
```bash
sudo chmod 600 /var/www/grump-config/.env
sudo chown www-data:www-data /var/www/grump-config/.env
```

### Get Gmail App Password:
1. Enable 2FA on Google account
2. Visit: https://myaccount.google.com/apppasswords
3. Create password for "Mail"
4. Use that 16-character password as `SMTP_PASSWORD`

## Step 5: Configure Whitelist

Edit `/var/www/grump-config/allowed_people.txt`:

```bash
# Individual emails
yaniv@edgeandnode.com

# Wildcard domains
*@thegraph.foundation
*@edgeandnode.com
```

## Step 6: Test Locally (Optional)

```bash
cd /var/www/grump-config
python3 auth_gate.py
```

Visit: http://localhost:8081

Press Ctrl+C to stop.

## Step 7: Deploy to Production

### Create systemd service:

```bash
sudo cp auth_gate.service /etc/systemd/system/grump_auth.service
```

Or create manually:

```bash
sudo nano /etc/systemd/system/grump_auth.service
```

```ini
[Unit]
Description=GRUMP Dashboard Authentication Gateway
After=network.target

[Service]
Type=simple
User=www-data
Group=www-data
WorkingDirectory=/var/www/grump-config
Environment="PATH=/usr/bin:/usr/local/bin"
ExecStart=/usr/bin/python3 /var/www/grump-config/auth_gate.py
Restart=always
RestartSec=10
StandardOutput=append:/var/www/iproot/grump/logs/auth_gateway.log
StandardError=append:/var/www/iproot/grump/logs/auth_gateway.log

# Security hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/www/iproot/grump/logs
ReadOnlyPaths=/var/www/grump-config

[Install]
WantedBy=multi-user.target
```

### Start service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable grump_auth.service
sudo systemctl start grump_auth.service
sudo systemctl status grump_auth.service
```

## Step 8: Configure Nginx

Add to your Nginx config:

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

## ✅ Done!

Your dashboard is now protected. Users will:
1. Visit dashboard URL
2. Enter their email (must be in whitelist)
3. Receive 6-digit OTP via email
4. Enter OTP to login
5. Stay logged in for 7 days

## 🔍 Monitoring

View logs:
```bash
# Real-time logs
tail -f /var/www/iproot/grump/logs/auth_gateway.log

# Or systemd logs
sudo journalctl -u grump_auth.service -f
```

## 🐛 Troubleshooting

**Email not sending?**
- Check SMTP credentials in `.env`
- For Gmail: ensure using App Password, not regular password
- Test: `python3 -c "import smtplib; smtplib.SMTP('smtp.gmail.com', 587).starttls()"`

**Email not authorized?**
- Add to `allowed_people.txt`
- Restart service: `sudo systemctl restart grump_auth.service`

**Cookie not working?**
- Ensure using HTTPS in production
- Check Nginx proxy settings preserve cookies

**Permission errors?**
```bash
sudo chown -R www-data:www-data /var/www/grump-config
sudo chown -R www-data:www-data /var/www/iproot/grump/logs
sudo chmod 600 /var/www/grump-config/.env
```

## 📖 Full Documentation

See [AUTHENTICATION.md](AUTHENTICATION.md) for:
- Complete configuration options
- Alternative SMTP providers (SendGrid, AWS SES, Mailgun)
- Security best practices
- Advanced troubleshooting
- Maintenance tasks

---

**Need help?** Contact [@pdiomede on X](https://x.com/pdiomede)

