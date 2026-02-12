"""
REO Database Module - SQLite-based data storage

Replaces JSON file-based storage with a proper SQLite database for production use.
"""

import sqlite3
import json
import os
from datetime import datetime
from typing import List, Dict, Optional, Any

# Database file path
DB_PATH = os.getenv('REO_DB_PATH', 'reo.db')


def _migrate_network_id_column(cursor: sqlite3.Cursor):
    """
    Migrate existing database to add network_id column if missing.

    Existing indexers will be assigned to 'testnet' network as the default.
    """
    # Check if network_id column exists
    cursor.execute("PRAGMA table_info(indexers)")
    columns = [col[1] for col in cursor.fetchall()]

    if 'network_id' not in columns:
        print("✓ Migrating database: Adding network_id column")
        # Add the column
        cursor.execute("ALTER TABLE indexers ADD COLUMN network_id TEXT DEFAULT 'testnet'")
        # Update existing rows to have testnet as their network
        cursor.execute("UPDATE indexers SET network_id = 'testnet' WHERE network_id IS NULL")
        print("✓ Migration complete: Existing indexers assigned to 'testnet' network")
    else:
        print("✓ database network_id column already exists")


def get_connection() -> sqlite3.Connection:
    """Get a database connection with row factory enabled."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize database schema."""
    conn = get_connection()
    cursor = conn.cursor()

    # Indexers table - stores current state of all indexers
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS indexers (
            address TEXT PRIMARY KEY,
            ens_name TEXT,
            staked_tokens TEXT,
            is_eligible INTEGER,
            eligibility_renewal_time INTEGER,
            status TEXT,
            last_status_change_date INTEGER,
            last_check_time INTEGER,
            network_id TEXT DEFAULT 'testnet'
        )
    """)

    # Migrate existing data to add network_id column if missing
    _migrate_network_id_column(cursor)

    # Status change log - tracks all status transitions
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS status_change_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            indexer_address TEXT,
            old_status TEXT,
            new_status TEXT,
            change_time INTEGER,
            tx_hash TEXT
        )
    """)

    # ENS cache - stores resolved ENS names
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ens_cache (
            address TEXT PRIMARY KEY,
            ens_name TEXT,
            resolved_at INTEGER
        )
    """)

    # Transactions cache - stores last transaction data
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hash TEXT UNIQUE,
            block_number INTEGER,
            block_timestamp INTEGER,
            fetched_at INTEGER
        )
    """)

    # Metadata table - stores sync state and config
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS metadata (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at INTEGER
        )
    """)

    # Sync state
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sync_state (
            platform TEXT PRIMARY KEY,
            last_sync INTEGER,
            items_count INTEGER
        )
    """)

    conn.commit()
    conn.close()

def save_indexers(indexers: List[Dict], network_id: str = 'testnet') -> int:
    """
    Save or update indexers in the database.

    Args:
        indexers: List of indexer dicts from subgraph
        network_id: Network identifier (e.g., 'mainnet', 'testnet')

    Returns:
        Number of indexers saved
    """
    conn = get_connection()
    cursor = conn.cursor()

    count = 0
    now = int(datetime.now().timestamp())

    for indexer in indexers:
        address = indexer.get('id', '').lower()
        ens_name = indexer.get('ens_name')

        # Check if indexer exists (considering network_id)
        cursor.execute("SELECT * FROM indexers WHERE address = ? AND network_id = ?", (address, network_id))
        existing = cursor.fetchone()

        if existing:
            # Update existing indexer
            cursor.execute("""
                UPDATE indexers
                SET ens_name = ?, staked_tokens = ?, last_check_time = ?
                WHERE address = ? AND network_id = ?
            """, (ens_name, indexer.get('staked_tokens'), now, address, network_id))
        else:
            # Insert new indexer
            cursor.execute("""
                INSERT INTO indexers (address, ens_name, staked_tokens, last_check_time, status, network_id)
                VALUES (?, ?, ?, ?, 'unknown', ?)
            """, (address, ens_name, indexer.get('staked_tokens'), now, network_id))
        count += 1

    conn.commit()
    conn.close()
    return count

def get_all_indexers(network_id: Optional[str] = None) -> List[Dict]:
    """
    Get all indexers from the database.

    Args:
        network_id: Filter by network ID, or None for all networks

    Returns:
        List of indexer dicts
    """
    conn = get_connection()
    cursor = conn.cursor()

    if network_id:
        cursor.execute("""
            SELECT
                address as id,
                ens_name,
                staked_tokens,
                is_eligible,
                eligibility_renewal_time,
                status,
                last_status_change_date,
                last_check_time
            FROM indexers
            WHERE network_id = ?
            ORDER BY address
        """, (network_id,))
    else:
        cursor.execute("""
            SELECT
                address as id,
                ens_name,
                staked_tokens,
                is_eligible,
                eligibility_renewal_time,
                status,
                last_status_change_date,
                last_check_time,
                network_id
            FROM indexers
            ORDER BY address
        """)

    indexers = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return indexers

def update_eligibility(address: str, is_eligible: bool, renewal_time: int, status: str, network_id: str = 'testnet'):
    """
    Update eligibility information for an indexer.

    Args:
        address: Indexer address
        is_eligible: Whether indexer is eligible
        renewal_time: Eligibility renewal timestamp
        status: Status string (eligible/grace/ineligible)
        network_id: Network identifier
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Get current status to check if it's changing
    cursor.execute("SELECT status FROM indexers WHERE address = ? AND network_id = ?", (address.lower(), network_id))
    row = cursor.fetchone()

    now = int(datetime.now().timestamp())

    if row:
        old_status = row['status']
        if old_status is not None and old_status != status:
            # Status is changing, update the last_status_change_date
            cursor.execute("""
                UPDATE indexers
                SET is_eligible = ?, eligibility_renewal_time = ?, status = ?, last_status_change_date = ?
                WHERE address = ? AND network_id = ?
            """, (1 if is_eligible else 0, renewal_time, status, now, address.lower(), network_id))
        else:
            # Status unchanged, don't update last_status_change_date
            cursor.execute("""
                UPDATE indexers
                SET is_eligible = ?, eligibility_renewal_time = ?, status = ?
                WHERE address = ? AND network_id = ?
            """, (1 if is_eligible else 0, renewal_time, status, address.lower(), network_id))
    else:
        # New indexer, set the last_status_change_date
        cursor.execute("""
            INSERT OR REPLACE INTO indexers (address, is_eligible, eligibility_renewal_time, status, last_status_change_date, network_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (address.lower(), 1 if is_eligible else 0, renewal_time, status, now, network_id))

    conn.commit()
    conn.close()

def log_status_change(address: str, old_status: str, new_status: str, tx_hash: Optional[str] = None, network_id: str = 'testnet'):
    """
    Log a status change for an indexer.

    Args:
        address: Indexer address
        old_status: Previous status
        new_status: New status
        tx_hash: Transaction hash (optional)
        network_id: Network identifier
    """
    conn = get_connection()
    cursor = conn.cursor()

    now = int(datetime.now().timestamp())
    cursor.execute("""
        INSERT INTO status_change_log (indexer_address, old_status, new_status, change_time, tx_hash)
        VALUES (?, ?, ?, ?, ?)
    """, (address.lower(), old_status, new_status, now, tx_hash))

    conn.commit()
    conn.close()

def get_previous_indexers(network_id: Optional[str] = None) -> List[Dict]:
    """
    Get indexers from the previous run (for comparison).

    Args:
        network_id: Filter by network ID, or None for all networks

    Returns:
        List of indexer dicts
    """
    # For now, we'll use a metadata flag to track "previous" state
    # This can be improved with proper snapshot tables
    return get_all_indexers(network_id)

def update_status_changes(current_indexers: List[Dict], previous_indexers: List[Dict], network_id: str = 'testnet') -> int:
    """
    Compare current and previous indexer states and log changes.

    Args:
        current_indexers: Current indexer data
        previous_indexers: Previous indexer data for comparison
        network_id: Network identifier

    Returns:
        Number of status changes detected
    """
    previous_dict = {i['address'].lower(): i for i in previous_indexers}

    changes_count = 0
    for indexer in current_indexers:
        address = indexer.get('address', indexer.get('id', '')).lower()
        current_status = indexer.get('status')

        if address in previous_dict:
            old_status = previous_dict[address].get('status')
            if old_status != current_status:
                log_status_change(address, old_status, current_status, network_id=network_id)
                changes_count += 1

    return changes_count

def save_ens_cache(ens_mapping: Dict[str, str]) -> int:
    """Save ENS resolutions to cache."""
    conn = get_connection()
    cursor = conn.cursor()

    count = 0
    now = int(datetime.now().timestamp())

    for address, ens_name in ens_mapping.items():
        cursor.execute("""
            INSERT OR REPLACE INTO ens_cache (address, ens_name, resolved_at)
            VALUES (?, ?, ?)
        """, (address.lower(), ens_name, now))
        count += 1

    conn.commit()
    conn.close()
    return count

def load_ens_cache() -> Dict[str, str]:
    """Load ENS cache from database."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT address, ens_name FROM ens_cache")
    rows = cursor.fetchall()

    cache = {row['address']: row['ens_name'] for row in rows}
    conn.close()
    return cache

def save_transaction(tx_data: Dict) -> bool:
    """Save transaction data to cache."""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        now = int(datetime.now().timestamp())
        cursor.execute("""
            INSERT OR REPLACE INTO transactions (hash, block_number, block_timestamp, fetched_at)
            VALUES (?, ?, ?, ?)
        """, (tx_data.get('hash'), tx_data.get('block_number'), tx_data.get('timestamp'), now))

        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error saving transaction: {e}")
        conn.close()
        return False

def get_last_transaction() -> Optional[Dict]:
    """Get the most recent cached transaction."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM transactions ORDER BY fetched_at DESC LIMIT 1")
    row = cursor.fetchone()

    conn.close()

    if row:
        return {
            'hash': row['hash'],
            'block_number': row['block_number'],
            'timestamp': row['block_timestamp']
        }
    return None

def update_sync_state(platform: str, last_sync: int, items_count: int):
    """Update sync state for a platform."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT OR REPLACE INTO sync_state (platform, last_sync, items_count)
        VALUES (?, ?, ?)
    """, (platform, last_sync, items_count))

    conn.commit()
    conn.close()

def set_metadata(key: str, value: str):
    """Set a metadata key-value pair."""
    conn = get_connection()
    cursor = conn.cursor()

    now = int(datetime.now().timestamp())
    cursor.execute("""
        INSERT OR REPLACE INTO metadata (key, value, updated_at)
        VALUES (?, ?, ?)
    """, (key, value, now))

    conn.commit()
    conn.close()

def get_metadata(key: str) -> Optional[str]:
    """Get a metadata value by key."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT value FROM metadata WHERE key = ?", (key,))
    row = cursor.fetchone()

    conn.close()
    return row['value'] if row else None


def get_status_change_history(address: str, network_id: str = 'testnet') -> List[Dict]:
    """
    Get complete status change history for an indexer, ordered by time descending.

    Args:
        address: Indexer address
        network_id: Network identifier (e.g., 'mainnet', 'testnet')

    Returns:
        List of status change dicts with keys: id, old_status, new_status, change_time, tx_hash
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, old_status, new_status, change_time, tx_hash
        FROM status_change_log
        WHERE indexer_address = ?
        ORDER BY change_time DESC
    """, (address.lower(),))

    history = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return history


def calculate_continuous_streak(address: str, current_time: int, network_id: str = 'testnet') -> Dict:
    """
    Calculate continuous eligibility streak for an indexer.

    The streak counts consecutive days where the indexer has been in an eligible status
    (eligible-active or eligible-grace). The streak is calculated by walking backwards
    from the current time through status changes, stopping when hitting an ineligible status.

    Args:
        address: Indexer address
        current_time: Current timestamp (for calculating streak end time)
        network_id: Network identifier

    Returns:
        Dict with keys:
            - days: Number of consecutive eligible days (0 if never eligible)
            - start_time: Timestamp when the current streak started
            - status_history: List of status change entries in the streak
    """
    # Get current status from indexers table
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT status
        FROM indexers
        WHERE address = ? AND network_id = ?
    """, (address.lower(), network_id))

    row = cursor.fetchone()
    conn.close()

    if not row:
        return {"days": 0, "start_time": current_time, "status_history": []}

    current_status = row['status']

    # If currently ineligible, streak is 0
    if current_status not in ('eligible-active', 'eligible-grace'):
        return {"days": 0, "start_time": current_time, "status_history": []}

    # Get status change history (ordered by change_time DESC - most recent first)
    history = get_status_change_history(address, network_id)

    # Walk through history to calculate streak
    # Start from current time and count days until we hit an ineligible status
    streak_end_time = current_time
    streak_start_time = current_time
    status_history_in_streak = []

    # The streak starts from the current time
    # We need to find when this current eligible period started
    # by looking at the most recent status change TO an eligible status

    # Find the most recent change that resulted in the current eligible status
    for entry in history:
        if entry['new_status'] == current_status:
            # This is when the current eligible period started
            streak_start_time = entry['change_time']
            status_history_in_streak.append(entry)
            break

    # Now continue walking back to see if there were previous eligible periods
    # (grace -> active or active -> grace transitions don't break the streak)
    i = len(status_history_in_streak)
    consecutive_eligible = True

    while consecutive_eligible and i < len(history):
        entry = history[i]

        # Check if this was a transition between eligible statuses
        old_eligible = entry['old_status'] in ('eligible-active', 'eligible-grace')
        new_eligible = entry['new_status'] in ('eligible-active', 'eligible-grace')

        if old_eligible and new_eligible:
            # Transition within eligible statuses (e.g., grace <-> active)
            streak_start_time = entry['change_time']
            status_history_in_streak.append(entry)
            i += 1
        elif new_eligible and not old_eligible:
            # Transition from ineligible to eligible - this starts a new eligible period
            # But we're walking backwards, so this would mean the streak started here
            streak_start_time = entry['change_time']
            status_history_in_streak.append(entry)
            i += 1
        else:
            # Hit a transition from eligible to ineligible - streak breaks here
            consecutive_eligible = False

    # Calculate days from streak_start_time to current_time
    if streak_start_time < current_time:
        days_diff = (current_time - streak_start_time) / 86400  # 86400 seconds per day
        days = max(0, int(days_diff))
    else:
        days = 0

    return {
        "days": days,
        "start_time": streak_start_time,
        "status_history": status_history_in_streak
    }


# Initialize database on import
init_db()
