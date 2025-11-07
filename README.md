## Rewards Eligibility Oracle (GIP-0079)

This dashboard is built to monitor indexers participating in [The Graph Protocol's Rewards Eligibility Oracle system](https://forum.thegraph.com/t/gip-0079-indexer-rewards-eligibility-oracle/6734).

### What is the Rewards Eligibility Oracle?

The **Rewards Eligibility Oracle** links eligibility for indexing rewards to the provision of quality service to consumers. Only indexers meeting minimum performance standards receive rewards, ensuring incentives align with providing value to the network.

**Key Features:**
- **Off-chain Oracle Nodes**: Assess indexer performance against published criteria
- **On-chain Oracle Contract**: Tracks which indexers are eligible for rewards
- **Service Quality Metrics**: Indexers are evaluated on actual service provision
- **14-Day Eligibility Period**: Qualifying indexers have their eligibility renewed for 14 days
- **Performance-Based**: Ineligible indexers are denied rewards until they improve service quality

This system ensures that rewards are distributed only to indexers who actively serve queries and maintain quality service, rather than simply allocating tokens based on stake alone.

**Learn More:**
- [GIP-0079 Forum Discussion](https://forum.thegraph.com/t/gip-0079-indexer-rewards-eligibility-oracle/6734)
- [Rewards Eligibility Oracle (REO) for The Graph Protocol.](https://github.com/graphprotocol/rewards-eligibility-oracle)

## 🆕 Recent Updates

**Version 0.0.15** (Nov 7, 2025):
- 🌐 **Public Access**: REO dashboard is now publicly accessible without authentication
- ⚡ **Improved Performance**: Direct static file serving for faster load times
- 🔒 **Security**: Sensitive files (.py, .env) remain protected
- 🧭 **Breadcrumb Navigation**: Added navigation bar at top with CSS-styled home icon
- 🔗 **Transaction Links**: Last Renewed dates now link to Arbiscan transaction details
- 📊 **Transaction Hash Tracking**: New `last_renewed_on_tx` field stores renewal transaction hash

**Version 0.0.13** (Nov 3, 2025):
- 🎯 **Watch Specific Indexers**: New `/watch`, `/unwatch`, and `/watchlist` commands let subscribers monitor specific indexers
- 📧 **Personalized Notifications**: Daily summaries filtered based on each user's watched indexers
- 📋 **Detailed Status Changes**: Notifications now show individual indexer addresses with their status transitions
- 📢 **Announcement Tool**: New script to notify existing subscribers about feature updates
- 📝 **Daily Summary Messaging**: Clarified that bot sends daily summary messages, not real-time notifications
- 🔗 **GIP-0079 Reference**: Added direct link to proposal in help message

**Version 0.0.12** (Nov 3, 2025):
- 📅 **Last Renewed Column**: New column showing when each indexer's eligibility was last renewed
- 🎨 **Hover Tooltips**: CSS-based tooltips show full timestamps on date hover for faster loading
- 📏 **Short Date Format**: Dates display as "2-Nov-2025" by default, full timestamp on hover

**Version 0.0.11** (Nov 3, 2025):
- 🔧 **Provider-Agnostic Configuration**: Renamed `QUICK_NODE` to `RPC_ENDPOINT` - now works with any Ethereum RPC provider (Alchemy, Infura, QuickNode, Ankr, etc.)

See [CHANGELOG.md](CHANGELOG.md) for complete version history.

---

## 📚 Documentation

This project includes comprehensive documentation:

- **[README.md](README.md)** - Main documentation (this file)
  - Dashboard features and functionality
  - How the oracle system works
  - Installation and usage instructions
  - File structure and configuration
  
- **[README_TelegramBOT.md](README_TelegramBOT.md)** - Telegram Bot Setup Guide
  - Complete bot deployment instructions
  - VPS setup and configuration
  - Systemd service setup for automatic startup
  - Bot commands and user management
  - Troubleshooting guide
  
- **[LOGGING.md](LOGGING.md)** - Logging System Documentation
  - Overview of all log files
  - How to monitor bot activity
  - Subscriber activity tracking
  - Error log analysis
  - Log rotation and maintenance
  
- **[UTILS_COMMANDS.md](UTILS_COMMANDS.md)** - Utility Commands Reference
  - Telegram bot service commands
  - Nginx configuration and restart commands
  - Log viewing and troubleshooting
  - Emergency recovery procedures
  
- **[activity_log_indexers_status_changes.json](activity_log_indexers_status_changes.json)** - Activity Log File
  - Cumulative history of all indexer status changes
  - Tracks status transitions over time (eligible ↔ grace ↔ ineligible)
  - Automatically updated by `generate_dashboard.py`
  - Used by Telegram notifier to send status change alerts
  - See [Activity Log section](#activity-log-activity_log_indexers_status_changesjson) for detailed structure

## Features

- 📊 **Smart Sorting**: Automatically sorts by eligibility status (eligible → grace → ineligible), then by ENS name
- 🏷️ **Three Status Types**: 
  - **Eligible**: Indexers with current eligibility (green badge)
  - **Grace Period**: Indexers in 14-day grace period with expiration date (yellow badge)
  - **Ineligible**: Indexers who lost eligibility (red badge)
- 🔍 **Real-time Search**: Filter indexers by address or ENS name
- 🔗 **Blockchain Integration**: Fetches live data from Arbitrum Sepolia via RPC endpoint
- ⏰ **Oracle Tracking**: Displays last oracle update time and 14-day eligibility period from contract
- ⏳ **Grace Period Monitoring**: Shows when grace period expires for indexers in transition
- 📱 **Responsive Design**: Mobile-friendly dark theme UI with collapsible sections
- 💾 **Offline Fallback**: Can work with cached transaction data from JSON file
- 🔗 **Transaction Links**: Last Renewed dates link to Arbiscan transaction details for eligible indexers
- 🧭 **Breadcrumb Navigation**: Easy navigation back to home page with styled breadcrumb bar

## Understanding Indexer Status

The dashboard tracks three distinct eligibility states for indexers:

### 🟢 Eligible Status
An indexer is **eligible** when:
- Their `eligibility_renewal_time` **matches** the contract's `last_oracle_update_time`
- This means they met the performance criteria in the most recent oracle update
- They will receive rewards for this period

### 🟡 Grace Period Status
An indexer enters the **grace period** when:
- They were previously eligible (have an `eligibility_renewal_time` from a past oracle update)
- Their `eligibility_renewal_time` **does NOT match** the current `last_oracle_update_time` (they weren't renewed in the latest update)
- Current time is still within: `eligibility_renewal_time + eligibility_period` (typically 14 days)
- **During grace period**: Indexers can still receive rewards and have time to improve their service quality
- **After grace period expires**: They become ineligible

**Example Grace Period Scenario:**
1. Day 0: Indexer meets criteria, gets renewed (`eligibility_renewal_time` = Day 0)
2. Day 7: Oracle runs again, indexer doesn't meet criteria
3. Day 7-21: Indexer is in **grace period** (14 days from Day 0)
4. Day 22: If still not renewed, indexer becomes **ineligible**

### 🔴 Ineligible Status
An indexer is **ineligible** when:
- They have no `eligibility_renewal_time`, OR
- Their grace period has expired (current time > `eligibility_renewal_time + eligibility_period`)
- They will **not** receive rewards until they improve service quality and get renewed by the oracle

## How It Works

### Data Flow

```
┌───────────────────┐
│ Network Subgraph  │ ──┐
│  (Active Indexers)│   │
└───────────────────┘   │
                        │
┌───────────────────┐   │
│  ENS Subgraph     │ ──┤
│  (Name Resolution)│   ├──► retrieveActiveIndexers() 
└───────────────────┘   │         │
     (or cached)        │         ▼
                        │    active_indexers.json
┌───────────────────┐   │         +
│ ens_resolution    │ ──┤    ens_resolution.json (cached ENS)
│     .json         │   │         │
└───────────────────┘   │         ▼
                        │    checkEligibility()
┌───────────────────┐   │         │
│ Contract: Oracle  │ ──┤         ▼
│  (Eligibility)    │   │    renderIndexerTable() (merges ENS data)
└───────────────────┘   │         │
                        │         ▼
┌───────────────────┐   │    HTML Dashboard (only eligible indexers)
│last_transaction   │ ──┘
│     .json         │
└───────────────────┘
```

### Main Components

#### 1. **Active Indexers Retrieval**
- **`retrieveActiveIndexers()`**: Queries The Graph's network subgraph to get indexers with self stake > 0
  - Queries network subgraph (deployment ID: `DZz4kDTdmzWLWsV373w2bSmoar3umKKH9y82SUKr5qmp`)
  - Fetches contract metadata:
    - Calls `getLastOracleUpdateTime()` (function selector: `0xbe626dd2`)
    - Calls `getEligibilityPeriod()` (function selector: `0xd0a5379e`)
    - Stores both values in metadata section of JSON
  - ENS resolution strategy (controlled by `USE_CACHED_ENS` environment variable):
    - **If `USE_CACHED_ENS=Y`**: Loads ENS names from `ens_resolution.json` cache file
    - **If `USE_CACHED_ENS=N`**: Queries ENS subgraph (deployment ID: `5XqPmWe6gjyrJtFn9cLy237i4cWw2j9HcUJEXsP5qGtH`) and updates cache
  - Writes results to `active_indexers.json` with fields: `address`, `is_eligible`, `status`, `eligible_until`, `eligible_until_readable`, `eligibility_renewal_time` (ENS stored separately)
  - ENS data saved to `ens_resolution.json` for caching

#### 2. **Eligibility Check (Three-Pass Approach)**
- **`checkEligibility()`**: Checks eligibility status for all active indexers
  - **Pass 1**: Calls `isEligible(address)` on contract for all indexers, stores result in `is_eligible` field
  - **Pass 2**: Only for eligible indexers, calls `getEligibilityRenewalTime(address)` (function selector: `0xd353402d`) and updates `eligibility_renewal_time`
  - **Pass 3**: Determines final status based on eligibility renewal time and grace period:
    - **"eligible"**: `eligibility_renewal_time == last_oracle_update_time`
    - **"grace"**: `eligibility_renewal_time != last_oracle_update_time` AND `current_time < eligibility_renewal_time + eligibility_period`
      - Sets `eligible_until` (Unix timestamp) and `eligible_until_readable` (human-readable format)
    - **"ineligible"**: Grace period has expired or no eligibility renewal time
  - Updates `active_indexers.json` with complete eligibility data including status

#### 3. **Status Change Tracking**
- **`updateStatusChangeDates()`**: Detects and tracks status changes between runs
  - **Before generating new data**: Backs up current `active_indexers.json` to `active_indexers_previous_run.json`
  - **After eligibility check**: Compares current run with previous run
  - **Comparison logic** (by indexer address):
    - **Status changed** (e.g., "eligible" → "grace"): Sets `last_status_change_date` to current date (format: `21/Oct/2025`)
    - **Status unchanged**: Keeps the previous `last_status_change_date` value (could be empty or a date)
    - **New indexer**: Leaves `last_status_change_date` empty (no previous status to compare)
  - **Date only appears when status actually changes** - stays empty until first change occurs
  - Updates `active_indexers.json` with status change dates

#### 3b. **Activity Log for Status Changes**
- **`logStatusChanges()`**: Maintains a cumulative activity log of all status changes
  - Creates/updates `activity_log_indexers_status_changes.json`
  - **Metadata section** (overwritten each run):
    - `last_check`: Timestamp when script last ran
    - `last_oracle_update_time`: Latest oracle update from contract
  - **Status changes section** (appended):
    - Logs each status transition with: address, previous_status, new_status, date_status_change
    - Only logs actual status changes (not new indexers or unchanged statuses)
    - Preserves complete historical record of all transitions
  - Runs after `updateStatusChangeDates()` to capture all changes
  - Provides audit trail for monitoring indexer status evolution over time

#### 4. **Dashboard Rendering**
- **`renderIndexerTable()`**: Reads `active_indexers.json` and returns all indexers
  - Loads ENS names from `ens_resolution.json` cache
  - Merges ENS data with indexer eligibility data
  - Returns list of all indexers with ENS names to display on the dashboard
  - **Both eligible and ineligible indexers are displayed** with appropriate status badges

#### 5. **Transaction Data Retrieval**
The script tries multiple methods to fetch the last transaction data (in priority order):

1. **`get_last_transaction_from_json()`**: 
   - Reads from local `last_transaction.json` file (fastest, offline-capable)
   
2. **`get_last_transaction_via_rpc()`**: 
   - Scans recent blocks via RPC endpoint
   - Finds the most recent transaction to the contract address
   
3. **`get_last_transaction()`**: 
   - Falls back to Arbiscan API
   - Returns `None` if API is unavailable (no mock data used)

#### 6. **Oracle Update Time**
- **`get_oracle_update_time()`**: 
  - Calls the contract's `getLastOracleUpdateTime()` function via RPC
  - Function selector: `0xbe626dd2`
  - Returns Unix timestamp of the last oracle update

#### 7. **Eligibility Period**
- **`get_eligibility_period()`**: 
  - Calls the contract's `getEligibilityPeriod()` function via RPC
  - Function selector: `0xd0a5379e`
  - Returns eligibility period in seconds

#### 8. **HTML Generation**
- **`generate_html_dashboard()`**: 
  - Loads all indexers using `renderIndexerTable()`
  - Creates a complete, self-contained HTML file
  - Embeds all CSS styling
  - Includes JavaScript for search and sort functionality
  - **Displays all indexers** with status badges (eligible/ineligible) in the main table
  - Formats timestamps to human-readable dates

#### 9. **Telegram Notifications** (Optional)
- **`telegram_bot.py`**: 
  - Telegram bot that runs 24/7 to handle user subscriptions
  - Manages subscriber database in `subscribers_telegram.json`
  - Logs all activity to `logs/` directory
  - Provides commands: `/start`, `/subscribe`, `/unsubscribe`, `/watch`, `/unwatch`, `/watchlist`, `/status`, `/stats`, `/help`, `/test`
  - Supports indexer-specific subscriptions with personalized notifications
- **`telegram_notifier.py`**: 
  - Called by `generate_dashboard.py` after status changes are logged
  - Reads subscriber list and activity log
  - Filters notifications based on each subscriber's watched indexers
  - Shows individual indexer addresses with status transitions
  - Sends formatted daily summary messages (once per day maximum)
  - Handles rate limiting and error recovery
- **`announce_update.py`**:
  - Tool to notify all existing subscribers about new features
  - Includes confirmation prompt and success/failure statistics

## Telegram Notifications 🔔

The dashboard now supports **daily summary notifications** via Telegram bot for oracle updates and indexer status changes. Users can subscribe to receive daily summaries and optionally watch specific indexers.

### Features

- 📧 **Daily Summary Messages**: Once-per-day notification when the oracle runs and updates eligibility
- 🎯 **Watch Specific Indexers**: Subscribe to updates for specific indexers using `/watch <address>` command
- 📝 **Detailed Status Changes**: Shows individual indexer addresses with their status transitions
- ⚠️ **Grace Period Monitoring**: Alerts when indexers enter/exit grace period
- ❌ **Ineligibility Notifications**: Track when indexers become ineligible
- 📊 **Summary Statistics**: Total counts of eligible, grace, and ineligible indexers
- 👥 **Self-Service Subscription**: Users can subscribe/unsubscribe anytime via bot commands
- 📋 **Watch List Management**: `/watchlist` command to view watched indexers
- 🔗 **GIP-0079 Reference**: Direct link to proposal in help message

### Notification Examples

**Daily Summary Message (with status changes):**
```
🔔 Oracle Update Detected!
━━━━━━━━━━━━━━━━━━━
Update Time: 2025-11-03 14:30:45 UTC

📊 Dashboard Stats:
• Total Indexers: 150
• Eligible: 142 ✅
• Grace Period: 5 ⚠️
• Ineligible: 3 ❌

📝 Status Changes Detected:

0x1234567890abcdef1234567890abcdef12345678
ineligible → eligible ✅

0xabcdef1234567890abcdef1234567890abcdef12
eligible → grace period ⚠️

0x5555666677778888999900001111222233334444
grace → ineligible ❌

🔍 [View Full Dashboard](http://dashboards.thegraph.foundation/reo/)
```

**If watching specific indexers:**
When you use `/watch <address>`, you only receive notifications about your watched indexers. Example:

```
🔔 Oracle Update Detected!
━━━━━━━━━━━━━━━━━━━
Update Time: 2025-11-03 14:30:45 UTC

📊 Dashboard Stats:
• Total Indexers: 150
• Eligible: 142 ✅
• Grace Period: 5 ⚠️
• Ineligible: 3 ❌

📝 Status Changes Detected:

0x1234567890abcdef1234567890abcdef12345678
eligible → grace period ⚠️

🔍 [View Full Dashboard](http://dashboards.thegraph.foundation/reo/)
```
Only the indexers you're watching appear in status changes.

### Setup Telegram Bot

#### Step 1: Create Your Bot

1. Open Telegram and search for `@BotFather`
2. Send `/newbot` command
3. Choose a name (e.g., "REO Dashboard Alerts")
4. Choose a username (must end in 'bot', e.g., "reo_dashboard_bot")
5. BotFather will give you a **BOT TOKEN** (looks like: `123456789:ABCdef...`)
6. Save this token securely

#### Step 2: Configure Environment

Add the bot token to your `.env` file:

```bash
# Telegram Bot Configuration (optional)
TELEGRAM_BOT_TOKEN=your_bot_token_here
```

#### Step 3: Install Dependencies

```bash
pip3 install python-telegram-bot==20.7
```

Or use the requirements file:
```bash
pip3 install -r requirements.txt
```

#### Step 4: Run the Bot

The bot needs to run continuously to accept user subscriptions. Choose one method:

**Option A: Using screen (Recommended for simplicity)**
```bash
cd /home/graph/ftpbox/reo
screen -S telegram_bot
python3 telegram_bot.py
# Press Ctrl+A then D to detach
```

To manage the screen session:
```bash
# List running screens
screen -ls

# Reattach to view logs
screen -r telegram_bot

# Kill the bot
screen -X -S telegram_bot quit
```

**Option B: Using systemd (Recommended for production)**
```bash
# Copy service file
sudo cp telegram_bot_service.service /etc/systemd/system/telegram_bot.service

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable telegram_bot.service
sudo systemctl start telegram_bot.service

# Check status
sudo systemctl status telegram_bot.service

# View logs
sudo journalctl -u telegram_bot.service -f

# Restart if needed
sudo systemctl restart telegram_bot.service
```

**Option C: Using nohup (Simple background process)**
```bash
cd /home/graph/ftpbox/reo
nohup python3 telegram_bot.py > telegram_bot.log 2>&1 &

# Check if running
ps aux | grep telegram_bot.py

# View logs
tail -f telegram_bot.log

# Kill if needed
pkill -f telegram_bot.py
```

#### Step 5: Schedule Dashboard Script

Set up a cron job to run the dashboard script periodically:

```bash
crontab -e
```

Add one of these lines:
```bash
# Run every hour
0 * * * * cd /home/graph/ftpbox/reo && /usr/bin/python3 generate_dashboard.py >> /home/graph/ftpbox/reo/cron.log 2>&1

# Run every 30 minutes
*/30 * * * * cd /home/graph/ftpbox/reo && /usr/bin/python3 generate_dashboard.py >> /home/graph/ftpbox/reo/cron.log 2>&1
```

View cron logs:
```bash
tail -f /home/graph/ftpbox/reo/cron.log
```

### Bot Commands

Users can interact with the bot using these commands:

| Command | Description |
|---------|-------------|
| `/start` | Welcome message with bot introduction |
| `/subscribe` | Subscribe to receive notifications |
| `/unsubscribe` | Stop receiving notifications |
| `/status` | Check your subscription status |
| `/stats` | View bot statistics (total subscribers, notifications sent) |
| `/help` | Show available commands and help |
| `/test` | Send a test notification (for subscribed users) |

### How Users Subscribe

1. Search for your bot on Telegram (using the username you chose)
2. Send `/start` or `/subscribe` to the bot
3. Receive confirmation message
4. Start getting notifications when the dashboard script runs!

### Subscriber Management

The bot automatically manages subscribers in `subscribers_telegram.json`:

```json
{
  "subscribers": [
    {
      "chat_id": 123456789,
      "username": "user123",
      "subscribed_at": "2025-10-22 14:30:00",
      "active": true
    }
  ],
  "stats": {
    "total_subscribers": 1,
    "total_notifications_sent": 45
  }
}
```

### Troubleshooting

**Bot not responding:**
- Check if bot is running: `ps aux | grep telegram_bot.py` or `screen -ls`
- Check bot logs: `tail -f telegram_bot.log` or `sudo journalctl -u telegram_bot.service -f`
- Verify `TELEGRAM_BOT_TOKEN` is set correctly in `.env`

**Notifications not sending:**
- Check cron is running: `crontab -l`
- View cron logs: `tail -f cron.log`
- Verify bot token is valid
- Check for errors in dashboard script output

**Rate limiting errors:**
- Telegram has rate limits (30 messages/second)
- The notifier includes small delays between messages
- For large subscriber lists (100+), messages are automatically paced

## File Structure

```
.
├── generate_dashboard.py                          # Main script
├── indexers.txt                                   # Legacy file (still read for backwards compatibility)
├── active_indexers.json                           # Active indexers with eligibility data (generated)
├── active_indexers_previous_run.json              # Backup of previous run for status change tracking (generated)
├── activity_log_indexers_status_changes.json      # Activity log tracking all status changes (generated)
├── activity_log_indexers_status_changes.json.example  # Example format for activity log
├── ens_resolution.json                            # ENS name cache (generated)
├── last_transaction.json                          # Cached transaction data (generated)
├── grt.png                                        # Logo image for the dashboard
├── index.html                                     # Generated dashboard (output)
├── .env                                           # Environment variables (create from env.example)
├── env.example                                    # Template for environment variables
├── requirements.txt                               # Python dependencies
├── README.md                                      # This file
│
├── telegram_bot.py                                # Telegram bot for user subscriptions (optional)
├── telegram_notifier.py                           # Notification sender module (optional)
├── telegram_bot_service.service                   # Systemd service file for bot (optional)
├── subscribers_telegram.json                      # Subscriber database (generated by bot)
├── subscribers_telegram.json.example              # Example subscriber structure
├── logs/                                          # Telegram bot logs directory (generated)
│   ├── telegram_bot.log                           # Bot technical logs
│   └── telegram_bot_activity.log                  # User activity logs
└── cron.log                                       # Cron job logs (generated)
```

## Usage

### Prerequisites

```bash
pip install -r requirements.txt
```

Or install manually:
```bash
pip install requests python-dotenv pycryptodome
```

### Environment Variables

The script reads configuration from a `.env` file in the project root. 

**Setup:**
1. Copy the example file:
   ```bash
   cp env.example .env
   ```

2. Edit `.env` and add your actual values:
   ```bash
   CONTRACT_ADDRESS=0x9BED32d2b562043a426376b99d289fE821f5b04E
   ARBISCAN_API_KEY=your_arbiscan_api_key
   RPC_ENDPOINT=your_rpc_endpoint_url
   GRAPH_API_KEY=your_graph_api_key
   USE_CACHED_ENS=N
   ```

The script will automatically load these variables. The first four variables are required for the script to run.

### Running the Script

```bash
python3 generate_dashboard.py
```

This will:
1. **Backup previous run**: Copy `active_indexers.json` to `active_indexers_previous_run.json` (if it exists)
2. **Retrieve active indexers** from The Graph's network subgraph (with self stake > 0)
3. **Fetch contract metadata**:
   - Call `getLastOracleUpdateTime()` to get the latest oracle update timestamp
   - Call `getEligibilityPeriod()` to get the grace period duration (14 days)
4. **Resolve ENS names**:
   - If `USE_CACHED_ENS=Y`: Load ENS names from `ens_resolution.json` cache
   - If `USE_CACHED_ENS=N`: Query ENS subgraph and update `ens_resolution.json` cache
5. **Check eligibility** (Three-Pass Approach):
   - **Pass 1**: Call contract's `isEligible()` function for all indexers
   - **Pass 2**: Call `getEligibilityRenewalTime()` for eligible indexers
   - **Pass 3**: Determine status based on renewal time comparison and grace period:
     - Set status to "eligible", "grace", or "ineligible"
     - Calculate `eligible_until` for grace period indexers
6. **Track status changes**: Compare with previous run to detect status changes
   - If status changed: Set `last_status_change_date` to current date
   - If status unchanged: Keep previous date (or empty if no previous change)
   - If new indexer: Leave date empty
7. **Log status changes to activity log**: Append status transitions to cumulative log
   - Update metadata (last_check, last_oracle_update_time)
   - Append new status change entries to historical record
8. Save complete indexer data to `active_indexers.json` (without ENS names)
9. **Render dashboard** showing all indexers with status badges (eligible/grace/ineligible) merged with ENS names from cache
10. Fetch the latest transaction data
11. Generate `index.html` with sorted table and interactive features

### Opening the Dashboard

```bash
open index.html
```

Or simply double-click `index.html` to open it in your browser.

## Configuration

All configuration is managed through environment variables in the `.env` file:

### Contract Address
- **Variable**: `CONTRACT_ADDRESS`
- **Default**: `0x9BED32d2b562043a426376b99d289fE821f5b04E` (Arbitrum Sepolia)
- **Purpose**: The Rewards Eligibility Oracle contract address

### Arbiscan API Key
- **Variable**: `ARBISCAN_API_KEY`
- **Purpose**: Fetches transaction data from Arbiscan API
- **Get yours**: [Arbiscan API Keys](https://arbiscan.io/myapikey)

### RPC Endpoint
- **Variable**: `RPC_ENDPOINT`
- **Purpose**: Connects to Arbitrum Sepolia for real-time blockchain data
- **Supported Providers**: Any Ethereum RPC provider (Alchemy, Infura, QuickNode, Ankr, etc.)
- **Get yours**: 
  - [QuickNode](https://quicknode.com)
  - [Alchemy](https://alchemy.com)
  - [Infura](https://infura.io)
  - [Ankr](https://ankr.com)

### The Graph API Key
- **Variable**: `GRAPH_API_KEY`
- **Purpose**: Queries The Graph's network and ENS subgraphs
- **Get yours**: [The Graph Studio](https://thegraph.com/studio/)

### ENS Cache Configuration
- **Variable**: `USE_CACHED_ENS`
- **Values**: `Y` or `N`
- **Purpose**: Controls whether to use cached ENS data or fetch from subgraph
  - **`Y`**: Use cached ENS names from `ens_resolution.json` (faster, saves API calls)
  - **`N`**: Query ENS subgraph and update cache (required for first run or to refresh ENS data)
- **Default**: `N`
- **Note**: On first run or when cache doesn't exist, ENS data will be fetched regardless of this setting

## Data Sources

### Generated: `active_indexers.json`
This file is automatically generated by the script and contains all active indexers with their eligibility data (without ENS names).

Structure:
```json
{
  "metadata": {
    "retrieved": "2025-10-21 08:00:00 UTC",
    "total_count": 99,
    "last_oracle_update_time": 1760956267,
    "eligibility_period": 1209600
  },
  "indexers": [
    {
      "address": "0x0058223c6617cca7ce76fc929ec9724cd43d4542",
      "is_eligible": true,
      "status": "eligible",
      "eligible_until": "",
      "eligible_until_readable": "",
      "eligibility_renewal_time": 1760956267,
      "last_status_change_date": ""
    },
    {
      "address": "0x51637a35f7f054c98ed51904de939b9561d37885",
      "is_eligible": true,
      "status": "grace",
      "eligible_until": 1762111555,
      "eligible_until_readable": "2025-11-02 19:25:55 UTC",
      "eligibility_renewal_time": 1760901955,
      "last_status_change_date": "21/Oct/2025"
    }
  ]
}
```

**Metadata Fields:**
- `retrieved`: Timestamp when the data was fetched
- `total_count`: Total number of active indexers
- `last_oracle_update_time`: Unix timestamp from contract's `getLastOracleUpdateTime()`
- `eligibility_period`: Duration in seconds (14 days = 1209600 seconds) from contract's `getEligibilityPeriod()`

**Indexer Fields:**
- `is_eligible`: Boolean indicating if the indexer returned `true` from contract's `isEligible()`
- `eligibility_renewal_time`: Unix timestamp of eligibility renewal (from contract's `getEligibilityRenewalTime()`)
- `status`: Current eligibility status - one of three values:
  - **"eligible"**: Renewal time matches oracle update time
  - **"grace"**: Within grace period (renewal time + eligibility period > current time)
  - **"ineligible"**: Grace period expired or never eligible
- `eligible_until`: Unix timestamp when grace period expires (only set for "grace" status)
- `eligible_until_readable`: Human-readable expiration date (only set for "grace" status)
- `last_status_change_date`: Date when the status last changed (format: `21/Oct/2025`)
  - **Empty string** (`""`) if status has never changed or for new indexers
  - **Date string** (e.g., `"21/Oct/2025"`) if status changed compared to previous run
  - Tracks status transitions between any states (eligible ↔ grace ↔ ineligible)
- **All indexers are displayed on the dashboard with status badges**

### Generated: `ens_resolution.json`
This file is automatically generated by the script and contains cached ENS name resolutions.

Structure:
```json
{
  "metadata": {
    "retrieved": "2025-10-17 20:00:00 UTC",
    "total_count": 100,
    "ens_resolved": 74
  },
  "ens_resolutions": {
    "0x0058223c6617cca7ce76fc929ec9724cd43d4542": "grassets-tech-2.eth",
    "0x01f17c392614c7ea586e7272ed348efee21b90a3": "oraclegen-indexer.eth",
    "0x0874e792462406dc12ee96b75e52a3bdbba3a123": "posthuman-validator.eth"
  }
}
```

**Key Fields:**
- `ens_resolutions`: Dictionary mapping lowercase addresses to ENS names
- `total_count`: Total number of addresses in the cache
- `ens_resolved`: Number of addresses with resolved ENS names
- **This cache is used during dashboard rendering to merge ENS names with indexer data**

### Cache: `last_transaction.json`
Example:
```json
{
  "hash": "0x4401f694b80775533566053f88026220e1eab4c84f771e5b600df76f89a768bc",
  "blockNumber": "205536308",
  "timeStamp": "1760696509",
  "status": "Success",
  "readable_time": "Oct-17-2025 10:21:49"
}
```

### Backup: `active_indexers_previous_run.json`
This file is automatically created as a backup of the previous run's `active_indexers.json`.

**Purpose:**
- Enables status change tracking between script runs
- Contains the exact same structure as `active_indexers.json`
- Automatically created/overwritten before each new run
- Only the most recent previous run is kept (no historical archive)

**Usage in Status Change Detection:**
Each time the script runs, it:
1. Backs up current `active_indexers.json` → `active_indexers_previous_run.json`
2. Generates new `active_indexers.json` with fresh data
3. Compares the new file with the backup to detect status changes
4. Updates `last_status_change_date` in the new file based on comparison

**Example Scenario:**
- **Run 1**: Indexer X has status "eligible" → `last_status_change_date` = `""`
- **Run 2**: Indexer X still has status "eligible" → `last_status_change_date` = `""` (no change)
- **Run 3**: Indexer X changes to status "grace" → `last_status_change_date` = `"21/Oct/2025"` (change detected!)
- **Run 4**: Indexer X still has status "grace" → `last_status_change_date` = `"21/Oct/2025"` (keeps previous date)

### Activity Log: `activity_log_indexers_status_changes.json`
This file maintains a cumulative historical record of all indexer status changes.

**Purpose:**
- Creates an audit trail of status transitions over time
- Preserves complete history of all status changes (not just the most recent)
- Enables analysis of indexer behavior patterns
- Provides accountability and transparency for status evolution

**Structure:**
```json
{
  "metadata": {
    "last_check": "2025-10-21 11:14:06 UTC",
    "last_oracle_update_time": 1761040822
  },
  "status_changes": [
    {
      "address": "0x0874e792462406dc12ee96b75e52a3bdbba3a123",
      "previous_status": "grace",
      "new_status": "eligible",
      "date_status_change": "2025-10-21"
    },
    {
      "address": "0x1234567890abcdef1234567890abcdef12345678",
      "previous_status": "eligible",
      "new_status": "grace",
      "date_status_change": "2025-10-22"
    }
  ]
}
```

**How It Works:**
Each time the script runs, it:
1. **Updates metadata** (overwrites):
   - `last_check`: Current timestamp when script ran
   - `last_oracle_update_time`: Latest oracle update from contract
2. **Appends status changes**:
   - Detects any indexer status transitions
   - Adds new entries with address, previous_status, new_status, and date
   - Never removes or modifies existing entries
3. **Preserves history**:
   - File grows over time as status changes accumulate
   - Complete historical record of all transitions
   - Can track patterns (e.g., indexer cycling between statuses)

**Key Fields:**
- `address`: Indexer Ethereum address
- `previous_status`: Status before the change (eligible/grace/ineligible)
- `new_status`: Status after the change (eligible/grace/ineligible)
- `date_status_change`: Date when the change was detected (YYYY-MM-DD format)

**Example Usage:**
- Monitor which indexers frequently lose eligibility
- Track grace period usage patterns
- Identify indexers that maintain consistent eligible status
- Generate reports on overall network eligibility trends

## Dashboard Features

### Contract Information Section
**Collapsible debug section** (click header to expand/collapse):
- **Sepolia Contract on Arbitrum**: Contract address with link to Arbiscan
- **Last Oracle Update Time**: Latest oracle update timestamp from the contract
- **Last Transaction ID**: Transaction hash with link to Arbiscan
- **Block Number**: Block where the transaction occurred
- **Eligibility Period**: 14-day grace period duration (1209600 seconds)

### Search and Filter Bar
**Combined search and filter section** (search left-aligned, filters right-aligned):
- **Search Box**: Real-time filtering by indexer address or ENS name
- **Status Filter Buttons**: Click to filter by status (eligible, grace, ineligible)
  - **Active State**: Selected filters invert colors (solid background, dark text)
  - **Toggle Behavior**: Click again to remove filter
  - **Reset Button**: Clears both search and status filter
  - **Helpful Tooltips**: Hover over any filter button to see instant descriptions (custom CSS tooltips with 0.2s fade-in):
    - **eligible**: "Indexers that are eligible for rewards"
    - **grace**: "Grace period is XX days" (dynamically shows actual period from contract)
    - **ineligible**: "Indexers that are NOT eligible for rewards"
    - **Reset**: "Show All"
- **Combined Filtering**: Search and status filters work together

### Indexers Table
- **All Indexers Displayed**: Shows all active indexers (eligible, grace period, and ineligible)
- **Status Badges**: 
  - **eligible** (green): Indexer's renewal time matches oracle update time
  - **grace** (yellow): Indexer is in grace period - eligible until expiration date shown
  - **ineligible** (red): Indexer's grace period has expired or never eligible
- **Eligible Until Column**: Shows grace period expiration date in format: `2-Nov-2025 at 19:25:55 UTC`
- **Smart Sorting**: Automatically sorted by eligibility status first (eligible → grace → ineligible), then alphabetically by ENS name
- **Sortable columns**: Click any header to sort by that column (while maintaining eligibility priority)
- **Statistics**: Shows total indexers and filtered count
- **Color-coded**: ENS names highlighted, missing ENS shown in gray
- **Clickable addresses**: Each indexer address links to their profile on The Graph Explorer

## Technical Details

### Status Determination Logic
The script uses a three-tier status system:

```python
if eligibility_renewal_time == last_oracle_update_time:
    status = "eligible"
elif eligibility_renewal_time != last_oracle_update_time:
    grace_period_end = eligibility_renewal_time + eligibility_period
    if current_time < grace_period_end:
        status = "grace"
        eligible_until = grace_period_end
    else:
        status = "ineligible"
else:
    status = "ineligible"
```

### Timestamp Conversion
All Unix timestamps are converted to UTC format:
```python
datetime.fromtimestamp(timestamp_int, tz=timezone.utc)
    .strftime("%Y-%m-%d %H:%M:%S UTC")
```

### Contract Function Calls
The script calls multiple contract functions using RPC:
```python
# getLastOracleUpdateTime()
function_selector = '0xbe626dd2'

# getEligibilityPeriod()
function_selector = '0xd0a5379e'

# getEligibilityRenewalTime(address)
function_selector = '0xd353402d'
```

### Block Scanning
When fetching transactions, the script scans the last 100 blocks to find the most recent transaction to the contract address.

## Error Handling

The script includes robust error handling with **no mock data**:
- Falls back through multiple data sources (JSON → RPC endpoint → Arbiscan)
- Prints informative console messages for debugging
- Gracefully handles missing data without using fake/mock values
- Displays clear error messages in the dashboard UI when data is unavailable:
  - **"Unable to fetch transaction data"** - when all transaction fetch methods fail
  - **"Unable to fetch oracle update time"** - when contract call fails
- All errors are displayed in styled red text (`.error-message` class) in the dashboard

## Styling

The dashboard uses a modern dark theme:
- **Background**: `#0C0A1D` (dark purple)
- **Text**: `#F8F6FF` (off-white)
- **Accent**: `#494755` (medium gray)
- **Font**: Poppins (from Google Fonts)

## Browser Compatibility

Works in all modern browsers:
- Chrome/Edge (Chromium)
- Firefox
- Safari
- Mobile browsers

## License

MIT License

Copyright (c) 2025

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

## Contact

**X (Twitter):** [@pdiomede](https://x.com/pdiomede)

