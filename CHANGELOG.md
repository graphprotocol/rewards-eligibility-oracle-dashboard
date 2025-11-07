# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.0.15] - 2025-11-07

### Added
- **Breadcrumb Navigation** - Added navigation bar at the top of the dashboard
  - CSS-styled home icon (no emoji dependency)
  - Format: "Home >> REO Eligibility Dashboard"
  - Links to `../index.html` for easy navigation back to main site
  - Positioned outside the main container frame
  - Matches existing dark theme design (#0C0A1D background, #F8F6FF text, #9CA3AF links)
  - Responsive and mobile-friendly
- **Transaction Hash Tracking** - Added `last_renewed_on_tx` field to indexer metadata
  - Stores the transaction hash when an indexer is confirmed eligible
  - Preserved when indexer transitions to grace or ineligible status
  - Available in `active_indexers.json` metadata section as `transaction_hash`
- **Clickable Transaction Links** - Last Renewed date now links to Arbiscan transaction
  - Eligible indexers with transaction hash: Date links to `https://sepolia.arbiscan.io/tx/{hash}`
  - Maintains hover tooltip with full date/time information
  - Applied to both static HTML and dynamic JavaScript rendering
  - Ineligible indexers continue to show "Never" with no link

### Changed
- **REO Dashboard is now publicly accessible** - Removed authentication requirements
- Dashboard serves static files directly via Nginx for improved performance
- Removed authentication gateway, login page, and email whitelist files
- Updated README.md to remove authentication references
- Preserved GRUMP authentication system in `grump-auth/` directory for future use
- **Significant performance improvement** - Replaced slow RPC block scanning with fast Arbiscan API
  - Transaction fetching now uses Etherscan V2 API (`txlist` endpoint with descending sort)
  - Instant transaction retrieval (< 1 second) vs. previous 50,000 block scan
  - Simplified transaction fetching logic with API-first approach
  - RPC fallback removed in favor of cached JSON fallback

### Removed
- `auth_gate.py` - Authentication gateway (REO-specific)
- `auth_gate.service` - Systemd service file (REO-specific)
- `AUTHENTICATION.md` - Auth documentation (moved to grump-auth/)
- `QUICKSTART_AUTH.md` - Quick start guide (moved to grump-auth/)
- `allowed_people.txt` and `allowed_people.txt.example` - Email whitelist (moved to grump-auth/)
- `login.html` - Login page (moved to grump-auth/)

### Security
- Sensitive files (.py, .env, configuration files) remain protected via Nginx configuration
- JSON data files and dashboard HTML are now publicly accessible as intended

---

## [0.0.14] - 2025-11-04

### Added
- **Authentication System** - Optional email-based OTP authentication for dashboard access control
- New `auth_gate.py` - Lightweight Bottle.py web server that acts as authentication gateway
- New `login.html` - Beautiful, responsive login page matching dashboard design
- New `allowed_people.txt` - Email whitelist supporting exact emails and wildcard domains (e.g., `*@domain.com`)
- **AUTHENTICATION.md** - Comprehensive documentation covering:
  - Architecture and how the system works
  - Installation and configuration steps
  - Production deployment with systemd
  - SMTP/email setup for multiple providers (Gmail, SendGrid, AWS SES, Mailgun)
  - Security features and best practices
  - Monitoring, logging, and troubleshooting
- Email whitelist with wildcard domain support (`*@thegraph.foundation`)
- 6-digit OTP codes with 10-minute expiry
- 7-day session cookies with tamper-proof signatures
- Rate limiting (5 OTP requests per hour per email)
- Beautiful HTML email templates for OTP delivery
- Audit logging of all authentication events
- Health check endpoint (`/health`) for monitoring
- Logout functionality with session invalidation
- Example configuration files: `allowed_people.txt.example`

### Changed
- Updated `README.md` to reference AUTHENTICATION.md in documentation section
- Updated file structure section to include authentication components
- Updated `.gitignore` to protect `allowed_people.txt` (contains authorized emails)
- Updated `env.example` with authentication configuration variables
- Updated `requirements.txt` to include `bottle>=0.12.25` web framework

### Security
- HTTP-only, Secure, SameSite=Strict cookies prevent XSS and CSRF attacks
- HMAC-SHA256 signed session tokens prevent tampering
- In-memory OTP storage (cleared on restart for security)
- Rate limiting prevents OTP spam and brute force attempts
- Email whitelist prevents unauthorized access attempts
- Automatic cleanup of expired OTPs and rate limit entries

### Changed
- **Authentication gateway now uses port 8081** instead of 8080 to avoid conflicts with other applications
- Updated all documentation to reflect new port configuration

### Fixed
- Fixed redirect after successful OTP verification to stay in `/reo/` context (was redirecting to root `/`)
- Fixed static asset serving - images (grt.png), CSS, and JS files now load correctly
- JavaScript fetch URLs now use relative paths for proper proxy routing

### Technical Details
- Zero changes to existing `generate_dashboard.py` or `index.html` (completely non-invasive)
- Auth gateway serves as gatekeeper - checks cookies before serving dashboard
- Supports any SMTP provider (Gmail, SendGrid, AWS SES, Mailgun, etc.)
- Production-ready with systemd service configuration
- Nginx reverse proxy compatible with SSL/TLS support

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

