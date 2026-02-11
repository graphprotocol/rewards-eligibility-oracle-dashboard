# CLAUDE.md

This file provides guidance to AI coding assistants when working with code in this repository.

## Project Overview

This is a **Python-based static dashboard** for monitoring The Graph Protocol's Rewards Eligibility Oracle (GIP-0079). The system tracks indexer eligibility for rewards based on service quality metrics, displaying real-time blockchain data in a self-contained HTML dashboard.

**Key Architecture**: Pure Python script (no web framework) → generates static `index.html` → deployed to static hosting. The script runs periodically via cron to update eligibility data from smart contracts.

## CRITICAL: Deployment Warnings

**READ BEFORE DEPLOYING**: This section contains critical deployment lessons learned that are not obvious.

### Docker Image Caching Issue

⚠️ **The standard deployment commands will NOT pull new images due to Docker caching:**

```bash
# THIS DOES NOT WORK AS EXPECTED:
docker compose pull reo reo-scheduler
docker compose up -d reo reo-scheduler
# Containers will keep using the OLD cached image!
```

**Always force pull images before deployment:**
```bash
# Force pull the latest image (ignores local cache)
docker pull ghcr.io/graphprotocol/rewards-eligibility-oracle-dashboard:latest

# Verify the image was actually updated
docker images ghcr.io/graphprotocol/rewards-eligibility-oracle-dashboard --format "{{.CreatedAt}}"

# Force recreate containers with the new image
docker compose up -d --force-recreate reo reo-scheduler

# Verify the version in the running container
docker exec reo-scheduler-prod python -c "import generate_dashboard; print(generate_dashboard.VERSION)"
```

### GitHub Actions Timing

⚠️ **After merging a PR, the `:latest` image is NOT immediately available:**

1. PR workflow creates `:pr-<number>` tag only (not `:latest`)
2. After merge, wait for `main` branch workflow to complete (~30-40 seconds)
3. Only the `main` branch workflow pushes the `:latest` tag
4. **Verify workflow completed before deploying:**
   ```bash
   gh run list --branch main --limit 1
   # Wait for "completed success" status
   ```

### Production Testing Requirements

⚠️ **HTML grep checks are NOT sufficient for UI changes:**

Just verifying HTML contains certain strings doesn't mean the feature works:
- ❌ `grep "environment-select"` - Only checks HTML exists
- ✅ **Open in actual browser** - Click toggle, verify it works
- ✅ **Check browser console** - No JavaScript errors
- ✅ **Test localStorage** - Refresh page, verify persistence

**For any UI change, you MUST test in a real browser before considering deployment complete.**

### Full Deployment Checklist

Before calling deployment "done", verify:

- [ ] Waited for main branch workflow to complete
- [ ] Force pulled new Docker image
- [ ] Verified image timestamp is recent
- [ ] Force recreated containers
- [ ] Verified version number in running container
- [ ] Opened production URL in browser
- [ ] Checked browser console for errors
- [ ] Tested new functionality works
- [ ] Tested old functionality still works (regression)
- [ ] Verified visual changes match expectations

**See `DEPLOYMENT.md` for detailed explanations and examples.**

## Development Commands

### Running the Dashboard
```bash
# Generate the dashboard (fetches live data from contracts/subgraphs)
python3 generate_dashboard.py

# View the generated dashboard
open index.html  # macOS
# or open in browser directly
```

### Environment Setup
```bash
# Install dependencies
pip3 install -r requirements.txt

# Create environment file from template
cp env.example .env
# Then edit .env with your actual API keys and endpoints
```

### Telegram Bot (Optional)
```bash
# Run the bot 24/7 for user subscriptions
python3 telegram_bot.py

# Or run via systemd (production)
sudo systemctl start telegram_bot.service
sudo systemctl status telegram_bot.service

# View bot logs
tail -f logs/telegram_bot.log
# or for systemd
sudo journalctl -u telegram_bot.service -f
```

### Testing/Simulation
There are **no unit tests** in this codebase. Testing is done by:
1. Running `generate_dashboard.py` and verifying output in `index.html`
2. Checking `active_indexers.json` for correct data structure
3. For Telegram: `python3 telegram_bot.py` and send `/test` command

## Architecture Overview

### Data Flow Pipeline

```
Network Subgraph (Active Indexers) → ENS Subgraph (Names) → Oracle Contract (Eligibility)
                                      ↓
                            generate_dashboard.py
                                      ↓
                    JSON Cache Files + HTML Dashboard
```

**Three-Pass Eligibility Check** (critical pattern in `generate_dashboard.py`):
1. **Pass 1**: Call `isEligible(address)` for all indexers
2. **Pass 2**: Call `getEligibilityRenewalTime(address)` only for eligible indexers
3. **Pass 3**: Determine status by comparing renewal time with oracle update time:
   - `eligible`: renewal_time == oracle_update_time
   - `grace`: renewal_time != oracle_update_time AND within 14-day period
   - `ineligible`: grace period expired

### Status System

The dashboard tracks three distinct states (not binary):
- **Eligible** (green): Actively renewed in latest oracle update
- **Grace** (yellow): Still eligible but needs action (14-day countdown)
- **Ineligible** (red): Grace period expired or never qualified

**Status Change Tracking**: Each run compares with `active_indexers_previous_run.json` to detect transitions and update `last_status_change_date`.

### File-Based State Management

**No database** - all state stored in JSON files:
- `active_indexers.json` - Current indexer data (generated each run)
- `active_indexers_previous_run.json` - Backup for comparison (auto-created)
- `ens_resolution.json` - ENS name cache (controlled by `USE_CACHED_ENS` env var)
- `last_transaction.json` - Cached transaction data for offline capability
- `activity_log_indexers_status_changes.json` - Cumulative audit log of all status changes
- `subscribers_telegram.json` - Telegram subscriber database (if bot enabled)

### Round-Robin RPC Load Balancing

The `RoundRobinRPC` class distributes RPC calls across multiple endpoints:
- Configure via `RPC_ENDPOINT_1`, `RPC_ENDPOINT_2`, etc. in `.env`
- Automatically rotates through available endpoints
- Falls back to next endpoint on failure
- Backward compatible with single `RPC_ENDPOINT` variable

## Key Files

- **`generate_dashboard.py`** (2700+ lines) - Main script containing all logic
  - `retrieveActiveIndexers()` - Fetches from subgraph with ENS resolution
  - `checkEligibility()` - Three-pass contract interaction
  - `updateStatusChangeDates()` - Compares runs to detect changes
  - `logStatusChanges()` - Appends to cumulative activity log
  - `renderIndexerTable()` - Merges ENS with eligibility data
  - `generate_html_dashboard()` - Creates self-contained HTML

- **`telegram_bot.py`** - 24/7 bot service for user subscriptions
  - Commands: `/start`, `/subscribe`, `/unsubscribe`, `/watch`, `/unwatch`, `/watchlist`, `/status`, `/stats`, `/help`, `/test`
  - Manages `subscribers_telegram.json`

- **`telegram_notifier.py`** - Notification sender (called by dashboard script)
  - Filters notifications by watched indexers
  - Sends daily summaries via Telegram

- **`env.example`** - Template for `.env` configuration
  - Required: `CONTRACT_ADDRESS`, `ARBISCAN_API_KEY`, `RPC_ENDPOINT`, `GRAPH_API_KEY`
  - Optional: `TELEGRAM_BOT_TOKEN`, `DASHBOARD_URL`, `USE_CACHED_ENS`

## Contract Interaction

**Direct RPC calls** (no web3.py/library dependencies):
- Contract functions called via raw JSON-RPC with manual function selectors
- `getLastOracleUpdateTime()`: `0xbe626dd2`
- `getEligibilityPeriod()`: `0xd0a5379e`
- `getEligibilityRenewalTime(address)`: `0xd353402d`

## Error Handling Strategy

**Graceful degradation** with multiple fallbacks:
1. Primary: Cached JSON data (offline-capable)
2. Fallback 1: RPC endpoint (round-robin across multiple)
3. Fallback 2: Arbiscan API (transaction data only)
4. **No mock data** - displays clear error messages when all sources fail

## Common Patterns

### Modifying Eligibility Logic
1. Edit `checkEligibility()` in `generate_dashboard.py` (Pass 3 status determination)
2. Test by running script and checking `active_indexers.json` status field
3. Verify HTML dashboard displays correct badges

### Adding Dashboard Features
1. HTML generation is in `generate_html_dashboard()` function
2. CSS is embedded directly (no separate CSS file)
3. JavaScript for interactivity is embedded in `<script>` tags

### Updating Subgraph Queries
1. Query in `retrieveActiveIndexers()` function
2. Network subgraph: `DZz4kDTdmzWLWsV373w2bSmoar3umKKH9y82SUKr5qmp`
3. ENS subgraph: `5XqPmWe6gjyrJtFn9cLy237i4cWw2j9HcUJEXsP5qGtH`

### Debugging Contract Calls
1. Check `active_indexers.json` for raw data
2. Verify `.env` has correct RPC endpoint
3. Script prints debug info to console (check cron.log if running via cron)
4. Use Arbiscan to verify contract state: https://arbiscan.io/address/0x9BED32d2b562043a426376b99d289fE821f5b04E

## Deployment

The dashboard is **static HTML** with no backend:
- Deploy `index.html` to any static hosting (Netlify, GitHub Pages, nginx)
- No server-side code execution required
- Script runs on separate server via cron, uploads HTML to static host

Typical cron schedule: Every 30 minutes or hourly
```bash
crontab -e
# Add: */30 * * * * cd /path/to/repo && python3 generate_dashboard.py >> cron.log 2>&1
```

---

See also [agents.md](agents.md) for additional AI coding assistant guidelines specific to this project.
