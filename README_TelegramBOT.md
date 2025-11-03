# Telegram Bot Setup Guide 🤖

Complete guide for setting up the REO Dashboard Telegram notification bot.

## Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Step 1: Create Telegram Bot](#step-1-create-telegram-bot)
- [Step 2: Install Dependencies](#step-2-install-dependencies)
- [Step 3: Configure Environment](#step-3-configure-environment)
- [Step 4: Deploy the Bot](#step-4-deploy-the-bot)
  - [Option A: Systemd Service (Recommended)](#option-a-systemd-service-recommended)
  - [Option B: Screen Session](#option-b-screen-session)
  - [Option C: Nohup](#option-c-nohup)
- [Step 5: Schedule Dashboard Script](#step-5-schedule-dashboard-script)
- [Bot Management](#bot-management)
- [User Commands](#user-commands)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)

---

## Overview

The Telegram bot provides real-time notifications to subscribers about:
- 🔔 Oracle updates
- 📝 Indexer status changes
- ⚠️ Grace period alerts
- ❌ Ineligibility notifications

**Key Features:**
- ✅ Auto-start on VPS boot
- ✅ Auto-restart on crash
- ✅ Self-service subscription (users subscribe themselves)
- ✅ Watch specific indexers (get notifications only for indexers you care about)
- ✅ Comprehensive logging
- ✅ Rate limiting protection

---

## Prerequisites

- VPS with Ubuntu/Debian (or similar Linux distribution)
- Python 3.10+ installed
- Git repository cloned at `/home/graph/ftpbox/reo`
- Telegram account
- `sudo` access for systemd setup

---

## Step 1: Create Telegram Bot

### 1.1 Open Telegram and Find BotFather

1. Open Telegram app (mobile or desktop)
2. Search for `@BotFather` (official Telegram bot for creating bots)
3. Start a chat with BotFather

### 1.2 Create Your Bot

Send this command to BotFather:
```
/newbot
```

### 1.3 Choose Bot Name

BotFather will ask for a **display name**. Choose something descriptive:
```
REO Dashboard Alerts
```
(or any name you prefer)

### 1.4 Choose Bot Username

BotFather will ask for a **username**. Must end with `bot`:
```
reo_dashboard_bot
```
(or `your_name_reo_bot`, etc.)

### 1.5 Save Your Bot Token

BotFather will give you a **BOT TOKEN** that looks like:
```
123456789:ABCdefGHIjklMNOpqrsTUVwxyz-1234567890
```

**⚠️ IMPORTANT:** 
- Keep this token **SECRET**
- Don't share it publicly
- Don't commit it to GitHub
- You'll need it in the next step

### 1.6 Optional: Set Bot Description

Send these commands to BotFather to customize your bot:

```
/setdescription
```
Choose your bot, then send:
```
Get real-time notifications about REO Dashboard indexer status changes and oracle updates.
```

```
/setabouttext
```
Choose your bot, then send:
```
REO Dashboard notification bot for The Graph Protocol's Rewards Eligibility Oracle (GIP-0079).
```

---

## Step 2: Install Dependencies

### 2.1 Navigate to Project Directory

```bash
cd /home/graph/ftpbox/reo
```

### 2.2 Pull Latest Code

```bash
git pull origin main
```

### 2.3 Install Python Telegram Library

```bash
pip3 install python-telegram-bot==20.7
```

Or install all requirements:
```bash
pip3 install -r requirements.txt
```

### 2.4 Verify Installation

```bash
python3 -c "import telegram; print('Telegram library installed:', telegram.__version__)"
```

Should output: `Telegram library installed: 20.7`

---

## Step 3: Configure Environment

### 3.1 Edit .env File

```bash
nano /home/graph/ftpbox/reo/.env
```

### 3.2 Add Telegram Bot Token

Add this line at the end of the file (replace with your actual token from Step 1.5):

```bash
# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
```

### 3.3 Save and Exit

- Press `Ctrl+O` to save
- Press `Enter` to confirm
- Press `Ctrl+X` to exit

### 3.4 Verify Configuration

```bash
grep TELEGRAM_BOT_TOKEN /home/graph/ftpbox/reo/.env
```

Should show your token (with `TELEGRAM_BOT_TOKEN=...`)

---

## Step 4: Deploy the Bot

Choose **ONE** of the following options. **Option A (Systemd)** is highly recommended for production.

---

### Option A: Systemd Service (Recommended)

This method ensures the bot:
- ✅ Starts automatically on VPS boot
- ✅ Runs in the background as a service
- ✅ Auto-restarts if it crashes
- ✅ Managed with standard Linux tools

#### A.1 Copy Service File

```bash
sudo cp /home/graph/ftpbox/reo/telegram_bot_service.service /etc/systemd/system/telegram_bot.service
```

#### A.2 Reload Systemd

```bash
sudo systemctl daemon-reload
```

#### A.3 Enable Service (Auto-Start on Boot)

```bash
sudo systemctl enable telegram_bot.service
```

You should see:
```
Created symlink /etc/systemd/system/multi-user.target.wants/telegram_bot.service → /etc/systemd/system/telegram_bot.service.
```

#### A.4 Start the Service

```bash
sudo systemctl start telegram_bot.service
```

#### A.5 Verify It's Running

```bash
sudo systemctl status telegram_bot.service
```

Expected output:
```
● telegram_bot.service - REO Dashboard Telegram Bot
   Loaded: loaded (/etc/systemd/system/telegram_bot.service; enabled)
   Active: active (running) since Tue 2025-10-22 15:30:00 UTC; 5s ago
 Main PID: 12345 (python3)
   ...
```

Look for: `Active: active (running)` in **green**

#### A.6 View Live Logs

```bash
sudo journalctl -u telegram_bot.service -f
```

You should see:
```
Starting REO Dashboard Telegram Bot...
✅ REO Dashboard Telegram Bot is running!
📱 Users can now subscribe by sending /start
```

Press `Ctrl+C` to stop viewing logs (bot keeps running)

#### A.7 Management Commands

```bash
# Check status
sudo systemctl status telegram_bot.service

# Restart bot
sudo systemctl restart telegram_bot.service

# Stop bot
sudo systemctl stop telegram_bot.service

# View last 50 log lines
sudo journalctl -u telegram_bot.service -n 50

# View logs from last 10 minutes
sudo journalctl -u telegram_bot.service --since "10 minutes ago"

# Follow logs in real-time
sudo journalctl -u telegram_bot.service -f

# Check if enabled for auto-start
sudo systemctl is-enabled telegram_bot.service
```

**✅ Done!** Your bot is now running and will auto-start on reboot.

---

### Option B: Screen Session

Good for manual control and easy log viewing.

#### B.1 Start Screen Session

```bash
cd /home/graph/ftpbox/reo
screen -S telegram_bot
```

#### B.2 Run the Bot

```bash
python3 telegram_bot.py
```

You should see:
```
✅ REO Dashboard Telegram Bot is running!
📱 Users can now subscribe by sending /start
🛑 Press Ctrl+C to stop the bot
```

#### B.3 Detach from Screen

Press: `Ctrl+A` then `D`

The bot keeps running in the background.

#### B.4 Management Commands

```bash
# List screen sessions
screen -ls

# Reattach to view logs
screen -r telegram_bot

# Kill the session (stops bot)
screen -X -S telegram_bot quit

# Check if bot is running
ps aux | grep telegram_bot.py
```

**⚠️ Note:** With screen, the bot will **NOT** auto-start on VPS reboot. You must manually start it again.

---

### Option C: Nohup

Simple background process.

#### C.1 Start Bot with Nohup

```bash
cd /home/graph/ftpbox/reo
nohup python3 telegram_bot.py > logs/telegram_bot_nohup.log 2>&1 &
```

#### C.2 Verify It's Running

```bash
ps aux | grep telegram_bot.py
```

#### C.3 View Logs

```bash
# Bot creates its own logs in logs/ directory
tail -f /home/graph/ftpbox/reo/logs/telegram_bot.log
tail -f /home/graph/ftpbox/reo/logs/telegram_bot_activity.log
```

#### C.4 Management Commands

```bash
# Check if running
ps aux | grep telegram_bot.py

# View logs (bot logs to logs/ directory)
tail -f /home/graph/ftpbox/reo/logs/telegram_bot.log
tail -f /home/graph/ftpbox/reo/logs/telegram_bot_activity.log

# Stop the bot (replace <PID> with actual process ID)
pkill -f telegram_bot.py

# Or kill specific PID
kill <PID>
```

**⚠️ Note:** With nohup, the bot will **NOT** auto-start on VPS reboot and will **NOT** auto-restart on crash.

---

## Step 5: Schedule Dashboard Script

The bot sends notifications when the dashboard script runs. Set up a cron job to run it periodically.

### 5.1 Edit Crontab

```bash
crontab -e
```

### 5.2 Add Cron Job

Choose your preferred frequency:

**Run every hour (at minute 0):**
```bash
0 * * * * cd /home/graph/ftpbox/reo && /usr/bin/python3 generate_dashboard.py >> /home/graph/ftpbox/reo/cron.log 2>&1
```

**Run every 30 minutes:**
```bash
*/30 * * * * cd /home/graph/ftpbox/reo && /usr/bin/python3 generate_dashboard.py >> /home/graph/ftpbox/reo/cron.log 2>&1
```

**Run every 15 minutes:**
```bash
*/15 * * * * cd /home/graph/ftpbox/reo && /usr/bin/python3 generate_dashboard.py >> /home/graph/ftpbox/reo/cron.log 2>&1
```

**Run every 6 hours:**
```bash
0 */6 * * * cd /home/graph/ftpbox/reo && /usr/bin/python3 generate_dashboard.py >> /home/graph/ftpbox/reo/cron.log 2>&1
```

### 5.3 Save and Exit

- If using `nano`: `Ctrl+O`, `Enter`, `Ctrl+X`
- If using `vim`: Press `Esc`, type `:wq`, press `Enter`

### 5.4 Verify Cron Job

```bash
crontab -l
```

Should show your cron job entry.

### 5.5 View Cron Logs

```bash
# View live logs
tail -f /home/graph/ftpbox/reo/cron.log

# View last 50 lines
tail -n 50 /home/graph/ftpbox/reo/cron.log
```

### 5.6 Test Manually

```bash
cd /home/graph/ftpbox/reo
python3 generate_dashboard.py
```

If you're subscribed to the bot, you should receive a notification! 🎉

---

## Bot Management

### Check Bot Status

**If using systemd:**
```bash
sudo systemctl status telegram_bot.service
```

**If using screen:**
```bash
screen -ls
```

**If using nohup or want to check process:**
```bash
ps aux | grep telegram_bot.py
```

### View Logs

**If using systemd:**
```bash
# Live logs
sudo journalctl -u telegram_bot.service -f

# Last 100 lines
sudo journalctl -u telegram_bot.service -n 100

# Logs since specific time
sudo journalctl -u telegram_bot.service --since "2025-10-22 14:00"
```

**If using screen:**
```bash
screen -r telegram_bot  # Reattach to view logs
# Press Ctrl+A then D to detach again
```

**If using nohup or file logs:**
```bash
tail -f /home/graph/ftpbox/reo/logs/telegram_bot.log
tail -f /home/graph/ftpbox/reo/logs/telegram_bot_activity.log
```

### Restart Bot

**If using systemd:**
```bash
sudo systemctl restart telegram_bot.service
```

**If using screen:**
```bash
screen -X -S telegram_bot quit  # Stop
screen -S telegram_bot           # Start new session
python3 telegram_bot.py          # Run bot
# Ctrl+A then D to detach
```

**If using nohup:**
```bash
pkill -f telegram_bot.py  # Stop
cd /home/graph/ftpbox/reo
nohup python3 telegram_bot.py > logs/telegram_bot_nohup.log 2>&1 &  # Start
```

### Stop Bot

**If using systemd:**
```bash
sudo systemctl stop telegram_bot.service
```

**If using screen:**
```bash
screen -X -S telegram_bot quit
```

**If using nohup:**
```bash
pkill -f telegram_bot.py
```

### Check Subscribers

```bash
cat /home/graph/ftpbox/reo/subscribers_telegram.json
```

Or view count:
```bash
cat /home/graph/ftpbox/reo/subscribers_telegram.json | grep '"active": true' | wc -l
```

### Send Announcements

When you add new features, you can notify all existing subscribers using the announcement script:

```bash
cd /home/graph/ftpbox/reo
python3 announce_update.py
```

The script will:
1. Show how many subscribers will receive the message
2. Ask for confirmation
3. Send the announcement to all active subscribers
4. Show success/failure statistics

**Note:** Edit `announce_update.py` to customize the announcement message before sending.

---

## User Commands

Users interact with the bot using these commands:

| Command | Description |
|---------|-------------|
| `/start` | Welcome message with bot introduction |
| `/subscribe` | Subscribe to receive all notifications |
| `/unsubscribe` | Stop receiving notifications |
| `/watch <address>` | Watch a specific indexer (receive notifications only for that indexer) |
| `/unwatch <address>` | Stop watching a specific indexer |
| `/watchlist` | Show all watched indexers |
| `/status` | Check subscription status |
| `/stats` | View bot statistics (total subscribers, notifications sent) |
| `/help` | Show available commands and help |
| `/test` | Send a test notification (for subscribed users) |

### How Users Subscribe

1. Search for your bot on Telegram (use the username from Step 1.4)
2. Send `/start` or `/subscribe`
3. Receive confirmation message
4. Start getting notifications! 🎉

### Watching Specific Indexers (v0.0.13+)

By default, subscribers receive notifications for **all indexers**. However, users can choose to watch specific indexers only:

**Watch a specific indexer:**
```
/watch 0x1234567890abcdef1234567890abcdef12345678
```

**Stop watching an indexer:**
```
/unwatch 0x1234567890abcdef1234567890abcdef12345678
```

**View watched indexers:**
```
/watchlist
```

**Behavior:**
- Empty watch list = receive notifications for all indexers (default)
- Non-empty watch list = receive notifications only for watched indexers
- Users can watch multiple indexers

---

## Testing

### Test 1: Bot is Running

```bash
# Check process
ps aux | grep telegram_bot.py

# Should show python3 telegram_bot.py running
```

### Test 2: Bot Responds on Telegram

1. Search for your bot on Telegram
2. Send `/start`
3. Bot should respond with welcome message

### Test 3: Subscribe

1. Send `/subscribe` to the bot
2. Bot should confirm subscription
3. Check subscribers file:
```bash
cat /home/graph/ftpbox/reo/subscribers.json
```
Your chat ID should be listed.

### Test 4: Test Notification

Send `/test` to the bot. You should receive a test message.

### Test 5: Manual Dashboard Run

```bash
cd /home/graph/ftpbox/reo
python3 generate_dashboard.py
```

Check the output for:
```
Sending Telegram notifications...
✅ Telegram notifications sent: 1 successful, 0 failed
```

You should receive a notification on Telegram! 🎉

### Test 6: Auto-Restart (Systemd Only)

```bash
# Get bot process ID
ps aux | grep telegram_bot.py

# Kill the process (simulate crash)
sudo kill -9 <PID>

# Wait 10 seconds
sleep 10

# Check if auto-restarted
sudo systemctl status telegram_bot.service
```

Should show `active (running)` again.

### Test 7: Auto-Start on Reboot (Systemd Only)

```bash
# Reboot VPS
sudo reboot

# After reboot, SSH back in and check
sudo systemctl status telegram_bot.service
```

Bot should be running automatically!

---

## Troubleshooting

### Bot Not Starting

**Check if bot token is set:**
```bash
grep TELEGRAM_BOT_TOKEN /home/graph/ftpbox/reo/.env
```

**Check Python version:**
```bash
python3 --version  # Should be 3.10+
```

**Check if telegram library is installed:**
```bash
python3 -c "import telegram; print('OK')"
```

**View error logs (systemd):**
```bash
sudo journalctl -u telegram_bot.service -n 50
```

**Run bot manually to see errors:**
```bash
cd /home/graph/ftpbox/reo
python3 telegram_bot.py
```

### Bot Not Responding

**Check if bot is running:**
```bash
ps aux | grep telegram_bot.py
```

**Check bot token validity:**
- Go to @BotFather on Telegram
- Send `/mybots`
- Select your bot
- Check token is still valid

**Restart the bot:**
```bash
sudo systemctl restart telegram_bot.service
```

### Notifications Not Sending

**Check if dashboard script runs successfully:**
```bash
cd /home/graph/ftpbox/reo
python3 generate_dashboard.py
```

Look for errors or:
```
⚠ Telegram notifications skipped: TELEGRAM_BOT_TOKEN not set
```

**Check cron is running:**
```bash
crontab -l
```

**View cron logs:**
```bash
tail -f /home/graph/ftpbox/reo/cron.log
```

**Verify bot is subscribed:**
```bash
cat /home/graph/ftpbox/reo/subscribers.json
```

**Check bot logs for errors:**
```bash
sudo journalctl -u telegram_bot.service -n 100
```

### Permission Errors

**If service file copy fails:**
```bash
sudo cp /home/graph/ftpbox/reo/telegram_bot_service.service /etc/systemd/system/telegram_bot.service
```

**If systemctl commands fail, ensure you use sudo:**
```bash
sudo systemctl status telegram_bot.service
```

### Rate Limiting Errors

If you have many subscribers (50+), Telegram may rate limit:
- The notifier automatically adds small delays
- For 100+ subscribers, messages are paced
- Check logs for rate limit errors:
```bash
sudo journalctl -u telegram_bot.service | grep -i "rate"
```

### After Code Updates

**If you pull new code from GitHub:**
```bash
cd /home/graph/ftpbox/reo
git pull origin main

# Restart bot
sudo systemctl restart telegram_bot.service

# View logs to ensure restart was successful
sudo journalctl -u telegram_bot.service -f
```

---

## Advanced Configuration

### Change Bot Deployment Method

**From screen to systemd:**
```bash
# Stop screen session
screen -X -S telegram_bot quit

# Set up systemd (follow Option A above)
sudo cp /home/graph/ftpbox/reo/telegram_bot_service.service /etc/systemd/system/telegram_bot.service
sudo systemctl daemon-reload
sudo systemctl enable telegram_bot.service
sudo systemctl start telegram_bot.service
```

### Update Service File

If you need to modify the service configuration:

```bash
# Edit service file
nano /home/graph/ftpbox/reo/telegram_bot_service.service

# Copy to systemd
sudo cp /home/graph/ftpbox/reo/telegram_bot_service.service /etc/systemd/system/telegram_bot.service

# Reload and restart
sudo systemctl daemon-reload
sudo systemctl restart telegram_bot.service
```

### Monitor Bot Performance

```bash
# Check memory usage
ps aux | grep telegram_bot.py | grep -v grep

# Check service uptime
sudo systemctl status telegram_bot.service | grep Active

# Count subscribers
cat /home/graph/ftpbox/reo/subscribers.json | grep '"active": true' | wc -l

# Check notification stats
cat /home/graph/ftpbox/reo/subscribers.json | grep total_notifications_sent
```

---

## Summary

✅ **Bot Created** - Via @BotFather  
✅ **Dependencies Installed** - `python-telegram-bot==20.7`  
✅ **Configuration Set** - `TELEGRAM_BOT_TOKEN` in `.env`  
✅ **Bot Deployed** - Systemd service running  
✅ **Auto-Start Enabled** - Boots with VPS  
✅ **Cron Job Set** - Dashboard runs periodically  
✅ **Tested** - Notifications working  

**Your bot is now fully operational!** 🎉

Users can subscribe by searching for your bot on Telegram and sending `/start`.

For questions or issues, check the [main README.md](README.md) or the troubleshooting section above.

