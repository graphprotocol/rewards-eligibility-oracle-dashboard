# 🔄 GRUMP Authentication Migration Checklist

This checklist helps you migrate the authentication system from the REO project to the GRUMP project.

## 📁 Files Overview

All files have been created in the `grump-auth/` directory with paths updated for your GRUMP project:

### ✅ Core Files (Must Copy)
- [ ] `auth_gate.py` → `/var/www/grump-config/auth_gate.py`
- [ ] `login.html` → `/var/www/iproot/grump/login.html`
- [ ] `allowed_people.txt.example` → `/var/www/grump-config/allowed_people.txt`

### ✅ Configuration Files (Must Create)
- [ ] `env.example` → Use as template for `/var/www/grump-config/.env`
- [ ] `requirements.txt` → Install dependencies

### ✅ Deployment Files (For Production)
- [ ] `auth_gate.service` → `/etc/systemd/system/grump_auth.service`

### ✅ Documentation Files (Reference)
- [ ] `README.md` → Main setup guide
- [ ] `QUICKSTART_AUTH.md` → Quick start guide
- [ ] `AUTHENTICATION.md` → Complete documentation

## 🎯 Path Configuration

All paths have been updated from REO to GRUMP:

### Config Directory
- **REO**: `/var/www/reo-config/`
- **GRUMP**: `/var/www/grump-config/` ✅

### Web Root
- **REO**: `/var/www/iproot/reo/`
- **GRUMP**: `/var/www/iproot/grump/` ✅

### Service Name
- **REO**: `reo_auth.service`
- **GRUMP**: `grump_auth.service` ✅

### Cookie Name
- **REO**: `reo_auth_session`
- **GRUMP**: `grump_auth_session` ✅

### Port
- **REO**: `8080`
- **GRUMP**: `8081` ✅

### Dashboard URL (Example)
- **REO**: `https://dashboards.thegraph.foundation/reo/`
- **GRUMP**: `https://dashboards.thegraph.foundation/grump/` ✅

## 🚀 Step-by-Step Migration

### Step 1: Create Directories

```bash
# Create config directory
sudo mkdir -p /var/www/grump-config

# Create logs directory
sudo mkdir -p /var/www/iproot/grump/logs

# Set permissions
sudo chown -R www-data:www-data /var/www/grump-config
sudo chown -R www-data:www-data /var/www/iproot/grump/logs
```

- [ ] Created `/var/www/grump-config/`
- [ ] Created `/var/www/iproot/grump/logs/`
- [ ] Set correct permissions

### Step 2: Install Dependencies

```bash
cd grump-auth/
pip3 install -r requirements.txt
```

- [ ] Installed `bottle`
- [ ] Installed `python-dotenv`

### Step 3: Copy Core Files

```bash
# From the grump-auth/ directory
sudo cp auth_gate.py /var/www/grump-config/
sudo cp login.html /var/www/iproot/grump/
sudo cp allowed_people.txt.example /var/www/grump-config/allowed_people.txt

# Set permissions
sudo chmod 644 /var/www/grump-config/auth_gate.py
sudo chmod 644 /var/www/grump-config/allowed_people.txt
sudo chmod 644 /var/www/iproot/grump/login.html
```

- [ ] Copied `auth_gate.py`
- [ ] Copied `login.html`
- [ ] Copied and renamed `allowed_people.txt`
- [ ] Set correct file permissions

### Step 4: Configure Environment

```bash
# Generate cookie secret
python3 -c "import os; print(os.urandom(32).hex())"

# Create .env file
sudo nano /var/www/grump-config/.env
```

Add to `.env`:
```bash
AUTH_COOKIE_SECRET=<paste-generated-secret>
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM=your-email@gmail.com
DASHBOARD_URL=https://dashboards.thegraph.foundation/grump/
```

Set secure permissions:
```bash
sudo chmod 600 /var/www/grump-config/.env
sudo chown www-data:www-data /var/www/grump-config/.env
```

- [ ] Generated `AUTH_COOKIE_SECRET`
- [ ] Created `.env` file
- [ ] Configured SMTP settings
- [ ] Set correct URL for `DASHBOARD_URL`
- [ ] Set secure permissions (600)

### Step 5: Configure Whitelist

```bash
sudo nano /var/www/grump-config/allowed_people.txt
```

Add authorized emails (one per line):
```
# Individual emails
admin@example.com

# Wildcard domains
*@thegraph.foundation
*@edgeandnode.com
```

- [ ] Added authorized emails
- [ ] Tested email format
- [ ] Saved file

### Step 6: Test Locally (Optional)

```bash
cd /var/www/grump-config
python3 auth_gate.py
```

Open browser to `http://localhost:8081`

- [ ] Server starts successfully
- [ ] Login page loads
- [ ] Can request OTP code
- [ ] Receives email with code
- [ ] Can verify code and login

Press `Ctrl+C` to stop.

### Step 7: Install Systemd Service

```bash
# Copy service file
sudo cp grump-auth/auth_gate.service /etc/systemd/system/grump_auth.service

# Reload systemd
sudo systemctl daemon-reload

# Enable service (start on boot)
sudo systemctl enable grump_auth.service

# Start service
sudo systemctl start grump_auth.service

# Check status
sudo systemctl status grump_auth.service
```

- [ ] Copied service file
- [ ] Enabled service
- [ ] Started service
- [ ] Service running successfully

### Step 8: Configure Nginx

Edit your Nginx config (e.g., `/etc/nginx/sites-available/dashboards.thegraph.foundation`):

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

Test and reload:
```bash
sudo nginx -t
sudo systemctl reload nginx
```

- [ ] Added location block to Nginx config
- [ ] Nginx config test passed
- [ ] Reloaded Nginx

### Step 9: Test Production

Visit your dashboard URL: `https://dashboards.thegraph.foundation/grump/`

- [ ] Login page displays
- [ ] Can enter email address
- [ ] Receives OTP via email
- [ ] Can verify OTP code
- [ ] Redirects to dashboard after login
- [ ] Dashboard loads correctly
- [ ] Session persists (try refreshing page)

### Step 10: Monitor Logs

```bash
# View real-time logs
sudo journalctl -u grump_auth.service -f

# Or log file
tail -f /var/www/iproot/grump/logs/auth_gateway.log
```

- [ ] Logs are being written
- [ ] No error messages
- [ ] Auth events being logged

## 🔐 Security Checklist

Before going live:

- [ ] Strong `AUTH_COOKIE_SECRET` generated (32+ bytes)
- [ ] `.env` file has 600 permissions
- [ ] `.env` file owned by `www-data:www-data`
- [ ] HTTPS enabled (SSL/TLS certificate)
- [ ] Using Gmail App Password (not regular password)
- [ ] Whitelist reviewed and contains only authorized emails
- [ ] Port 8081 not exposed to internet (firewalled)
- [ ] Nginx proxy configured correctly
- [ ] Cookies working correctly in production
- [ ] Email delivery working
- [ ] Logs directory writable by `www-data`

## 🐛 Troubleshooting

If you encounter issues, check:

1. **Logs**: `sudo journalctl -u grump_auth.service -f`
2. **Permissions**: Ensure all files owned by `www-data`
3. **SMTP**: Test email sending with Gmail App Password
4. **Nginx**: Verify proxy configuration
5. **Firewall**: Ensure port 8081 accessible from localhost
6. **Dashboard**: Ensure `index.html` exists in `/var/www/iproot/grump/`

## 📚 Documentation

After migration, refer to:

- **Quick Setup**: [QUICKSTART_AUTH.md](QUICKSTART_AUTH.md)
- **Full Docs**: [AUTHENTICATION.md](AUTHENTICATION.md)
- **Main Guide**: [README.md](README.md)

## ✅ Migration Complete!

Once all items are checked off, your GRUMP dashboard is now protected with the same authentication system as REO!

---

**Questions?** Contact [@pdiomede on X](https://x.com/pdiomede)

