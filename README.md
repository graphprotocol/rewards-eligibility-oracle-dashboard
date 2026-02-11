# 🍪 Rewards Eligibility Oracle Dashboard

The **Rewards Eligibility Oracle (REO)** dashboard monitors indexer eligibility for rewards based on service quality metrics in [The Graph Protocol](https://thegraph.com).

**Live Dashboard**: https://hub.thegraph.org/reo/

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

# Edit .env with your API keys and RPC endpoints, then:
python3 generate_dashboard.py
open index.html
```

## Environments

| Environment | Contract Address | Deployment Block |
|-------------|-----------------|------------------|
| **testnet** (Current) | `0x62c23057...9a99` | 237961353 |
| **testnet_old** (Previous) | `0x4eb1de98...b924` | 237989268 |

## Data Sources

- **Network Subgraph**: Active indexers (stakedTokens > 0)
- **ENS Subgraph**: Indexer ENS names
- **RPC Calls**: Contract state (eligibility, timestamps)
- **GitHub Registry**: Contract addresses ([addresses.json](https://github.com/graphprotocol/contracts/blob/main/packages/issuance/addresses.json))

## Documentation

For AI agents and developers:
- **Deployment Guide**: [docs/agents/DEPLOYMENT_LESSONS_LEARNED.md](docs/agents/DEPLOYMENT_LESSONS_LEARNED.md)
- **Architecture**: [docs/agents/CLAUDE.md](docs/agents/CLAUDE.md)

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
- [Rewards Eligibility Oracle Contract](https://github.com/graphprotocol/rewards-eligibility-oracle)
