# 🍪 Rewards Eligibility Oracle Dashboard

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

# Edit .env with your API keys and RPC endpoints, then:
python3 generate_dashboard.py
open index.html
```

## Environments

| Environment | Contract Address | Network |
|-------------|-----------------|---------|
| **mainnet** | `0x8ec2767a9d9ba02b4e09e8ff4fac2e14a340f304` | Arbitrum One (42161) |
| **testnet** | `0x62c2305739cc75f19a3a6d52387ceb3690d99a99` | Arbitrum Sepolia (421614) |

## Data Sources

- **Network Subgraph**: Active indexers (stakedTokens > 0)
- **ENS Subgraph**: Indexer ENS names
- **RPC Calls**: Contract state (eligibility, timestamps)
- **GitHub Registry**: Contract addresses ([addresses.json](https://github.com/graphprotocol/contracts/blob/main/packages/issuance/addresses.json))

## Documentation

For AI agents and developers:
- **Deployment Guide**: [docs/agents/DEPLOYMENT.md](docs/agents/DEPLOYMENT.md)
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
