# 🚀 GRUMP Authentication Setup - 6 Essential Steps

This is the minimal setup guide. For detailed documentation, see [QUICKSTART_AUTH.md](QUICKSTART_AUTH.md) or [AUTHENTICATION.md](AUTHENTICATION.md).

---

## Step 1: Create Directories

```bash
# Create config directory
sudo mkdir -p /var/www/grump-config

# Create logs directory
sudo mkdir -p /var/www/iproot/grump/logs

# Set ownership
sudo chown -R www-data:www-data /var/www/grump-config
sudo chown -R www-data:www-data /var/www/iproot/grump/logs
```

---

## Step 2: Copy Files from grump-auth/

```bash
# Navigate to the grump-auth directory
cd /path/to/grump-auth/

# Copy authentication gateway to config directory
sudo cp auth_gate.py /var/www/grump-config/

# Copy login page to web root
sudo cp login.html /var/www/iproot/grump/

# Copy and rename whitelist template
sudo cp allowed_people.txt.example /var/www/grump-config/allowed_people.txt

# Set permissions
sudo chmod 644 /var/www/grump-config/auth_gate.py
sudo chmod 644 /var/www/grump-config/allowed_people.txt
sudo chmod 644 /var/www/iproot/grump/login.html
```

**Also install Python dependencies:**
```bash
pip3 install bottle python-dotenv
```

---

## Step 3: Create .env with Your SMTP Settings

```bash
# Generate a secure cookie secret first
python3 -c "import os; print(os.urandom(32).hex())"
# Copy the output - you'll paste it below

# Create .env file
sudo nano /var/www/grump-config/.env
```

**Add this content to `.env` file:**
```bash
# Paste the generated secret here
AUTH_COOKIE_SECRET=<paste-your-generated-secret>

# Gmail SMTP settings (use App Password!)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-16-character-app-password
SMTP_FROM=your-email@gmail.com

# Your dashboard URL
DASHBOARD_URL=https://dashboards.thegraph.foundation/grump/
```

**Get Gmail App Password:**
1. Enable 2FA on your Google account
2. Visit: https://myaccount.google.com/apppasswords
3. Create password for "Mail"
4. Use that 16-character password as `SMTP_PASSWORD`

**Set secure permissions:**
```bash
sudo chmod 600 /var/www/grump-config/.env
sudo chown www-data:www-data /var/www/grump-config/.env
```

---

## Step 4: Configure Your Email Whitelist

```bash
sudo nano /var/www/grump-config/allowed_people.txt
```

**Add authorized emails (one per line):**
```
# Individual emails
yaniv@edgeandnode.com
admin@example.com

# Wildcard domains (all emails from these domains)
*@thegraph.foundation
*@edgeandnode.com
```

Save and close the file.

---

## Step 5: Install Systemd Service

```bash
# Copy service file
sudo cp auth_gate.service /etc/systemd/system/grump_auth.service

# Reload systemd daemon
sudo systemctl daemon-reload

# Enable service (auto-start on boot)
sudo systemctl enable grump_auth.service

# Start the service
sudo systemctl start grump_auth.service

# Check status (should show "active (running)")
sudo systemctl status grump_auth.service
```

**View logs if needed:**
```bash
sudo journalctl -u grump_auth.service -f
```

---

## Step 6: Update Nginx Config for /grump/ Location

### Your Current Configuration

Your Nginx config at `/etc/nginx/sites-available/dashboards.thegraph.foundation` (or similar) currently has GRUMP using **basic auth** (lines 37-43):

```nginx
# GRUMP (protected)
location = /grump { return 301 /grump/; }
location ^~ /grump/ {
    auth_basic "Grump";
    auth_basic_user_file /etc/nginx/.htpasswd-grump;
    try_files $uri $uri/ /grump/index.html;
}
```

### What You Need to Change

**REPLACE** the above GRUMP section with the new authentication gateway configuration:

```bash
# Edit your Nginx config
sudo nano /etc/nginx/sites-available/dashboards.thegraph.foundation
```

**Find lines 37-43** and replace them with:

```nginx
# ============================================
# GRUMP DASHBOARD AUTHENTICATION
# ============================================

# Deny access to sensitive files in /grump/
location ~ ^/grump/(\.env|.*\.py|allowed_people\.txt|.*\.json|.*\.json\.example|requirements\.txt)$ {
    deny all;
    return 404;
}

# Redirect /grump to /grump/
location = /grump { return 301 /grump/; }

# Proxy GRUMP to auth gateway (running on localhost:8081)
location ^~ /grump/ {
    proxy_pass http://127.0.0.1:8081/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    
    # Important: preserve cookies for authentication
    proxy_cookie_path / /grump/;
    
    # WebSocket support (if needed)
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upstream_upgrade;
    proxy_set_header Connection "upgrade";
}
# ============================================
```

### Complete Modified Section

Your GRUMP section should now look like your REO section (lines 47-75 in your current config). Here's how it should look after modification:

**Before (lines 37-43):**
```nginx
# GRUMP (protected)
location = /grump { return 301 /grump/; }
location ^~ /grump/ {
    auth_basic "Grump";                                    ← OLD: basic auth
    auth_basic_user_file /etc/nginx/.htpasswd-grump;      ← OLD: password file
    try_files $uri $uri/ /grump/index.html;               ← OLD: static files
}
```

**After (new configuration):**
```nginx
# ============================================
# GRUMP DASHBOARD AUTHENTICATION
# ============================================

# Deny access to sensitive files in /grump/
location ~ ^/grump/(\.env|.*\.py|allowed_people\.txt|.*\.json|.*\.json\.example|requirements\.txt)$ {
    deny all;
    return 404;
}

# Redirect /grump to /grump/
location = /grump { return 301 /grump/; }

# Proxy GRUMP to auth gateway (running on localhost:8081)
location ^~ /grump/ {
    proxy_pass http://127.0.0.1:8081/;                    ← NEW: proxy to auth gateway
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    
    # Important: preserve cookies for authentication
    proxy_cookie_path / /grump/;                          ← NEW: cookie handling
    
    # WebSocket support (if needed)
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upstream_upgrade;
    proxy_set_header Connection "upgrade";
}
# ============================================
```

### Important Notes

1. **Port 8081** - GRUMP auth gateway runs on port 8081 (REO uses 8080)
2. **Remove basic auth** - The `auth_basic` lines are no longer needed
3. **Cookie path** - Must be `/grump/` not `/reo/`
4. **Sensitive files** - The first location block prevents access to `.env`, `.py` files, etc.

### Optional: Remove Old .htpasswd File

After confirming the new auth works, you can remove the old password file:

```bash
sudo rm /etc/nginx/.htpasswd-grump
```

### Test and Reload Nginx

```bash
# Test config (should say "test is successful")
sudo nginx -t

# If test passes, reload Nginx
sudo systemctl reload nginx
```

### Verify the Change

After reloading Nginx:
1. Visit: `https://dashboards.thegraph.foundation/grump/`
2. You should see the **new login page** (not the browser's basic auth prompt)
3. Enter an authorized email and test the OTP flow

---

## ✅ Done! Test Your Setup

Visit your dashboard: `https://dashboards.thegraph.foundation/grump/`

You should see:
1. 🔐 Login page appears
2. Enter your authorized email
3. 📧 Receive OTP code via email
4. Enter the code
5. ✅ Redirected to your dashboard

---

## 🔍 Quick Commands Reference

```bash
# View logs
sudo journalctl -u grump_auth.service -f

# Restart service
sudo systemctl restart grump_auth.service

# Check service status
sudo systemctl status grump_auth.service

# Edit whitelist (changes apply immediately)
sudo nano /var/www/grump-config/allowed_people.txt

# Update auth code
sudo nano /var/www/grump-config/auth_gate.py
sudo systemctl restart grump_auth.service
```

---

## 🐛 Quick Troubleshooting

**Email not sending?**
- Check `.env` has correct SMTP credentials
- For Gmail: must use App Password, not regular password
- Test: `python3 -c "import smtplib; smtplib.SMTP('smtp.gmail.com', 587).starttls()"`

**"Email not authorized"?**
- Add email to `/var/www/grump-config/allowed_people.txt`

**Permission errors?**
```bash
sudo chown -R www-data:www-data /var/www/grump-config
sudo chown -R www-data:www-data /var/www/iproot/grump/logs
sudo chmod 600 /var/www/grump-config/.env
```

**Service won't start?**
```bash
# Check if port 8081 is in use
sudo lsof -i :8081

# View detailed logs
sudo journalctl -u grump_auth.service -n 50
```

---

## 📚 More Documentation

- **This file** - Minimal 6-step setup
- **[QUICKSTART_AUTH.md](QUICKSTART_AUTH.md)** - Quick setup with more context (8 steps)
- **[MIGRATION_CHECKLIST.md](MIGRATION_CHECKLIST.md)** - Detailed checklist with boxes to check (10 steps)
- **[AUTHENTICATION.md](AUTHENTICATION.md)** - Complete documentation (architecture, security, troubleshooting)
- **[README.md](README.md)** - Project overview and guide

---

**Questions?** Contact [@pdiomede on X](https://x.com/pdiomede)

