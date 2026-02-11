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


class TestGetStatusChangeHistory:
    """Tests for get_status_change_history function."""

    def test_empty_history(self, sample_address, clean_db):
        """Test that empty history is returned for indexer with no changes."""
        result = get_status_change_history(sample_address(), 'testnet')

        assert result is not None
        assert isinstance(result, list)
        assert len(result) == 0

    def test_single_status_change(self, sample_address, clean_db):
        """Test that single status change is returned correctly."""
        # First, log a status change
        log_status_change(
            sample_address(),
            'ineligible-unqualified',
            'eligible-active',
            tx_hash='0xtx123',
            network_id='testnet'
        )

        result = get_status_change_history(sample_address(), 'testnet')

        assert len(result) == 1
        assert result[0]['old_status'] == 'ineligible-unqualified'
        assert result[0]['new_status'] == 'eligible-active'
        assert result[0]['tx_hash'] == '0xtx123'

    def test_multiple_status_changes(self, sample_address, clean_db):
        """Test that multiple status changes are returned in correct order (newest first)."""
        # Log multiple status changes
        log_status_change(
            sample_address(),
            'eligible-grace',
            'eligible-active',
            tx_hash='0xtx456',
            network_id='testnet'
        )
        log_status_change(
            sample_address(),
            'eligible-active',
            'ineligible-expired',
            tx_hash='0xtx789',
            network_id='testnet'
        )

        result = get_status_change_history(sample_address(), 'testnet')

        assert len(result) == 2
        # Most recent first
        assert result[0]['old_status'] == 'ineligible-expired'
        assert result[0]['new_status'] == 'eligible-active'
        assert result[0]['tx_hash'] == '0xtx456'
        # Second entry
        assert result[1]['old_status'] == 'eligible-active'
        assert result[1]['new_status'] == 'eligible-active'
        assert result[1]['tx_hash'] == '0xtx789'


class TestCalculateContinuousStreak:
    """Tests for calculate_continuous_streak function."""

    def test_no_history_eligible(self, clean_db, sample_address):
        """Test streak calculation for indexer with no history but currently eligible."""
        # Manually set indexer as eligible in database
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO indexers (address, status, network_id)
            VALUES (?, 'eligible-active', 'testnet')
        """, (sample_address(),))
        conn.commit()
        conn.close()

        result = calculate_continuous_streak(sample_address(), current_time(), 'testnet')

        # Should return 0 days since no history
        assert result['days'] == 0
        assert isinstance(result['start_time'], int)
        assert result['status_history'] == []

    def test_no_history_ineligible(self, clean_db, sample_address):
        """Test streak calculation for indexer with no history and currently ineligible."""
        # Manually set indexer as ineligible in database
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO indexers (address, status, network_id)
            VALUES (?, 'ineligible-unqualified', 'testnet')
        """, (sample_address(),))
        conn.commit()
        conn.close()

        result = calculate_continuous_streak(sample_address(), current_time(), 'testnet')

        # Should return 0 days since currently ineligible
        assert result['days'] == 0
        assert result['start_time'] == current_time()
        assert result['status_history'] == []

    def test_single_eligible_period(self, clean_db, sample_address):
        """Test streak calculation for indexer with single eligible period."""
        # Create a status change from 5 days ago to now
        five_days_ago = int(datetime(2025, 2, 11, 7, 0, 0).timestamp())
        one_day_ago = int(datetime(2025, 2, 11, 12, 0, 0).timestamp()

        # Log status changes
        log_status_change(
            sample_address(),
            'ineligible-unqualified',
            'eligible-active',
            tx_hash='0xtx111',
            network_id='testnet',
            change_time=five_days_ago
        )
        log_status_change(
            sample_address(),
            'eligible-active',
            'eligible-grace',
            tx_hash='0xtx222',
            network_id='testnet',
            change_time=one_day_ago
        )

        # Set current status as eligible
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE indexers SET status = ? WHERE address = ?
        """, ('eligible-active', sample_address()))
        conn.commit()
        conn.close()

        result = calculate_continuous_streak(sample_address(), current_time(), 'testnet')

        # Should count days from eligible-grace change (1 day ago)
        assert result['days'] == 1
        assert result['start_time'] == one_day_ago

    def test_multiple_eligible_transitions(self, clean_db, sample_address):
        """Test streak counting through eligible-grace to eligible-active transitions."""
        # Create status changes spanning 3 days
        three_days_ago = int(datetime(2025, 2, 11, 9, 0, 0).timestamp())
        two_days_ago = int(datetime(2025, 2, 11, 10, 0, 0).timestamp())
        one_day_ago = int(datetime(2025, 2, 11, 11, 0, 0).timestamp()

        # Log status changes
        log_status_change(
            sample_address(),
            'ineligible-unqualified',
            'eligible-active',
            tx_hash='0xtx111',
            network_id='testnet',
            change_time=three_days_ago
        )
        log_status_change(
            sample_address(),
            'eligible-active',
            'eligible-grace',
            tx_hash='0xtx222',
            network_id='testnet',
            change_time=two_days_ago
        )
        log_status_change(
            sample_address(),
            'eligible-grace',
            'eligible-active',
            tx_hash='0xtx333',
            network_id='testnet',
            change_time=one_day_ago
        )

        # Set current status as eligible
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE indexers SET status = ? WHERE address = ?
        """, ('eligible-active', sample_address()))
        conn.commit()
        conn.close()

        result = calculate_continuous_streak(sample_address(), current_time(), 'testnet')

        # Should count all 3 days as continuous streak (grace->active->grace transitions don't break streak)
        assert result['days'] == 3
        assert result['start_time'] == three_days_ago

    def test_streak_resets_on_ineligible(self, clean_db, sample_address):
        """Test that streak resets to 0 when hitting ineligible status."""
        # Create a status changes with an ineligible period
        five_days_ago = int(datetime(2025, 2, 11, 9, 0, 0).timestamp()
        three_days_ago = int(datetime(2025, 2, 11, 8, 0, 0).timestamp()

        # Log status changes
        log_status_change(
            sample_address(),
            'eligible-active',
            'ineligible-expired',
            tx_hash='0xtx999',
            network_id='testnet',
            change_time=five_days_ago
        )
        log_status_change(
            sample_address(),
            'ineligible-expired',
            'eligible-grace',
            tx_hash='0xtx888',
            network_id='testnet',
            change_time=three_days_ago
        )

        # Set current status as grace
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE indexers SET status = ? WHERE address = ?
        """, ('eligible-grace', sample_address()))
        conn.commit()
        conn.close()

        result = calculate_continuous_streak(sample_address(), current_time(), 'testnet')

        # Should count only 2 days (expired->grace transition broke streak, then grace->eligible continues it)
        assert result['days'] == 2
        assert result['start_time'] == five_days_ago


class TestIntegration:
    """Integration tests for streak calculation."""

    def test_full_workflow(self, clean_db, sample_address):
        """Test the full workflow: log changes, then calculate streak."""
        # Simulate a real workflow:
        # 1. Indexer becomes eligible (5 days ago)
        # 2. Transitions to grace (1 day ago)
        # 3. Then calculate streak

        four_days_ago = int(datetime(2025, 2, 11, 8, 0, 0).timestamp()

        # Log status changes
        log_status_change(
            sample_address(),
            'ineligible-unqualified',
            'eligible-active',
            tx_hash='0xtx111',
            network_id='testnet',
            change_time=four_days_ago
        )
        log_status_change(
            sample_address(),
            'eligible-active',
            'eligible-grace',
            tx_hash='0xtx222',
            network_id='testnet',
            change_time=int(datetime(2025, 2, 11, 9, 0, 0).timestamp())
        )

        # Set current status as eligible
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE indexers SET status = ? WHERE address = ?
        """, ('eligible-active', sample_address()))
        conn.commit()
        conn.close()

        result = calculate_continuous_streak(sample_address(), int(datetime(2025, 2, 11, 12, 0, 0).timestamp()), 'testnet')

        # Should count 1 day of continuous eligibility
        assert result['days'] == 1
        assert len(result['status_history']) >= 1


if __name__ == "__main__":
    pytest.main([__file__], verbosity=2)
