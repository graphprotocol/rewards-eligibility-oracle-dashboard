# 🍪 Rewards Eligibility Oracle Dashboard

The **Rewards Eligibility Oracle (REO)** dashboard monitors indexer eligibility for rewards based on service quality metrics in [The Graph Protocol](https://thegraph.com).

## Quick Start

```bash
# Clone the repository
git clone https://github.com/graphprotocol/rewards-eligibility-oracle-dashboard.git
cd rewards-eligibility-oracle-dashboard

# Install dependencies
pip3 install -r requirements.txt

# Configure environment
cp env.example .env
# Edit .env with your API keys and RPC endpoints

# Generate the dashboard
python3 generate_dashboard.py

# View the dashboard
open index.html  # macOS
# or open in browser: https://hub.thegraph.org/reo/
```

## What is the Rewards Eligibility Oracle?

The REO links indexer eligibility for rewards to service quality provision. Only indexers meeting performance standards receive rewards, ensuring incentives align with providing value to the network.

**Key Features:**
- 🎯 **Real-time Eligibility Tracking**: Mon indexer eligibility status
- 🌍 **Multi-Environment Support**: Toggle between different deployments
- 📊 **Status Categories**: Active, Grace, Expired, Unqualified
- 🔔 **Telegram Notifications**: Get notified about status changes
- 🔄 **Auto-Refresh**: Dashboard regenerates every 5 minutes via scheduler

## Environments

The dashboard currently supports multiple deployments on Arbitrum Sepolia (testnet):

| Environment | Contract Address | Deployment Block |
|-------------|-----------------|------------------|
| **testnet** (Current) | `0x62c23057...9a99` | 237961353 |
| **testnet_old** (Previous) | `0x4eb1de98...b924` | 237989268 |

Toggle between environments to compare eligibility data across deployments.

## Deployment

The dashboard is deployed to production via Docker Compose:

**Production URL**: https://hub.thegraph.org/reo/

**Version**: v0.1.7 (as of 2026-02-10)

## Source of Truth

**Contract Addresses**: Fetched from [GitHub JSON Registry](https://raw.githubusercontent.com/graphprotocol/contracts/refs/heads/main/packages/issuance/addresses.json)

**Data Sources**:
- **Network Subgraph**: Active indexers (stakedTokens > 0)
- **ENS Subgraph**: Indexer ENS names
- **RPC Calls**: Contract state (eligibility, timestamps)
- **Arbiscan API**: Transaction data

## Documentation

- **Deployment Guide**: [DEPLOYMENT_LESSONS_LEARNED.md](docs/agents/DEPLOYMENT_LESSONS_LEARNED.md)
- **Agent Documentation**: [docs/agents/](docs/agents/)
- **Architecture**: See [Architecture Diagram](#architecture) below

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     User (Browser)                             │
│                https://hub.thegraph.org/reo/               │
└────────────────────────┬────────────────────────────────────┘
                         │
        ┌────────────────┴────────────────┐
        │   Static HTML (Generated)      │
        │   - environmentData (JSON)      │
        │   - Indexer eligibility data    │
        └────────────────┬─────────────────┘
                         │
        ┌────────────────▼─────────────────┐
        │  generate_dashboard.py           │
        │  (Runs every 5 min via scheduler)│
        └────────────────┬─────────────────┘
                         │
    ┌────────────────────┼────────────────────┐
    ▼                    ▼                    ▼
┌─────────┐      ┌──────────┐      ┌──────────┐
│Network  │      │   ENS     │      │   RPC     │
│Subgraph │      │Subgraph  │      │Endpoints │
└─────────┘      └──────────┘      └──────────┘
    │                │                │
    └────────────────┴────────────────┘
             │
    ┌────────▼────────┐
    │  active_indexers │
    │     .json        │
    └─────────────────┘
```

## Contributing

See [docs/agents/](docs/agents/) for development documentation.

## Telegram Bot (Optional)

For real-time notifications about indexer eligibility changes, you can run the Telegram bot:

```bash
# Configure bot token in .env
TELEGRAM_BOT_TOKEN=your_bot_token_here

# Run the bot
python3 telegram_bot.py
```

**Bot Commands**:
- `/start` - Subscribe to notifications
- `/watch <address>` - Watch a specific indexer
- `/unwatch <address>` - Stop watching
- `/watchlist` - Show your watched indexers
- `/status` - Check your subscription status
- `/help` - Get help

## License

MIT License - see [LICENSE](LICENSE) file.

---

**Links**:
- [GIP-0079: Indexer Rewards Eligibility Oracle](https://forum.thegraph.com/t/gip-0079-indexer-rewards-eligibility-oracle/6734)
- [Rewards Eligibility Oracle Contract](https://github.com/graphprotocol/rewards-eligibility-oracle)
- [GitHub Releases](https://github.com/graphprotocol/rewards-eligibility-oracle-dashboard/releases)
