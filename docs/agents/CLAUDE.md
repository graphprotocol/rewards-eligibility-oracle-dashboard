# CLAUDE.md

This file provides guidance to AI coding assistants when working with code in this repository.

## Project Overview

This is a **Python-based static dashboard** for monitoring The Graph Protocol's Rewards Eligibility Oracle (GIP-0079). The system tracks indexer eligibility for rewards based on service quality metrics, displaying real-time blockchain data in a self-contained HTML dashboard.

**Key Architecture**: Pure Python script (no web framework) → generates static `index.html` → deployed to static hosting via Docker Compose with scheduler that regenerates every 5 minutes.

**Production URL**: https://hub.thegraph.org/reo/

## CRITICAL: Deployment Warnings

**READ BEFORE DEPLOYING**: This section contains critical deployment lessons learned that are not obvious.

### Always Restart the Scheduler

⚠️ **Pulling a new image does NOT update running containers:**

The `reo-scheduler` container runs continuously and regenerates the dashboard every 5 minutes. Simply pulling the image won't update it - you MUST restart the scheduler.

```bash
# Correct deployment workflow:
cd dashboard-infrastructure/
docker pull ghcr.io/graphprotocol/rewards-eligibility-oracle-dashboard:latest
docker compose up -d --force-recreate reo reo-scheduler

# Verify the version in production
docker exec dashboards-caddy grep -o "v[0-9]\+\.[0-9]\+\.[0-9]\+" /usr/share/nginx/html/reo/index.html | head -1
```

**Mnemonic: "Pull one, restart both"** - When you pull the `reo` image, restart BOTH `reo` AND `reo-scheduler`.

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
- [ ] Restarted BOTH `reo` and `reo-scheduler` containers
- [ ] Verified version in production (via curl or browser)
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
open output/index.html  # macOS
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

### Running Tests
```bash
# Run all unit tests
pytest tests/unit/

# Run specific test file
pytest tests/unit/test_block_parsing.py -v

# Run integration tests (requires environment setup)
bash tests/integration/test_frontend_toggle.sh
```

### Telegram Bot (Optional)
```bash
# Run the bot 24/7 for user subscriptions
python3 telegram_bot.py
```

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
   - `eligible-active`: renewal_time == oracle_update_time
   - `eligible-grace`: renewal_time != oracle_update_time AND within grace period
   - `ineligible-expired`: grace period expired (previously eligible)
   - `ineligible-unqualified`: never qualified

### Status System

The dashboard tracks four distinct states:
- **Eligible-Active** (green): Actively renewed in latest oracle update
- **Eligible-Grace** (yellow): Still eligible but needs action (14-day countdown)
- **Ineligible-Expired** (red): Grace period expired (previously eligible)
- **Ineligible-Unqualified** (red): Never qualified

**Status Change Tracking**: Each run compares with previous run to detect transitions and update `last_status_change_date`.

### State Management

**Hybrid approach** - uses both JSON files and SQLite database:

**JSON files** (for data exchange):
- `active_indexers.json` - Current indexer data (generated each run)
- `active_indexers_previous_run.json` - Backup for comparison (auto-created)
- `ens_resolution.json` - ENS name cache (controlled by `USE_CACHED_ENS` env var)
- `activity_log_indexers_status_changes.json` - Cumulative audit log of all status changes
- `subscribers_telegram.json` - Telegram subscriber database (if bot enabled)

**SQLite database** (for persistent state):
- `reo.db` - Stores ENS cache, transaction data, and other state across runs

### Round-Robin RPC Load Balancing

The `RoundRobinRPC` class distributes RPC calls across multiple endpoints:
- Configure via `RPC_ENDPOINT` (single) or `RPC_ENDPOINT_1`, `RPC_ENDPOINT_2`, etc. in `.env`
- Automatically rotates through available endpoints
- Falls back to next endpoint on failure
- Backward compatible with single `RPC_ENDPOINT` variable

### Multi-Environment Support

The dashboard supports multiple contract deployments simultaneously:
- Environment data fetched from [GitHub JSON Registry](https://raw.githubusercontent.com/graphprotocol/contracts/refs/heads/main/packages/issuance/addresses.json)
- Contract addresses auto-discovered for each network (Arbitrum One, Arbitrum Sepolia)
- JavaScript environment toggle switches between deployments client-side
- Each environment has its own indexer data and eligibility state

## Key Files

- **`generate_dashboard.py`** (3400+ lines) - Main script containing all logic
  - `retrieveActiveIndexers()` - Fetches from subgraph with ENS resolution
  - `checkEligibility()` - Three-pass contract interaction
  - `updateStatusChangeDates()` - Compares runs to detect changes
  - `logStatusChanges()` - Appends to cumulative activity log
  - `generate_html_dashboard()` - Creates self-contained HTML with embedded CSS/JS

- **`scheduler.py`** - Runs continuously, regenerates dashboard every 5 minutes
  - Reads from `.env` for configuration
  - Calls `generate_dashboard.py()` on schedule
  - Logs generation results

- **`telegram_bot.py`** - 24/7 bot service for user subscriptions
  - Commands: `/start`, `/watch <address>`, `/unwatch <address>`, `/watchlist`, `/status`, `/help`, `/test`
  - Manages `subscribers_telegram.json`

- **`telegram_notifier.py`** - Notification sender (called by dashboard script)
  - Filters notifications by watched indexers
  - Sends daily summaries via Telegram

- **`database.py`** - SQLite database operations
  - ENS cache storage and retrieval
  - Transaction data caching
  - Schema initialization

- **`env.example`** - Template for `.env` configuration
  - Required: `ARBISCAN_API_KEY`, `GRAPH_API_KEY`, `RPC_ENDPOINT`
  - Optional: `TELEGRAM_BOT_TOKEN`, `DASHBOARD_URL`, `USE_CACHED_ENS`
  - Manual environment config: `TESTNET_NEW_CONTRACT_ADDRESS`, `TESTNET_NEW_DEPLOYMENT_BLOCK`

## Contract Interaction

**Direct RPC calls** (no web3.py/library dependencies):
- Contract functions called via raw JSON-RPC with manual function selectors
- `getLastOracleUpdateTime()`: `0xbe626dd2`
- `getEligibilityPeriod()`: `0xd0a5379e`
- `getEligibilityRenewalTime(address)`: `0xd353402d`

## Error Handling Strategy

**Graceful degradation** with multiple fallbacks:
1. Primary: RPC endpoint (round-robin across multiple)
2. Fallback 1: Cached data in SQLite database
3. Fallback 2: Arbiscan API (transaction data only)
4. **No mock data** - displays clear error messages when all sources fail

## Common Patterns

### Modifying Eligibility Logic
1. Edit `checkEligibility()` in `generate_dashboard.py` (Pass 3 status determination)
2. Test by running script and checking `active_indexers.json` status field
3. Verify HTML dashboard displays correct badges

### Adding Dashboard Features
1. HTML generation is in `generate_html_dashboard()` function
2. CSS is embedded directly in `<style>` tags (no separate CSS file)
3. JavaScript for interactivity is embedded in `<script>` tags
4. For multi-environment support, add to `environments` dict before HTML generation

### Updating Subgraph Queries
1. Query in `retrieveActiveIndexers()` function
2. Network subgraph: `DZz4kDTdmzWLWsV373w2bSmoar3umKKH9y82SUKr5qmp`
3. ENS subgraph: `5XqPmWe6gjyrJtFn9cLy237i4cWw2j9HcUJEXsP5qGtH`

### Debugging Contract Calls
1. Check `active_indexers.json` for raw data
2. Verify `.env` has correct RPC endpoint
3. Script prints debug info to console (check scheduler logs)
4. Use Arbiscan to verify contract state

## Deployment

**Production deployment** uses Docker Compose:
- Separate infrastructure repository: `dashboard-infrastructure`
- `reo` container: One-shot container that generates dashboard on startup
- `reo-scheduler` container: Runs continuously, regenerates every 5 minutes
- `caddy` container: Web server that serves static HTML files
- Volumes: `reo-output` for generated HTML, `reo-data` for database

**For detailed deployment instructions**, see `DEPLOYMENT.md`.
