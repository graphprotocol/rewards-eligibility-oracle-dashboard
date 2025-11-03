# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.0.13] - 2025-11-03

### Added
- **Indexer-specific subscriptions** in Telegram bot - watch individual indexers instead of all
- New `/watch <address>` command - subscribe to notifications for specific indexers only
- New `/unwatch <address>` command - remove indexer from watch list
- New `/watchlist` command - view all watched indexers
- Filtered notifications - users with watched indexers only receive updates about those specific indexers
- Empty watch list means receive all notifications (default behavior)
- **Announcement script** (`announce_update.py`) - notify existing subscribers about new features
- Confirmation prompt before sending announcements with success/failure statistics
- **Direct link to GIP-0079 proposal** in help message for easy reference
- **Individual indexer addresses shown in notifications** - see exactly which indexers changed status

### Changed
- Updated subscriber data structure to include `watched_indexers` array
- Telegram notifier now filters status changes based on each subscriber's watch list
- **Notification messages now show specific indexer addresses** with status transitions (e.g., "eligible → grace period")
- Updated bot help text and welcome messages with new commands
- **Clarified messaging: "daily summary message"** instead of "real-time notifications" throughout
- Subscribe/unsubscribe commands now reference "daily summary message" for accuracy
- Watch/unwatch messages updated to reference "daily summary" context
- **Fixed Telegram Markdown formatting** - using single asterisks (*text*) for bold instead of double (**text**)
- **Made section headings bold** throughout bot messages for better readability
- Enhanced `/status` command to show "Daily summary message" in status
- **Clarified `/unsubscribe` functionality** - now explicitly states "Stop receiving all notifications"
- `/unsubscribe` now clears the watched_indexers list for a clean slate on resubscribe
- Improved watch/unwatch command usage messages with full address examples
- Updated README_TelegramBOT.md with:
  - Announcement script usage instructions
  - Watch specific indexers feature documentation
  - Daily summary messaging clarification
  - New command documentation
- Address validation shows full 42-character format in error messages

---

## [0.0.12] - 2025-11-03

### Added
- New "Last Renewed" column in dashboard table showing when each indexer's eligibility was last renewed
- CSS-based hover tooltips for date columns showing full timestamp on hover
- Short date format display (e.g., "2-Nov-2025") with full date/time on hover (e.g., "2-Nov-2025 at 13:31:42 UTC")
- Shows "Never" for indexers that have never been eligible
- Column positioned between "Status" and "Eligible Until" for better readability

### Changed
- Updated table structure to accommodate new column
- Enhanced indexer eligibility tracking with renewal timestamp visibility
- Both "Last Renewed" and "Eligible Until" columns now use short date format with CSS hover tooltips
- Improved page load performance by using CSS tooltips instead of JavaScript

---

## [0.0.11] - 2025-11-03

### Changed
- Renamed environment variable from `QUICK_NODE` to `RPC_ENDPOINT` for provider-agnostic configuration
- Updated all function parameters from `quicknode_url` to `rpc_endpoint` throughout codebase
- Renamed `get_last_transaction_via_quicknode()` to `get_last_transaction_via_rpc()`
- Configuration now supports any Ethereum RPC provider (Alchemy, Infura, QuickNode, Ankr, etc.)
- Updated documentation to reflect provider flexibility
- Updated all example files (`.env.example`, `env.example`) with new variable name

---

## [0.0.10] - 2025-10-29

### Changed
- Simplified Telegram notification message format to a cleaner summary style
- Telegram notifications now limited to once per day to reduce notification frequency
- Removed detailed changes message, sending only one summary message per notification
- Added notification tracking system to prevent duplicate notifications on the same day

---

## [0.0.9] - 2025-10-27

### Fixed
- Fixed Telegram bot notification message to properly display oracle update time by converting Unix timestamp to readable format
- Removed redundant "Oracle Timestamp" field from Telegram notifications

---

## [0.0.8] - 2025-10-22

### Added
- Telegram notifications integration for real-time alerts on oracle updates and status changes
- Subscribe to notifications via Telegram bot link in dashboard footer

### Fixed
- Fixed status column sorting functionality - status column can now be sorted in both ascending and descending order
- Status column now properly sorts by status value (eligible, grace, ineligible) alphabetically
- Other columns maintain status priority grouping while sorting within those groups
- Improved ENS name column sorting - only rows with ENS names are sorted, rows without ENS maintain their original order and are placed at the end (ascending) or beginning (descending)

