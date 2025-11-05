# 📝 Nginx Configuration Modification Guide

This guide shows exactly how to modify your Nginx configuration to replace basic auth with OTP authentication for GRUMP.

---

## 📍 File Location

Your Nginx configuration file:
```
/etc/nginx/sites-available/dashboards.thegraph.foundation
```

Or possibly:
```
/etc/nginx/conf.d/dashboards.thegraph.foundation.conf
```

---

## 🔍 What to Change

### Current Configuration (Lines 37-43)

Your GRUMP section **currently looks like this:**

```nginx
# GRUMP (protected)
location = /grump { return 301 /grump/; }
location ^~ /grump/ {
    auth_basic "Grump";
    auth_basic_user_file /etc/nginx/.htpasswd-grump;
    try_files $uri $uri/ /grump/index.html;
}
```

This uses **basic authentication** (username/password prompt in browser).

---

## 🎯 New Configuration

**Replace the above** with this complete block:

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

This uses **OTP authentication** (email-based with 6-digit code).

---

## 📋 Step-by-Step Instructions

### 1. Backup Current Configuration

```bash
sudo cp /etc/nginx/sites-available/dashboards.thegraph.foundation \
       /etc/nginx/sites-available/dashboards.thegraph.foundation.backup
```

### 2. Edit the Configuration

```bash
sudo nano /etc/nginx/sites-available/dashboards.thegraph.foundation
```

### 3. Find the GRUMP Section

Look for lines 37-43:
```nginx
# GRUMP (protected)
location = /grump { return 301 /grump/; }
location ^~ /grump/ {
    auth_basic "Grump";
    auth_basic_user_file /etc/nginx/.htpasswd-grump;
    try_files $uri $uri/ /grump/index.html;
}
```

### 4. Delete Old Lines

**Delete** all 7 lines (from `# GRUMP (protected)` to the closing `}`).

### 5. Paste New Configuration

**Paste** the new configuration block (see "New Configuration" section above).

### 6. Save the File

- In nano: `Ctrl+O` (save), `Enter`, `Ctrl+X` (exit)
- In vim: `:wq`

### 7. Test Configuration

```bash
sudo nginx -t
```

Expected output:
```
nginx: the configuration file /etc/nginx/nginx.conf syntax is ok
nginx: configuration file /etc/nginx/nginx.conf test is successful
```

### 8. Reload Nginx

```bash
sudo systemctl reload nginx
```

### 9. Verify the Change

Visit: `https://dashboards.thegraph.foundation/grump/`

You should now see:
- ✅ **Beautiful login page** (not a browser password prompt)
- ✅ **Email entry field**
- ✅ **OTP code verification**

---

## 🔑 Key Differences

| Feature | Old (Basic Auth) | New (OTP Auth) |
|---------|------------------|----------------|
| **Authentication** | Browser password prompt | Email + OTP code |
| **User Experience** | Browser-controlled | Custom login page |
| **Session** | Per-browser session | 7-day cookie |
| **Configuration** | `.htpasswd` file | Email whitelist |
| **Port** | Static files | Proxy to 8081 |
| **Security** | Password-based | Email + time-limited OTP |

---

## 📊 What Each Part Does

### 1. Deny Sensitive Files
```nginx
location ~ ^/grump/(\.env|.*\.py|allowed_people\.txt|.*\.json|.*\.json\.example|requirements\.txt)$ {
    deny all;
    return 404;
}
```
**Purpose:** Prevents direct access to configuration files, scripts, and data files.

### 2. Redirect Without Trailing Slash
```nginx
location = /grump { return 301 /grump/; }
```
**Purpose:** Ensures `/grump` redirects to `/grump/` for consistency.

### 3. Proxy to Auth Gateway
```nginx
location ^~ /grump/ {
    proxy_pass http://127.0.0.1:8081/;
    ...
}
```
**Purpose:** Forwards all `/grump/` requests to the authentication gateway running on port 8081.

### 4. Cookie Handling
```nginx
proxy_cookie_path / /grump/;
```
**Purpose:** Ensures authentication cookies work correctly with the `/grump/` path.

### 5. WebSocket Support
```nginx
proxy_http_version 1.1;
proxy_set_header Upgrade $http_upstream_upgrade;
proxy_set_header Connection "upgrade";
```
**Purpose:** Allows WebSocket connections if needed (future-proofing).

---

## 🗑️ Optional: Clean Up Old Files

After confirming the new authentication works:

```bash
# Remove old password file (no longer needed)
sudo rm /etc/nginx/.htpasswd-grump

# List to verify it's gone
ls -la /etc/nginx/.htpasswd-*
```

---

## 🆚 Side-by-Side Comparison

### BEFORE: Basic Auth (Old)
```nginx
# GRUMP (protected)
location = /grump { return 301 /grump/; }
location ^~ /grump/ {
    auth_basic "Grump";                         ← Browser prompt
    auth_basic_user_file /etc/nginx/.htpasswd-grump;  ← Password file
    try_files $uri $uri/ /grump/index.html;    ← Serve static files
}
```

### AFTER: OTP Auth (New)
```nginx
# ============================================
# GRUMP DASHBOARD AUTHENTICATION
# ============================================

# Deny access to sensitive files
location ~ ^/grump/(\.env|.*\.py|allowed_people\.txt|...)$ {
    deny all;
    return 404;
}

location = /grump { return 301 /grump/; }

location ^~ /grump/ {
    proxy_pass http://127.0.0.1:8081/;         ← Proxy to auth gateway
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    
    proxy_cookie_path / /grump/;               ← Handle cookies
    
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upstream_upgrade;
    proxy_set_header Connection "upgrade";
}
# ============================================
```

---

## 🔍 Complete File Reference

A complete, updated version of your Nginx config is available at:
```
./grump-auth/dashboards.thegraph.foundation.conf
```

This file shows your **entire configuration** with the GRUMP section already updated.

---

## 🐛 Troubleshooting

### "Nginx test failed"

**Check syntax:**
```bash
sudo nginx -t
```

Common issues:
- Missing semicolon `;` at end of line
- Mismatched `{` and `}` braces
- Copy-paste formatting issues

**Solution:** Compare with the working REO section (lines 47-75) in your config.

### "502 Bad Gateway"

**Cause:** Auth gateway not running.

**Solution:**
```bash
sudo systemctl status grump_auth.service
sudo systemctl start grump_auth.service
```

### "Connection refused on port 8081"

**Cause:** Auth gateway not listening on port 8081.

**Solutions:**
```bash
# Check if something else is using port 8081
sudo lsof -i :8081

# Check auth gateway logs
sudo journalctl -u grump_auth.service -n 50
```

### Still shows browser password prompt

**Cause:** Browser cached the old auth method.

**Solutions:**
1. Clear browser cache
2. Use incognito/private window
3. Try different browser
4. Hard refresh: `Ctrl+Shift+R` or `Cmd+Shift+R`

### Old basic auth still appears

**Cause:** Wrong Nginx config file being used, or changes not reloaded.

**Solutions:**
```bash
# Check which config files are being used
sudo nginx -T | grep "configuration file"

# Reload Nginx again
sudo systemctl reload nginx

# Or restart Nginx
sudo systemctl restart nginx
```

---

## ✅ Verification Checklist

After making changes:

- [ ] Backed up original config
- [ ] Edited Nginx config file
- [ ] Replaced GRUMP section (lines 37-43)
- [ ] Saved file
- [ ] Tested config: `sudo nginx -t` passed
- [ ] Reloaded Nginx: `sudo systemctl reload nginx`
- [ ] Visited `https://dashboards.thegraph.foundation/grump/`
- [ ] See new login page (not browser prompt)
- [ ] Can request OTP code
- [ ] Receives email with code
- [ ] Can login successfully
- [ ] Dashboard loads after login

---

## 📚 Related Files

- **Nginx snippet**: `nginx-grump-config.snippet` - Just the config block to copy
- **Complete config**: `dashboards.thegraph.foundation.conf` - Full file with changes applied
- **Setup guide**: `SETUP_STEPS.md` - Complete 6-step setup process

---

## 🆘 Need Help?

If you encounter issues:

1. **Check logs**: `sudo journalctl -u grump_auth.service -f`
2. **Verify Nginx syntax**: `sudo nginx -t`
3. **Test auth gateway**: `sudo systemctl status grump_auth.service`
4. **Review complete config**: Compare with `dashboards.thegraph.foundation.conf` in this directory

Contact: [@pdiomede on X](https://x.com/pdiomede)

---

**Last Updated:** November 5, 2025

