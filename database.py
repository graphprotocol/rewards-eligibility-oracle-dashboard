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
            last_check_time INTEGER
        )
    """)

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

def save_indexers(indexers: List[Dict]) -> int:
    """Save or update indexers in the database."""
    conn = get_connection()
    cursor = conn.cursor()

    count = 0
    now = int(datetime.now().timestamp())

    for indexer in indexers:
        address = indexer.get('id', '').lower()
        ens_name = indexer.get('ens_name')

        # Check if indexer exists
        cursor.execute("SELECT * FROM indexers WHERE address = ?", (address,))
        existing = cursor.fetchone()

        if existing:
            # Update existing indexer
            cursor.execute("""
                UPDATE indexers
                SET ens_name = ?, staked_tokens = ?, last_check_time = ?
                WHERE address = ?
            """, (ens_name, indexer.get('staked_tokens'), now, address))
        else:
            # Insert new indexer
            cursor.execute("""
                INSERT INTO indexers (address, ens_name, staked_tokens, last_check_time, status)
                VALUES (?, ?, ?, ?, 'unknown')
            """, (address, ens_name, indexer.get('staked_tokens'), now))
        count += 1

    conn.commit()
    conn.close()
    return count

def get_all_indexers() -> List[Dict]:
    """Get all indexers from the database."""
    conn = get_connection()
    cursor = conn.cursor()

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
        ORDER BY address
    """)

    indexers = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return indexers

def update_eligibility(address: str, is_eligible: bool, renewal_time: int, status: str):
    """Update eligibility information for an indexer."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE indexers
        SET is_eligible = ?, eligibility_renewal_time = ?, status = ?
        WHERE address = ?
    """, (1 if is_eligible else 0, renewal_time, status, address.lower()))

    conn.commit()
    conn.close()

def log_status_change(address: str, old_status: str, new_status: str, tx_hash: Optional[str] = None):
    """Log a status change for an indexer."""
    conn = get_connection()
    cursor = conn.cursor()

    now = int(datetime.now().timestamp())
    cursor.execute("""
        INSERT INTO status_change_log (indexer_address, old_status, new_status, change_time, tx_hash)
        VALUES (?, ?, ?, ?, ?)
    """, (address.lower(), old_status, new_status, now, tx_hash))

    conn.commit()
    conn.close()

def get_previous_indexers() -> List[Dict]:
    """Get indexers from the previous run (for comparison)."""
    # For now, we'll use a metadata flag to track "previous" state
    # This can be improved with proper snapshot tables
    return get_all_indexers()

def update_status_changes(current_indexers: List[Dict], previous_indexers: List[Dict]) -> int:
    """Compare current and previous indexer states and log changes."""
    previous_dict = {i['address'].lower(): i for i in previous_indexers}

    changes_count = 0
    for indexer in current_indexers:
        address = indexer.get('address', indexer.get('id', '')).lower()
        current_status = indexer.get('status')

        if address in previous_dict:
            old_status = previous_dict[address].get('status')
            if old_status != current_status:
                log_status_change(address, old_status, current_status)
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

# Initialize database on import
init_db()
