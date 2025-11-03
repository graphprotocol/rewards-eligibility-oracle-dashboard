# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.0.12] - 2025-11-03

### Added
- New "Last Renewed" column in dashboard table showing when each indexer's eligibility was last renewed
- Displays `eligibility_renewal_time` in human-readable format (e.g., "16-Nov-2025 at 13:31:42 UTC")
- Shows "Never" for indexers that have never been eligible
- Column positioned between "Status" and "Eligible Until" for better readability

### Changed
- Updated table structure to accommodate new column
- Enhanced indexer eligibility tracking with renewal timestamp visibility

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

