# REO Dashboard - Utility Commands Reference

Quick reference guide for managing the REO Dashboard infrastructure components.

---

## 🔐 Authentication Gateway Commands

### Service Management
```bash
# Check service status
sudo systemctl status auth_gate

# Start service
sudo systemctl start auth_gate

# Stop service
sudo systemctl stop auth_gate

# Restart service
sudo systemctl restart auth_gate

# Enable auto-start on boot
sudo systemctl enable auth_gate

# Disable auto-start on boot
sudo systemctl disable auth_gate

# Check if enabled for boot
sudo systemctl is-enabled auth_gate
```

### Logs and Monitoring
```bash
# View application logs (last 50 lines)
tail -50 /var/www/iproot/reo/logs/auth_gateway.log

# Follow logs in real-time
tail -f /var/www/iproot/reo/logs/auth_gateway.log

# View systemd logs
sudo journalctl -u auth_gate -n 100 --no-pager

# Follow systemd logs in real-time
sudo journalctl -u auth_gate -f

# View logs since specific time
sudo journalctl -u auth_gate --since "1 hour ago"
sudo journalctl -u auth_gate --since "2025-11-04 12:00:00"
```

### Testing and Debugging
```bash
# Test auth_gate manually (as www-data user)
sudo -u www-data python3 /var/www/reo-config/auth_gate.py

# Check if port 8081 is in use
sudo lsof -i :8081
sudo netstat -tulpn | grep :8081

# Kill hanging auth_gate processes
sudo pkill -f "auth_gate.py"

# Test OTP request via curl
curl -X POST https://dashboards.thegraph.foundation/reo/request-otp \
  -H "Content-Type: application/json" \
  -d '{"email":"your-email@example.com"}'

# Test health check endpoint
curl http://localhost:8081/health
```

### User Whitelist Management
```bash
# Edit allowed users (no restart needed!)
sudo nano /var/www/reo-config/allowed_people.txt

# View current whitelist
sudo cat /var/www/reo-config/allowed_people.txt

# Count whitelisted entries
sudo grep -v '^#' /var/www/reo-config/allowed_people.txt | grep -v '^$' | wc -l
```

### Configuration
```bash
# Edit environment variables
sudo nano /var/www/reo-config/.env

# View configuration (without passwords)
sudo grep -v 'PASSWORD' /var/www/reo-config/.env

# Check file permissions
sudo ls -la /var/www/reo-config/
```

---

## 📱 Telegram Bot Commands

### Service Management
```bash
# Check service status
sudo systemctl status telegram_bot

# Start service
sudo systemctl start telegram_bot

# Stop service
sudo systemctl stop telegram_bot

# Restart service
sudo systemctl restart telegram_bot

# Enable auto-start on boot
sudo systemctl enable telegram_bot

# Disable auto-start on boot
sudo systemctl disable telegram_bot

# Check if enabled for boot
sudo systemctl is-enabled telegram_bot
```

### Logs and Monitoring
```bash
# View application logs
tail -50 /var/www/iproot/reo/logs/telegram_bot.log

# Follow logs in real-time
tail -f /var/www/iproot/reo/logs/telegram_bot.log

# View systemd logs
sudo journalctl -u telegram_bot -n 100 --no-pager

# Follow systemd logs in real-time
sudo journalctl -u telegram_bot -f
```

### Testing and Configuration
```bash
# Test bot manually
cd /var/www/iproot/reo
sudo -u www-data python3 telegram_bot.py

# Check bot configuration
cat /var/www/iproot/reo/.env | grep TELEGRAM

# View subscribers
cat /var/www/iproot/reo/subscribers_telegram.json
```

---

## 🌐 Nginx Commands

### Service Management
```bash
# Check status
sudo systemctl status nginx

# Start nginx
sudo systemctl start nginx

# Stop nginx
sudo systemctl stop nginx

# Restart nginx (brief downtime)
sudo systemctl restart nginx

# Reload nginx (no downtime, recommended)
sudo systemctl reload nginx

# Enable auto-start on boot
sudo systemctl enable nginx

# Check if enabled
sudo systemctl is-enabled nginx
```

### Configuration Testing
```bash
# Test configuration syntax
sudo nginx -t

# Test and show full configuration
sudo nginx -T

# Test specific configuration section
sudo nginx -T | grep -A 20 "location.*reo"

# Test and reload if valid
sudo nginx -t && sudo systemctl reload nginx
```

### Logs
```bash
# View access logs
sudo tail -50 /var/log/nginx/access.log
sudo tail -f /var/log/nginx/access.log

# View error logs
sudo tail -50 /var/log/nginx/error.log
sudo tail -f /var/log/nginx/error.log

# View specific domain logs (if configured)
sudo tail -f /var/log/nginx/dashboards.thegraph.foundation_access.log
sudo tail -f /var/log/nginx/dashboards.thegraph.foundation_error.log

# Search for specific URL in logs
sudo grep "/reo/" /var/log/nginx/access.log | tail -20

# Search for errors
sudo grep "error" /var/log/nginx/error.log | tail -20
```

### SSL/TLS Certificate Management
```bash
# Check SSL certificate expiry
sudo certbot certificates

# Renew certificates (dry run)
sudo certbot renew --dry-run

# Renew certificates
sudo certbot renew

# Force renew specific domain
sudo certbot renew --cert-name dashboards.thegraph.foundation --force-renewal
```

---

## 🐍 Python Dashboard Generator

### Manual Execution
```bash
# Run dashboard generator
cd /var/www/iproot/reo
python3 generate_dashboard.py

# Run as www-data user
sudo -u www-data python3 /var/www/iproot/reo/generate_dashboard.py
```

### Check Dependencies
```bash
# List installed Python packages
pip3 list

# Check specific package
pip3 show requests

# Install/update requirements
cd /var/www/iproot/reo
sudo pip3 install -r requirements.txt
```

---

## 📊 System Monitoring

### Service Overview
```bash
# Check all REO-related services
sudo systemctl status auth_gate telegram_bot nginx

# Check which services are enabled
sudo systemctl list-unit-files | grep -E '(auth_gate|telegram_bot|nginx)'

# Check failed services
sudo systemctl --failed
```

### Resource Usage
```bash
# Check memory usage of services
ps aux | grep -E '(auth_gate|telegram_bot|nginx)' | grep -v grep

# Check disk space
df -h

# Check disk usage in web directories
du -sh /var/www/iproot/reo/
du -sh /var/www/reo-config/

# Check log file sizes
du -h /var/www/iproot/reo/logs/
```

### Network and Ports
```bash
# Check listening ports
sudo netstat -tulpn | grep LISTEN

# Check specific ports
sudo netstat -tulpn | grep -E '(80|443|8081)'

# Check established connections
sudo netstat -an | grep ESTABLISHED

# Check firewall status
sudo ufw status verbose
```

---

## 🔄 Restart All Services (Safe Order)

```bash
# 1. Restart authentication gateway
sudo systemctl restart auth_gate
sleep 2

# 2. Restart telegram bot
sudo systemctl restart telegram_bot
sleep 2

# 3. Reload nginx (no downtime)
sudo systemctl reload nginx

# 4. Verify all services are running
sudo systemctl status auth_gate telegram_bot nginx
```

---

## 🚨 Emergency Commands

### Quick Recovery
```bash
# Kill all Python processes (if services are stuck)
sudo pkill -f "auth_gate.py"
sudo pkill -f "telegram_bot.py"

# Restart all services
sudo systemctl restart auth_gate telegram_bot nginx

# Check everything is running
sudo systemctl status auth_gate telegram_bot nginx
```

### Clear Logs (if disk is full)
```bash
# Check log sizes first
du -h /var/www/iproot/reo/logs/
du -h /var/log/nginx/

# Truncate logs (keeps file but clears content)
sudo truncate -s 0 /var/www/iproot/reo/logs/auth_gateway.log
sudo truncate -s 0 /var/www/iproot/reo/logs/telegram_bot.log
sudo truncate -s 0 /var/log/nginx/access.log
sudo truncate -s 0 /var/log/nginx/error.log

# Restart services after log cleanup
sudo systemctl restart auth_gate telegram_bot nginx
```

### Reboot Server (Nuclear Option)
```bash
# Reboot system (all enabled services will auto-start)
sudo reboot

# After reboot, verify services
sudo systemctl status auth_gate telegram_bot nginx
```

---

## 📁 File Permissions Reference

### Authentication Files
```bash
# Check permissions
sudo ls -la /var/www/reo-config/

# Fix ownership (if needed)
sudo chown www-data:www-data /var/www/reo-config/auth_gate.py
sudo chown www-data:www-data /var/www/reo-config/.env
sudo chown www-data:www-data /var/www/reo-config/allowed_people.txt

# Fix permissions (if needed)
sudo chmod 700 /var/www/reo-config/
sudo chmod 600 /var/www/reo-config/.env
sudo chmod 600 /var/www/reo-config/allowed_people.txt
sudo chmod 700 /var/www/reo-config/auth_gate.py
```

### Web Files
```bash
# Check permissions
sudo ls -la /var/www/iproot/reo/

# Fix ownership (if needed)
sudo chown -R www-data:www-data /var/www/iproot/reo/

# Fix permissions (if needed)
sudo chmod 755 /var/www/iproot/reo/
sudo chmod 644 /var/www/iproot/reo/*.html
sudo chmod 644 /var/www/iproot/reo/*.png
sudo chmod 700 /var/www/iproot/reo/*.py
```

### Log Directory
```bash
# Create logs directory (if missing)
sudo mkdir -p /var/www/iproot/reo/logs

# Fix ownership and permissions
sudo chown -R www-data:www-data /var/www/iproot/reo/logs/
sudo chmod 755 /var/www/iproot/reo/logs/
```

---

## 🔍 Troubleshooting Quick Reference

### "Connection Error" on Login Page
```bash
# 1. Check auth_gate service
sudo systemctl status auth_gate

# 2. Check if port 8081 is listening
sudo netstat -tulpn | grep :8081

# 3. Test from server
curl http://localhost:8081/health

# 4. Check nginx proxy configuration
sudo nginx -T | grep -A 20 "location.*reo"

# 5. Check logs
tail -50 /var/www/iproot/reo/logs/auth_gateway.log
```

### "Port Already in Use" Error
```bash
# Find what's using the port
sudo lsof -i :8081

# Kill the process
sudo pkill -f "auth_gate.py"

# Restart service
sudo systemctl restart auth_gate
```

### "Permission Denied" Errors
```bash
# Check file ownership
sudo ls -la /var/www/reo-config/
sudo ls -la /var/www/iproot/reo/

# Fix ownership
sudo chown -R www-data:www-data /var/www/reo-config/
sudo chown -R www-data:www-data /var/www/iproot/reo/
```

### Service Won't Start After Reboot
```bash
# Check if service is enabled
sudo systemctl is-enabled auth_gate
sudo systemctl is-enabled telegram_bot
sudo systemctl is-enabled nginx

# Enable if needed
sudo systemctl enable auth_gate
sudo systemctl enable telegram_bot
sudo systemctl enable nginx
```

---

## 📚 Related Documentation

- **[README.md](README.md)** - Project overview and setup
- **[AUTHENTICATION.md](AUTHENTICATION.md)** - Authentication system details
- **[CHANGELOG.md](CHANGELOG.md)** - Version history and changes
- **[README_TelegramBOT.md](README_TelegramBOT.md)** - Telegram bot documentation

---

## 💡 Tips

1. **Always test nginx config before reloading:** `sudo nginx -t && sudo systemctl reload nginx`
2. **Use reload instead of restart for nginx:** Less downtime
3. **Check logs first when troubleshooting:** Most errors are visible in logs
4. **No restart needed for whitelist changes:** Just edit `allowed_people.txt`
5. **Keep backups of config files:** Before making major changes
6. **Use `sudo systemctl daemon-reload`:** After editing .service files

---

*Last updated: 2025-11-04 (v0.0.14)*

