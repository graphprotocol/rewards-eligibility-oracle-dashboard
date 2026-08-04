# Rewards Eligibility Oracle Dashboard

The **Rewards Eligibility Oracle (REO)** dashboard monitors indexer eligibility for rewards based on service quality metrics in [The Graph Protocol](https://thegraph.com).

**Live Dashboard**: https://hub.thegraph.foundation/reo/

## What It Does

The REO links indexer eligibility for rewards to service quality provision. Only indexers meeting performance standards receive rewards.

**Features:**
- 🎯 Real-time eligibility tracking for all active indexers
- 🌍 Multi-environment toggle (compare deployments)
- 📊 Status categories: Active, Grace, Expired, Unqualified
- 🔔 Optional Telegram notifications for status changes
- 🔄 Auto-refreshes every 5 minutes

## Quick Start

```bash
# Clone and setup
git clone https://github.com/graphprotocol/rewards-eligibility-oracle-dashboard.git
cd rewards-eligibility-oracle-dashboard
pip3 install -r requirements.txt
cp env.example .env

# Build the frontend once (needs Node.js >= 20). This compiles the renderer and
# the GDS stylesheet that generate_dashboard.py renders through.
bash scripts/build_frontend.sh

# Edit .env with your API keys and RPC endpoints, then:
python3 generate_dashboard.py
open output/index.html
```

> After deploying, verify visually — an HTTP 200 does not mean the page rendered:
> ```bash
> cd frontend && npm run verify -- https://hub.thegraph.foundation/reo
> ```
> This drives a real browser, asserts styling/data/hydration, saves screenshots to
> `verification-shots/`, and exits non-zero on failure.
>
> The dashboard is written to `output/index.html` (override with `REO_OUTPUT_DIR`).
> Re-run `scripts/build_frontend.sh` only when frontend code changes; day-to-day
> data refreshes just need `python3 generate_dashboard.py`.
> Each environment queries its own chain, so mainnet needs `RPC_ENDPOINT_MAINNET`
> and testnet needs `RPC_ENDPOINT_TESTNET` (see [env.example](env.example)).

## Environments

Contract addresses are resolved dynamically per network from the [GitHub registry](https://github.com/graphprotocol/contracts/blob/main/packages/issuance/addresses.json) (`addresses.json`). The values below reflect the current registry entries:

| Environment | Contract Address | Network |
|-------------|-----------------|---------|
| **mainnet** | `0x8ec2767a9d9ba02b4e09e8ff4fac2e14a340f304` | Arbitrum One (42161) |
| **testnet** | `0x6ba849fbd33257162552578b2a432d30784f2f80` | Arbitrum Sepolia (421614) |

The Sepolia registry exposes several oracle variants (`RewardsEligibilityOracleA/B/Mock`); the auto-pick lands on `A`. To pin an explicit address, set `TESTNET_CONTRACT_ADDRESS` (or `MAINNET_CONTRACT_ADDRESS`) in `.env`.

## Architecture

Two halves, one contract between them:

```
generate_dashboard.py  ->  output/data.json  ->  React (SSG)  ->  output/index.html
```

`generate_dashboard.py` fetches on-chain data and writes JSON; the React frontend in `frontend/`
renders that JSON to static HTML. The frontend reads only `data.json`, and Python emits no markup.

Nothing is fetched in the browser — freshness comes from regenerating every ~5 minutes, so the
page is a snapshot that is never more than one cycle stale. The UI is built on
[The Graph Design System](https://github.com/graphprotocol/gds) (`@graphprotocol/gds-react`).

## Data Sources

- **Network Subgraph**: Active indexers (stakedTokens > 0) — both environments query the Arbitrum One network subgraph, so testnet scores the real mainnet indexer set against the testnet oracle
- **ENS Subgraph**: Indexer ENS names
- **RPC Calls**: Contract state (eligibility, timestamps)
- **GitHub Registry**: Contract addresses ([addresses.json](https://github.com/graphprotocol/contracts/blob/main/packages/issuance/addresses.json))

## Documentation

For AI agents and developers:
- **Architecture and conventions**: [CLAUDE.md](CLAUDE.md)

## Telegram Bot (Optional)

```bash
# Add to .env:
TELEGRAM_BOT_TOKEN=your_bot_token_here

# Run the bot
python3 telegram_bot.py
```

**Commands**: `/start`, `/watch <address>`, `/unwatch <address>`, `/watchlist`, `/status`, `/help`

## License

MIT License - see [LICENSE](LICENSE) file.

---

**Links**:
- [GIP-0079: Indexer Rewards Eligibility Oracle](https://forum.thegraph.com/t/gip-0079-indexer-rewards-eligibility-oracle/6734)
- [GIP-0079 specification](https://github.com/graphprotocol/graph-improvement-proposals/blob/main/gips/0079.md)
- [Council ratification: GGP-0058](https://snapshot.org/#/s:council.graphprotocol.eth/proposal/0x68265745988129067231366a8c56e9e13e32693522dd80930a9cc557eebabd22) (passed 6-0)
- [Eligibility criteria](https://github.com/graphprotocol/rewards-eligibility-oracle/blob/main/ELIGIBILITY_CRITERIA.md#active-eligibility-criteria)
- [Rewards Eligibility Oracle Contract](https://github.com/graphprotocol/rewards-eligibility-oracle)
