# 🚀 Quick Start: Authentication Setup

This is a quick 5-minute guide to get authentication running. For full documentation, see [AUTHENTICATION.md](AUTHENTICATION.md).

## Step 1: Install Dependencies

```bash
pip3 install bottle
```

## Step 2: Configure Email

Add to your `.env` file:

```bash
# Authentication
AUTH_COOKIE_SECRET=$(python3 -c "import os; print(os.urandom(32).hex())")

# Gmail SMTP (use App Password, not regular password)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-16-char-app-password
SMTP_FROM=your-email@gmail.com

DASHBOARD_URL=https://dashboards.thegraph.foundation/reo/
```

### Get Gmail App Password:
1. Enable 2FA on Google account
2. Visit: https://myaccount.google.com/apppasswords
3. Create password for "Mail"
4. Use that 16-character password as `SMTP_PASSWORD`

## Step 3: Configure Whitelist

Edit `allowed_people.txt`:

```bash
# Individual emails
yaniv@edgeandnode.com

# Wildcard domains
*@thegraph.foundation
*@edgeandnode.com
```

## Step 4: Test Locally

```bash
python3 auth_gate.py
```

Visit: http://localhost:8080

## Step 5: Deploy to Production

### Create systemd service:

```bash
sudo nano /etc/systemd/system/reo_auth.service
```

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
EnvironmentFile=/home/graph/ftpbox/reo/.env

[Install]
WantedBy=multi-user.target
```

### Start service:

```bash
mkdir -p logs
sudo systemctl daemon-reload
sudo systemctl enable reo_auth.service
sudo systemctl start reo_auth.service
sudo systemctl status reo_auth.service
```

## Step 6: Configure Nginx (Optional)

If using Nginx as reverse proxy:

```nginx
location /reo/ {
    proxy_pass http://127.0.0.1:8080/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_cookie_path / /reo/;
}
```

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
tail -f logs/auth_gateway.log

# Or systemd logs
sudo journalctl -u reo_auth.service -f
```

## 🐛 Troubleshooting

**Email not sending?**
- Check SMTP credentials in `.env`
- For Gmail: ensure using App Password, not regular password
- Test: `python3 -c "import smtplib; smtplib.SMTP('smtp.gmail.com', 587).starttls()"`

**Email not authorized?**
- Add to `allowed_people.txt`
- Restart service (optional, whitelist reloads on each request)

**Cookie not working?**
- Ensure using HTTPS in production
- Check Nginx proxy settings

## 📖 Full Documentation

See [AUTHENTICATION.md](AUTHENTICATION.md) for:
- Complete configuration options
- Alternative SMTP providers (SendGrid, AWS SES, Mailgun)
- Security best practices
- Advanced troubleshooting
- Maintenance tasks

---

**Need help?** Contact [@pdiomede on X](https://x.com/pdiomede)

