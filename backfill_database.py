#!/usr/bin/env python3
"""
Backfill script - Populate database with current indexer states

This is a one-time script to populate the database with the current state
of all indexers from the JSON files. This enables the streak calculation
to work properly.

Run this after deploying the database changes to initialize the database.
"""

import json
import os
import sys
from datetime import datetime, timezone

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database import save_indexers, init_db, get_connection

def backfill_from_json(json_file: str, network_id: str = 'testnet') -> int:
    """
    Backfill database with indexer data from JSON file.

    Args:
        json_file: Path to active_indexers JSON file
        network_id: Network identifier (testnet, mainnet)

    Returns:
        Number of indexers backfilled
    """
    print(f"Backfilling database from {json_file}...")

    if not os.path.exists(json_file):
        print(f"❌ JSON file not found: {json_file}")
        return 0

    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    indexers = data.get("indexers", [])

    if not indexers:
        print(f"❌ No indexers found in {json_file}")
        return 0

    print(f"Found {len(indexers)} indexers in JSON file")

    # Map JSON indexer format to database format
    # JSON has: address, ens_name, staked_tokens, is_eligible, etc.
    # We need to add status field if not present
    backfill_data = []
    for indexer in indexers:
        backfill_indexer = {
            'id': indexer.get('address', ''),
            'address': indexer.get('address', ''),
            'ens_name': indexer.get('ens_name', ''),
            'staked_tokens': indexer.get('staked_tokens', ''),
        }

        # Map is_eligible to status if not already set
        if 'status' not in indexer:
            is_eligible = indexer.get('is_eligible', False)

            # Determine status from eligibility and dates
            eligible_until = indexer.get('eligible_until', '')
            last_renewed = indexer.get('last_renewed_on', '')

            if is_eligible:
                if eligible_until:
                    # Has eligible_until date, so in grace period
                    backfill_indexer['status'] = 'eligible-grace'
                else:
                    # Eligible with no until date = active
                    backfill_indexer['status'] = 'eligible-active'
            else:
                if last_renewed and last_renewed > 0:
                    # Was eligible once but now isn't
                    backfill_indexer['status'] = 'ineligible-expired'
                else:
                    # Never was eligible
                    backfill_indexer['status'] = 'ineligible-unqualified'
        else:
            backfill_indexer['status'] = indexer.get('status', 'ineligible-unqualified')

        backfill_indexer['is_eligible'] = indexer.get('is_eligible', False)
        backfill_indexer['eligibility_renewal_time'] = indexer.get('eligibility_renewal_time', 0)
        backfill_indexer['last_renewed_on_tx'] = indexer.get('last_renewed_on_tx', '')

        backfill_data.append(backfill_indexer)

    # Save to database
    print(f"Saving {len(backfill_data)} indexers to database...")
    saved_count = save_indexers(backfill_data, network_id=network_id)

    return saved_count


def main():
    """Main backfill function."""
    print("=" * 60)
    print("  DATABASE BACKFILL SCRIPT")
    print("=" * 60)
    print()

    # Initialize database
    print("Initializing database...")
    init_db()

    # Backfill testnet
    testnet_json = 'active_indexers_testnet.json'
    if os.path.exists(testnet_json):
        print("\n📋 Processing testnet...")
        testnet_count = backfill_from_json(testnet_json, 'testnet')
        print(f"✅ Backfilled {testnet_count} testnet indexers")
    else:
        print(f"⚠️  Testnet JSON file not found: {testnet_json}")

    # Backfill mainnet if exists
    mainnet_json = 'active_indexers.json'
    if os.path.exists(mainnet_json):
        print("\n📋 Processing mainnet...")
        mainnet_count = backfill_from_json(mainnet_json, 'mainnet')
        print(f"✅ Backfilled {mainnet_count} mainnet indexers")
    else:
        print(f"⚠️  Mainnet JSON file not found: {mainnet_json}")

    # Verify backfill
    print("\n" + "=" * 60)
    print("  VERIFYING BACKFILL")
    print("=" * 60)

    conn = get_connection()
    cursor = conn.cursor()

    for network in ['testnet', 'mainnet']:
        cursor.execute("SELECT COUNT(*) FROM indexers WHERE network_id = ?", (network,))
        count = cursor.fetchone()[0]
        print(f"  {network_id}: {count} indexers in database")

    conn.close()

    print("\n" + "=" * 60)
    print("✅ BACKFILL COMPLETE")
    print("=" * 60)
    print("\nThe database is now populated with current indexer states.")
    print("Going forward, eligibility checks will update this data automatically.")
    print("Streak calculation will now work correctly!")


if __name__ == "__main__":
    main()
