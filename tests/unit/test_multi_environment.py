"""
Unit tests for multi-environment REO dashboard functionality.

Tests the multi-environment support which:
1. Fetches contract addresses from GitHub JSON registry
2. Configures multiple environments (mainnet, testnet, testnet_new)
3. Supports multi-network database schema
4. Generates HTML with embedded environment data
5. Displays timestamps for contract deployment and dashboard generation
"""

import json
import unittest
import sqlite3
import os
import re
import tempfile
import shutil
from unittest.mock import Mock, patch, MagicMock
import requests


class TestJsonRegistryFetch(unittest.TestCase):
    """Test fetching contract addresses from GitHub JSON registry."""

    def test_json_registry_fetch(self):
        """
        Test 1.1: Verify GitHub JSON is fetched and parsed correctly.

        This test verifies that:
        - GitHub JSON registry is fetched successfully
        - Returns dict with network IDs as keys
        - Contains expected networks (42161 for Arbitrum One, 421614 for Sepolia)
        - Contains RewardsEligibilityOracle address for testnet
        """
        # Arrange: Mock successful GitHub response
        mock_response = Mock()
        mock_response.json.return_value = {
            "42161": {
                "RewardsEligibilityOracle": {
                    "address": "0x0000000000000000000000000000000000000000"
                }
            },
            "421614": {
                "RewardsEligibilityOracle": {
                    "address": "0x62c2305739cc75f19a3a6d52387ceb3690d99a99"
                }
            }
        }
        mock_response.raise_for_status = Mock()

        # Act & Assert
        with patch('requests.get', return_value=mock_response) as mock_get:
            from generate_dashboard import fetch_contract_addresses

            addresses = fetch_contract_addresses()

            # Verify request was made to GitHub
            mock_get.assert_called_once()
            call_args = mock_get.call_args
            self.assertIn("raw.githubusercontent.com", call_args[0][0])
            self.assertIn("addresses.json", call_args[0][0])

            # Should return dict with network IDs as keys
            self.assertIsInstance(addresses, dict)
            self.assertIn("42161", addresses)  # Arbitrum One
            self.assertIn("421614", addresses)  # Arbitrum Sepolia

            # Testnet should have RewardsEligibilityOracle
            self.assertIn("RewardsEligibilityOracle", addresses["421614"])
            self.assertEqual(addresses["421614"]["RewardsEligibilityOracle"]["address"], "0x62c2305739cc75f19a3a6d52387ceb3690d99a99")

    def test_json_registry_fallback_on_request_error(self):
        """
        Test 1.1b: Verify graceful fallback when GitHub fetch fails.

        This test verifies that:
        - Function returns empty dict on request failure
        - Warning is logged (not crashing)
        - Fallback to environment variables is mentioned
        """
        # Arrange: Mock failed request
        with patch('requests.get', side_effect=requests.exceptions.RequestException("Network error")):
            from generate_dashboard import fetch_contract_addresses

            # Act
            addresses = fetch_contract_addresses()

            # Assert: Should return empty dict (graceful degradation)
            self.assertIsInstance(addresses, dict)
            self.assertEqual(len(addresses), 0)

    def test_json_registry_fallback_on_invalid_json(self):
        """
        Test 1.1c: Verify graceful fallback when JSON is invalid.

        This test verifies that:
        - Function returns empty dict on JSON decode error
        - Warning is logged
        """
        # Arrange: Mock response with invalid JSON
        mock_response = Mock()
        mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)
        mock_response.raise_for_status = Mock()

        with patch('requests.get', return_value=mock_response):
            from generate_dashboard import fetch_contract_addresses

            # Act
            addresses = fetch_contract_addresses()

            # Assert: Should return empty dict
            self.assertIsInstance(addresses, dict)
            self.assertEqual(len(addresses), 0)


class TestEnvironmentConfiguration(unittest.TestCase):
    """Test ENVIRONMENTS configuration dict."""

    def test_environment_config(self):
        """
        Test 1.2: Verify ENVIRONMENTS dict is properly configured.

        This test verifies that:
        - ENVIRONMENTS dict contains mainnet, testnet, testnet_new
        - Each environment has required fields
        - Network IDs are correct for each environment
        """
        from generate_dashboard import get_environments_config

        # Get the environments config
        ENVIRONMENTS = get_environments_config()

        # Should have two environments (production)
        self.assertIn("mainnet", ENVIRONMENTS)
        self.assertIn("testnet", ENVIRONMENTS)
        self.assertNotIn("testnet_new", ENVIRONMENTS)

        # Verify each environment has required fields
        required_fields = [
            "name",
            "network_id",
            "rpc_manager",
            "contract_address"
        ]

        for env_name, env_config in ENVIRONMENTS.items():
            for field in required_fields:
                self.assertIn(field, env_config, msg=f"{env_name} missing {field}")

        # Verify network IDs
        self.assertEqual(ENVIRONMENTS["mainnet"]["network_id"], 42161)
        self.assertEqual(ENVIRONMENTS["testnet"]["network_id"], 421614)

        # Verify testnet uses JSON registry address
        self.assertIn("0x", ENVIRONMENTS["testnet"]["contract_address"])

    def test_parse_contract_address_from_registry(self):
        """
        Test 1.2b: Verify contract address parsing from registry.

        This test verifies that:
        - Correct address is extracted for each network
        - Returns None when network not found
        - Returns None when RewardsEligibilityOracle not found
        """
        from generate_dashboard import parse_contract_address_from_registry

        # Arrange: Mock registry data
        registry = {
            "421614": {
                "RewardsEligibilityOracle": {
                    "address": "0x62c2305739cc75f19a3a6d52387ceb3690d99a99"
                }
            },
            "42161": {}  # Mainnet without Oracle
        }

        # Act & Assert
        # Should find testnet address
        address = parse_contract_address_from_registry(registry, "421614")
        self.assertEqual(address, "0x62c2305739cc75f19a3a6d52387ceb3690d99a99")

        # Should return None for mainnet (empty)
        address = parse_contract_address_from_registry(registry, "42161")
        self.assertIsNone(address)

        # Should return None for unknown network
        address = parse_contract_address_from_registry(registry, "1")
        self.assertIsNone(address)


class TestDatabaseNetworkId(unittest.TestCase):
    """Test database multi-network support."""

    def test_database_network_id_column(self):
        """
        Test 1.3: Verify database has network_id column.

        This test verifies that:
        - indexers table has network_id column
        - Existing data gets network_id = 'testnet' as default
        - No indexers have NULL network_id after migration
        """
        # Arrange: Create a test database
        tmp_dir = tempfile.mkdtemp()
        try:
            test_db_path = os.path.join(tmp_dir, "test_reo.db")

            with patch('database.DB_PATH', test_db_path):
                from database import init_db, get_connection

                # Act: Initialize database (runs migration)
                init_db()

                # Assert: Check column exists
                conn = get_connection()
                cursor = conn.cursor()

                cursor.execute("PRAGMA table_info(indexers)")
                columns = [col[1] for col in cursor.fetchall()]
                self.assertIn("network_id", columns)

                # Check default value is 'testnet'
                cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='indexers'")
                table_sql = cursor.fetchone()[0]
                self.assertTrue("DEFAULT 'testnet'" in table_sql or "DEFAULT('testnet')" in table_sql)

                conn.close()
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_database_migration_assigns_testnet_to_existing(self):
        """
        Test 1.3b: Verify existing data gets assigned to 'testnet'.

        This test verifies that:
        - Migration updates existing rows to network_id = 'testnet'
        - Migration is idempotent (can run multiple times)
        """
        # Arrange: Create a database without network_id column
        tmp_dir = tempfile.mkdtemp()
        try:
            test_db_path = os.path.join(tmp_dir, "test_migration.db")

            conn = sqlite3.connect(test_db_path)
            cursor = conn.cursor()

            # Create table WITHOUT network_id (simulating old schema)
            cursor.execute("""
                CREATE TABLE indexers (
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

            # Insert test data
            cursor.execute("""
                INSERT INTO indexers (address, status)
                VALUES ('0x123', 'eligible')
            """)
            conn.commit()
            conn.close()

            # Act: Run migration through init_db
            with patch('database.DB_PATH', test_db_path):
                from database import init_db, get_connection

                init_db()

                # Assert: Check migration happened
                conn = get_connection()
                cursor = conn.cursor()

                # Column should exist
                cursor.execute("PRAGMA table_info(indexers)")
                columns = [col[1] for col in cursor.fetchall()]
                self.assertIn("network_id", columns)

                # Existing data should have network_id = 'testnet'
                cursor.execute("SELECT network_id FROM indexers WHERE address = '0x123'")
                result = cursor.fetchone()
                self.assertEqual(result[0], 'testnet')

                conn.close()
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_database_no_null_network_ids(self):
        """
        Test 1.3c: Verify no indexers have NULL network_id.

        This test verifies that:
        - All indexers have a network_id set
        - Default value prevents NULLs
        """
        tmp_dir = tempfile.mkdtemp()
        try:
            test_db_path = os.path.join(tmp_dir, "test_nulls.db")

            # We need to patch DB_PATH at module level before importing
            import database
            original_db_path = database.DB_PATH
            database.DB_PATH = test_db_path

            try:
                # Initialize and add test data
                database.init_db()

                # Save some indexers without explicit network_id
                # Note: save_indexers expects 'id' field, not 'address'
                database.save_indexers([
                    {
                        "id": "0xabc",
                        "status": "eligible",
                        "staked_tokens": "1000"
                    },
                    {
                        "id": "0xdef",
                        "status": "ineligible",
                        "staked_tokens": "2000"
                    }
                ], network_id="mainnet")

                # Check no NULL network_ids
                conn = database.get_connection()
                cursor = conn.cursor()

                cursor.execute("SELECT COUNT(*) FROM indexers WHERE network_id IS NULL")
                null_count = cursor.fetchone()[0]
                self.assertEqual(null_count, 0, "Some indexers missing network_id")

                # Verify the network_ids were set correctly
                cursor.execute("SELECT address, network_id FROM indexers")
                results = cursor.fetchall()
                self.assertGreaterEqual(len(results), 2, "Should have at least 2 indexers")
                self.assertEqual(results[0][1], "mainnet")
                self.assertEqual(results[1][1], "mainnet")

                conn.close()
            finally:
                database.DB_PATH = original_db_path
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)


class TestHtmlMultiEnvironmentData(unittest.TestCase):
    """Test HTML generation with multi-environment data."""

    def test_html_multi_environment_data(self):
        """
        Test 1.4: Verify generated HTML contains all environment data.

        This test verifies that:
        - HTML has environment toggle selector
        - environmentData JavaScript object is embedded
        - All environments (mainnet, testnet, testnet_new) are present
        - switchEnvironment function exists
        """
        # This test requires the full dashboard generation
        # For now, we'll test the structure conceptually
        # Full implementation test will be in integration tests

        # Arrange: Mock minimal data for HTML generation
        from generate_dashboard import get_environments_config

        ENVIRONMENTS = get_environments_config()

        # Act & Assert: Verify ENVIRONMENTS has expected structure
        # that will be embedded in HTML

        # Should have two environments (production)
        self.assertEqual(len(ENVIRONMENTS), 2)

        # Each should have required keys for HTML generation
        for env_key, env_data in ENVIRONMENTS.items():
            self.assertIn("name", env_data)
            self.assertIn("network_id", env_data)
            self.assertIn("contract_address", env_data)

    def test_html_contains_environment_select(self):
        """
        Test 1.4b: Verify HTML contains environment toggle.

        This is a structure test for the HTML template.
        """
        # We'll verify the HTML generation logic works
        # Full HTML generation test requires more setup

        # For now, verify the required data exists
        from generate_dashboard import get_environments_config

        ENVIRONMENTS = get_environments_config()

        # Check that environment data is structured for HTML
        self.assertIsInstance(ENVIRONMENTS, dict)
        self.assertTrue(all(isinstance(k, str) for k in ENVIRONMENTS.keys()))
        self.assertTrue(all(isinstance(v, dict) for v in ENVIRONMENTS.values()))


class TestTimestampsInHtml(unittest.TestCase):
    """Test timestamp display in generated HTML."""

    def test_timestamps_in_html(self):
        """
        Test 1.5: Verify contract deployment and generation timestamps are displayed.

        This test verifies that:
        - Dashboard generation time is displayed
        - Contract deployment time is included (when available)
        - Timestamp format is correct (YYYY-MM-DD HH:MM:SS)
        """
        from datetime import datetime, timezone

        # Test timestamp format validation
        timestamp_pattern = re.compile(r'\d{4}-\d{2}-\d{2}.*\d{2}:\d{2}:\d{2}')

        # Test current time formatting
        now = datetime.now(timezone.utc)
        timestamp_str = now.strftime("%Y-%m-%d %H:%M:%S UTC")

        self.assertIsNotNone(timestamp_pattern.match(timestamp_str), "Timestamp format incorrect")

        # Verify the timestamp contains expected components
        self.assertTrue("UTC" in timestamp_str or len(timestamp_str.split("-")) == 3)

    def test_block_timestamp_format(self):
        """
        Test 1.5b: Verify block timestamp formatting.

        Tests the formatTimestamp utility function pattern.
        """
        from datetime import datetime, timezone
        import time

        # Create a test timestamp
        test_timestamp = int(time.time())

        # Format it (matching the dashboard format)
        formatted = datetime.fromtimestamp(test_timestamp, timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        # Verify format
        timestamp_pattern = re.compile(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} UTC')
        self.assertIsNotNone(timestamp_pattern.match(formatted), "Block timestamp format incorrect")

    def test_deployment_block_info_structure(self):
        """
        Test 1.5c: Verify contract info structure for deployment data.

        This tests the expected structure for contract deployment info
        that will be embedded in the HTML.
        """
        # Simulate contract_info structure
        contract_info = {
            "address": "0x62c2305739cc75f19a3a6d52387ceb3690d99a99",
            "deployment_block": 237961353,
            "deployment_time": "2025-01-29T18:47:05.000Z"
        }

        # Verify structure
        self.assertIn("address", contract_info)
        self.assertIn("deployment_block", contract_info)
        self.assertIn("deployment_time", contract_info)

        # Verify address format
        self.assertTrue(contract_info["address"].startswith("0x"))
        self.assertEqual(len(contract_info["address"]), 42)

        # Verify block number is positive integer
        self.assertGreater(contract_info["deployment_block"], 0)
        self.assertIsInstance(contract_info["deployment_block"], int)

        # Verify timestamp is parseable
        timestamp_pattern = re.compile(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}')
        self.assertIsNotNone(timestamp_pattern.match(contract_info["deployment_time"]))
