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

# View the generated dashboard — it MUST be served over http
python3 -m http.server 8799 --directory output
open http://localhost:8799/
```

**Do not `open output/index.html`.** The page hydrates from an ES module
(`app.js`), and browsers refuse to load modules from a `file://` origin — CORS
blocks it, so the markup renders but nothing is interactive. Copy buttons do
nothing, filters do nothing, sorting does nothing, and none of it reports an
error anywhere the reader will see. It looks like a working page.

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

# Verify a built or deployed page end-to-end (real browser, real assertions)
cd frontend && npm run build && npm run verify -- <url>
```

`tests/integration/test_frontend_toggle.sh` predates the React rewrite — it
drives `agent-browser` looking for an "Environment:" `<select>` that no longer
exists. `frontend/scripts/verify-deployment.mjs` is the frontend test that is
actually maintained.

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
  - `scripts/verify-deployment.mjs` - The frontend test. Drives a real browser
  - `css/entry.css` - Tailwind/GDS entry point. Nothing hand-written belongs here

- **`.claude/skills/gds/`** - The Graph Design System's own skill, vendored from
  `graphprotocol/gds` (`packages/react/skill`). Read it before any UI change;
  re-copy it when GDS is upgraded so it tracks the installed version

- **`scheduler.py`** - Runs continuously, regenerates dashboard every 5 minutes
  - Reads from `.env` for configuration
  - Calls `generate_dashboard.py()` on schedule
  - Logs generation results

- **`storage.py`** - Round-trips run-to-run state through Vercel Blob
  - A no-op unless `BLOB_READ_WRITE_TOKEN` is set, so local runs are unaffected
  - `pull()`/`push()` for working state; `publish()` for the generated `data.json`

- **`api/refresh.py`** - The hourly cron function (Vercel). Serverless `scheduler.py`
- **`api/render.js`** - Renders the page per request from the published `data.json`

- **`database.py`** - SQLite database operations
  - ENS cache storage and retrieval
  - Transaction data caching
  - Schema initialization

- **`env.example`** - Template for `.env` configuration
  - Required: `ARBISCAN_API_KEY`, `GRAPH_API_KEY`, `RPC_ENDPOINT`
  - Optional: `USE_CACHED_ENS`
  - Vercel only: `BLOB_READ_WRITE_TOKEN`, `CRON_SECRET`
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

**Read `.claude/skills/gds/SKILL.md` before touching any UI.** It is the design
system's own guidance, vendored into this repo, and it is the difference between
using GDS and merely importing it. Its `references/tokens.md` is required
reading — standard Tailwind tokens (`text-sm`, `rounded-md`, `max-w-xl`,
`text-gray-500`) do not exist here; GDS replaces the whole scale.

`.mcp.json` points at the GDS Storybook MCP server. With it connected you can
ask for a component's real prop types and usage examples instead of guessing.

1. UI lives in `frontend/src/App.jsx`; build with `bash scripts/build_frontend.sh`
2. Use GDS components from `@graphprotocol/gds-react` — do not hand-roll
   equivalents. Before writing a control, check the component table in the skill.
   Filters are `Chip.Group`, view switches are `SegmentedControl`, sorting is
   built into `Table`, addresses are `Address`, key/value data is
   `DescriptionList`, links are `Link`, buttons are `Button`. Every one of those
   was hand-rolled here once and every one was worse.
3. Style with GDS Tailwind utilities/tokens; there is no hand-written CSS file.
   `css/entry.css` exists only to register the Tailwind sources.
4. Do not fight a component with `className`. Components already carry their own
   padding, colour and layout — `Card`, notably, pads itself, so an inner `p-6`
   doubles it. `className` is for extrinsic layout only (margin, grid placement,
   max-width), or for CSS props like `max-sm:prop-size-small`.
5. If the UI needs a new field, add it in `write_dashboard_data()` first —
   `data.json` is the only channel between the halves

**There is no separate mobile rendering.** The roster is one `Table` that
scrolls horizontally on small screens, which is what GDS's `Table` is built to
do. It used to be a table *plus* a duplicate card list for `max-md`, which
rendered all 97 rows twice into every page.

**The roster renders `VISIBLE_ROWS` (25) until "View all" is clicked**, so the
criteria and oracle panels below it are reachable. Two consequences: the
prerendered `index.html` contains 25 rows, not all of them (the rest live in the
embedded JSON and appear on expand); and sorting is applied in `Roster` *before*
truncating, then again by `Table.Body`, using the same `COMPARATORS`. Slicing
first would make the table "25 arbitrary rows, then sorted".

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

There are two supported targets. They share the entire pipeline and the entire
UI; they differ only in **when index.html is rendered**.

### Docker Compose (current production)

- Separate infrastructure repository: `dashboard-infrastructure`
- `reo` container: One-shot container that generates dashboard on startup
- `reo-scheduler` container: Runs continuously, regenerates every 5 minutes
- `caddy` container: Web server that serves static HTML files
- Volumes: `reo-output` for generated HTML, `reo-data` for database

Renders **ahead of time**: `render_dashboard()` shells out to
`frontend/scripts/prerender.mjs`, which writes `output/index.html`.

**For detailed deployment instructions**, see `DEPLOYMENT.md`.

### Vercel

Renders **per request**: `api/render.js` runs the same SSR bundle over the
`data.json` that `api/refresh.py` published to Blob, and caches the result for
an hour. The two paths are verified byte-identical for the same data — if you
change one, change the shared code in `frontend/src/lib/document.js` and
`entry-server.jsx`, never one caller alone.

Why per request: a Vercel deployment is immutable, so an `index.html` baked at
build time would freeze the dashboard at deploy time while the hourly cron kept
updating Blob forever. `scripts/build_vercel.sh` fails the build if an
`index.html` appears in `public/`, because it would shadow the render function
and resurrect exactly that bug.

**Setup, once:**

1. Import the repo as a Vercel project. `vercel.json` supplies the build command,
   output directory, cron, and the `/` → `/api/render` rewrite.
2. Create a Blob store and connect it to the project (sets `BLOB_READ_WRITE_TOKEN`).
3. Set `CRON_SECRET` to a random 16+ character string. **`api/refresh.py` fails
   closed** — with no secret set, every request is denied, including the cron's.
4. Set `GRAPH_API_KEY`, `ARBISCAN_API_KEY`, `RPC_ENDPOINT_MAINNET`, and
   `RPC_ENDPOINT_TESTNET`. The mainnet endpoint is not optional — see the warning
   above about the silently-empty page.
5. Deploy, then trigger the first refresh by hand. Until it completes, Blob has
   no `data.json` and the page correctly serves a 503 "Generating" placeholder:

   ```bash
   curl -H "Authorization: Bearer $CRON_SECRET" https://<deployment>/api/refresh
   ```

6. Verify visually, exactly as with Docker — an HTTP 200 still proves nothing:

   ```bash
   cd frontend && npm run verify -- https://<deployment>
   ```

**State lives in Blob, not on disk.** The filesystem is per-invocation, so
`storage.py` pulls the working files before each run and pushes them after.
Without that, every run would see a blank slate and conclude nothing had ever
changed — silently breaking status-change detection, the activity log, streaks,
and the ENS cache. `BLOB_READ_WRITE_TOKEN` is the switch: unset, `storage.py`
does nothing, which is what keeps local runs identical to how they always were.

**Single writer.** One cron writes this state and there are no locks. Do not add
a second writer without replacing `storage.py` with something that has real
atomicity.
