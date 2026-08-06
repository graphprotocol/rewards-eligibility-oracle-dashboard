"""
Unit tests for continuous eligibility streak calculation in database.py
"""

import pytest
import sys
import os

# Add parent directory to path to allow imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database import (
    get_status_change_history,
    calculate_continuous_streak,
    init_db,
    get_connection,
    log_status_change,
)
from datetime import datetime, timezone


@pytest.fixture
def sample_address():
    """Return a sample indexer address."""
    return "0x1234567890abcdef1234567890abcdef12"


@pytest.fixture
def current_time():
    """Return current timestamp for testing."""
    return int(datetime(2025, 2, 11, 12, 0, 0).timestamp())


def _log_status_change_at(address, old_status, new_status, change_time, tx_hash=None):
    """
    Like database.log_status_change(), but lets the caller control change_time
    directly (the real function always stamps datetime.now()). Mirrors its
    INSERT exactly so tests can construct specific historical timelines.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO status_change_log (indexer_address, old_status, new_status, change_time, tx_hash)
        VALUES (?, ?, ?, ?, ?)
    """, (address.lower(), old_status, new_status, change_time, tx_hash))
    conn.commit()
    conn.close()


class TestGetStatusChangeHistory:
    """Tests for get_status_change_history function."""

    def test_empty_history(self, sample_address, clean_db):
        """Test that empty history is returned for indexer with no changes."""
        result = get_status_change_history(sample_address, 'testnet')

        assert result is not None
        assert isinstance(result, list)
        assert len(result) == 0

    def test_single_status_change(self, sample_address, clean_db):
        """Test that single status change is returned correctly."""
        # First, log a status change
        log_status_change(
            sample_address,
            'ineligible-unqualified',
            'eligible-active',
            tx_hash='0xtx123',
            network_id='testnet'
        )

        result = get_status_change_history(sample_address, 'testnet')

        assert len(result) == 1
        assert result[0]['old_status'] == 'ineligible-unqualified'
        assert result[0]['new_status'] == 'eligible-active'
        assert result[0]['tx_hash'] == '0xtx123'

    def test_multiple_status_changes(self, sample_address, clean_db):
        """Test that multiple status changes are returned in correct order (newest first)."""
        # Log multiple status changes with explicit, ordered timestamps
        _log_status_change_at(
            sample_address, 'eligible-grace', 'eligible-active',
            change_time=1000, tx_hash='0xtx456',
        )
        _log_status_change_at(
            sample_address, 'eligible-active', 'ineligible-expired',
            change_time=2000, tx_hash='0xtx789',
        )

        result = get_status_change_history(sample_address, 'testnet')

        assert len(result) == 2
        # Most recent first
        assert result[0]['old_status'] == 'eligible-active'
        assert result[0]['new_status'] == 'ineligible-expired'
        assert result[0]['tx_hash'] == '0xtx789'
        # Second entry
        assert result[1]['old_status'] == 'eligible-grace'
        assert result[1]['new_status'] == 'eligible-active'
        assert result[1]['tx_hash'] == '0xtx456'


class TestCalculateContinuousStreak:
    """Tests for calculate_continuous_streak function."""

    def test_no_history_eligible(self, clean_db, sample_address, current_time):
        """Test streak calculation for indexer with no history but currently eligible."""
        # Manually set indexer as eligible in database
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO indexers (address, status, network_id)
            VALUES (?, 'eligible-active', 'testnet')
        """, (sample_address,))
        conn.commit()
        conn.close()

        result = calculate_continuous_streak(sample_address, current_time, 'testnet')

        # Should return 0 days since no history
        assert result['days'] == 0
        assert isinstance(result['start_time'], int)
        assert result['status_history'] == []

    def test_no_history_ineligible(self, clean_db, sample_address, current_time):
        """Test streak calculation for indexer with no history and currently ineligible."""
        # Manually set indexer as ineligible in database
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO indexers (address, status, network_id)
            VALUES (?, 'ineligible-unqualified', 'testnet')
        """, (sample_address,))
        conn.commit()
        conn.close()

        result = calculate_continuous_streak(sample_address, current_time, 'testnet')

        # Should return 0 days since currently ineligible
        assert result['days'] == 0
        assert result['start_time'] == current_time
        assert result['status_history'] == []

    def test_single_eligible_period(self, clean_db, sample_address, current_time):
        """Test streak calculation for indexer with single eligible period."""
        # Create a status change from 5 days ago to 1 day ago
        five_days_ago = current_time - 5 * 86400
        one_day_ago = current_time - 1 * 86400

        # Log status changes
        _log_status_change_at(
            sample_address, 'ineligible-unqualified', 'eligible-active',
            change_time=five_days_ago, tx_hash='0xtx111',
        )
        _log_status_change_at(
            sample_address, 'eligible-active', 'eligible-grace',
            change_time=one_day_ago, tx_hash='0xtx222',
        )

        # Set current status to match the last logged transition (grace)
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO indexers (address, status, network_id) VALUES (?, ?, 'testnet')
        """, (sample_address, 'eligible-grace'))
        conn.commit()
        conn.close()

        result = calculate_continuous_streak(sample_address, current_time, 'testnet')

        # Continuous streak runs from when it first became eligible (5 days ago);
        # the later active->grace transition doesn't break it
        assert result['days'] == 5
        assert result['start_time'] == five_days_ago

    def test_multiple_eligible_transitions(self, clean_db, sample_address, current_time):
        """Test streak counting through eligible-grace to eligible-active transitions."""
        # Create status changes spanning 3 days
        three_days_ago = current_time - 3 * 86400
        two_days_ago = current_time - 2 * 86400
        one_day_ago = current_time - 1 * 86400

        # Log status changes
        _log_status_change_at(
            sample_address, 'ineligible-unqualified', 'eligible-active',
            change_time=three_days_ago, tx_hash='0xtx111',
        )
        _log_status_change_at(
            sample_address, 'eligible-active', 'eligible-grace',
            change_time=two_days_ago, tx_hash='0xtx222',
        )
        _log_status_change_at(
            sample_address, 'eligible-grace', 'eligible-active',
            change_time=one_day_ago, tx_hash='0xtx333',
        )

        # Set current status to match the last logged transition (active)
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO indexers (address, status, network_id) VALUES (?, ?, 'testnet')
        """, (sample_address, 'eligible-active'))
        conn.commit()
        conn.close()

        result = calculate_continuous_streak(sample_address, current_time, 'testnet')

        # Should count all 3 days as continuous streak (grace->active->grace transitions don't break streak)
        assert result['days'] == 3
        assert result['start_time'] == three_days_ago

    def test_streak_resets_on_ineligible(self, clean_db, sample_address, current_time):
        """Test that a prior ineligible period doesn't extend the current streak."""
        # Create a status changes with an ineligible period
        five_days_ago = current_time - 5 * 86400
        three_days_ago = current_time - 3 * 86400

        # Log status changes
        _log_status_change_at(
            sample_address, 'eligible-active', 'ineligible-expired',
            change_time=five_days_ago, tx_hash='0xtx999',
        )
        _log_status_change_at(
            sample_address, 'ineligible-expired', 'eligible-grace',
            change_time=three_days_ago, tx_hash='0xtx888',
        )

        # Set current status to match the last logged transition (grace)
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO indexers (address, status, network_id) VALUES (?, ?, 'testnet')
        """, (sample_address, 'eligible-grace'))
        conn.commit()
        conn.close()

        result = calculate_continuous_streak(sample_address, current_time, 'testnet')

        # Should count only since re-becoming eligible (3 days), not back through
        # the ineligible-expired period
        assert result['days'] == 3
        assert result['start_time'] == three_days_ago


class TestIntegration:
    """Integration tests for streak calculation."""

    def test_full_workflow(self, clean_db, sample_address, current_time):
        """Test the full workflow: log changes, then calculate streak."""
        # Simulate a real workflow:
        # 1. Indexer becomes eligible (4 days ago)
        # 2. Transitions to grace (1 day ago)
        # 3. Then calculate streak

        four_days_ago = current_time - 4 * 86400
        one_day_ago = current_time - 1 * 86400

        # Log status changes
        _log_status_change_at(
            sample_address, 'ineligible-unqualified', 'eligible-active',
            change_time=four_days_ago, tx_hash='0xtx111',
        )
        _log_status_change_at(
            sample_address, 'eligible-active', 'eligible-grace',
            change_time=one_day_ago, tx_hash='0xtx222',
        )

        # Set current status to match the last logged transition (grace)
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO indexers (address, status, network_id) VALUES (?, ?, 'testnet')
        """, (sample_address, 'eligible-grace'))
        conn.commit()
        conn.close()

        result = calculate_continuous_streak(sample_address, current_time, 'testnet')

        # Should count 4 days of continuous eligibility (active->grace doesn't break it)
        assert result['days'] == 4
        assert len(result['status_history']) >= 1


if __name__ == "__main__":
    pytest.main([__file__], verbosity=2)
