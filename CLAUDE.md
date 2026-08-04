# CLAUDE.md

This file provides guidance to AI coding assistants when working with code in this repository.

## Project Overview

This is a **Python-based static dashboard** for monitoring The Graph Protocol's Rewards Eligibility Oracle (GIP-0079). The system tracks indexer eligibility for rewards based on service quality metrics, displaying real-time blockchain data in a self-contained HTML dashboard.

**Key Architecture**: Pure Python script (no web framework) → generates static `index.html` → deployed to static hosting via Docker Compose with scheduler that regenerates every 5 minutes.

**Production URL**: https://hub.thegraph.foundation/reo/

## CRITICAL: Deployment Warnings

**READ BEFORE DEPLOYING**: every item here comes from something that actually
broke in production.

### The deploy

```bash
cd dashboard-infrastructure/
docker compose pull reo reo-scheduler
docker compose up -d --force-recreate reo reo-scheduler

# Then ALWAYS verify visually (see below) — never by HTTP status alone:
cd ../rewards-eligibility-oracle-dashboard/frontend
npm run verify -- https://hub.thegraph.foundation/reo
```

`reo` is one-shot: it fetches data, writes `output/data.json`, copies the
frontend assets, and renders `output/index.html`. `reo-scheduler` then repeats
that every 5 minutes. **Restart both** — pulling an image does not update a
running container.

### Verify visually, not with curl

An HTTP 200 proves almost nothing here. Real incidents that all returned 200:

- **Completely unstyled page.** `gds.css` and `app.js` 404'd, so the page
  rendered as raw HTML with a giant blue logo.
- **Empty page.** Only one network was configured, and that network's oracle had
  never run, so the roster correctly refused to show anything.
- **Inert page.** The client bundle was missing from the image, so nothing
  hydrated — filters and sorting silently did nothing.

`npm run verify -- <url>` catches all three. It drives a real browser and
asserts the stylesheet is attached, the themed background and brand font are
applied, the roster has rows, a filter click actually changes the table (proving
hydration), and mobile renders cards without horizontal overflow. It writes
screenshots to `verification-shots/` and exits non-zero on failure. **Look at
the screenshots.**

### The URL must work without a trailing slash

`hub.thegraph.foundation/reo` and `.../reo/` must both work. Assets are
referenced relatively (`gds.css`, `app.js`), so without a redirect the browser
resolves them against the domain root and they 404 — leaving the page unstyled.

Caddy needs an explicit redirect *before* the handler, because `handle /reo*`
serves `index.html` directly and never issues the directory redirect itself:

```caddyfile
redir /reo /reo/ 301

handle /reo* {
    root * /usr/share/nginx/html/reo
    uri strip_prefix /reo
    file_server browse
}
```

The old dashboard inlined all its CSS, so it survived this; the current build
depends on external assets and does not.

### Editing the Caddyfile requires restarting Caddy

`infrastructure/caddy/Caddyfile` is bind-mounted as a **single file**. Editors
that write atomically (temp file + rename) change the inode, and the container
keeps serving the old one — `caddy reload` will happily report success while
nothing changes. Confirm the container actually sees the edit:

```bash
docker exec dashboards-caddy grep -n "redir /reo" /etc/caddy/Caddyfile
docker restart dashboards-caddy   # if it does not
```

### Both networks need an RPC endpoint

`.env` must define `RPC_ENDPOINT_MAINNET` as well as `RPC_ENDPOINT_TESTNET`.
Without the mainnet endpoint the generator silently produces one environment,
and since the Sepolia oracle has never posted an update the page renders an
empty state. The public endpoint is sufficient — no key required:

```
RPC_ENDPOINT_MAINNET=https://arb1.arbitrum.io/rpc
```

### Image tags

`docker.yml` publishes `:latest` and `:main` on every push to main, and
`:{version}` for `v*.*.*` git tags. Compose tracks `:latest`. To pin a release,
tag the repo (`git tag v0.4.0 && git push origin v0.4.0`), wait for the workflow,
then set the image in `docker-compose.yml`.

### The scheduler healthcheck

It asserts `output/index.html` was rewritten within the last 15 minutes, which
detects a hung loop rather than just a live process. It deliberately does not
call `scripts/healthcheck.py` — that file is not in the published image, and
referencing it left the container permanently unhealthy while it was working
fine.

### GitHub Actions timing

After merging, `:latest` is not immediately available. Wait for the main-branch
workflow to finish (~1-2 min):

```bash
gh run list --branch main --limit 1   # wait for "completed success"
```

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

- **`generate_dashboard.py`** (~2000 lines) - Data layer: fetches on-chain data, writes JSON
  - `retrieveActiveIndexers()` - Fetches from subgraph with ENS resolution
  - `checkEligibility()` - Three-pass contract interaction
  - `updateStatusChangeDates()` - Compares runs to detect changes
  - `logStatusChanges()` - Appends to cumulative activity log
  - `write_dashboard_data()` - Writes `output/data.json`, the contract with the frontend
  - `render_dashboard()` - Shells out to the Node prerenderer (non-fatal on failure)

- **`frontend/`** - Presentation layer: React + The Graph Design System, prerendered
  - `src/App.jsx` - The page. Two surfaces: indexer self-lookup, then the oracle roster
  - `src/lib/status.js` - Eligibility domain logic (status → GDS variant, grace countdown)
  - `src/lib/data.js` - Reads `output/data.json`; the frontend reads nothing else
  - `scripts/prerender.mjs` - Renders `output/index.html` atomically

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

### Architecture: two halves, one contract

**Python fetches data and writes `output/data.json`. React renders that JSON to
`output/index.html`.** Neither half reaches across the line: the frontend reads
only `data.json`, and Python emits no markup. Freshness comes from regeneration
(~5 min), not from client-side fetching — nothing is fetched in the browser.

The renderer is a self-contained bundle built by `vite build`, so the runtime
image needs a `node` binary but **no `node_modules`**.

### Adding Dashboard Features
1. UI lives in `frontend/src/App.jsx`; build with `bash scripts/build_frontend.sh`
2. Use GDS components from `@graphprotocol/gds-react` — do not hand-roll equivalents
3. Style with GDS Tailwind utilities/tokens; there is no hand-written CSS file
4. If the UI needs a new field, add it in `write_dashboard_data()` first — `data.json`
   is the only channel between the halves

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
