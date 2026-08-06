"""
Unit tests for Graph Subgraph data fetching.

Tests the retrieveActiveIndexers function which:
1. Queries Network Subgraph for active indexers (stakedTokens > 0)
2. Queries ENS Subgraph for name resolution
3. Creates active_indexers.json with the results
"""

import json
import pytest
from unittest.mock import Mock, patch
import requests


class TestSubgraphDataFetching:
    """Test fetching data from The Graph's subgraphs."""

    def test_queries_network_subgraph_for_active_indexers(self):
        """
        RED Test: Should query Network Subgraph and retrieve indexers with stakedTokens > 0.

        This test verifies that:
        - The correct GraphQL query is sent to the Network Subgraph
        - Indexers with self-stake > 0 are returned
        - The response is parsed correctly
        """
        # Arrange: Mock the successful GraphQL response
        mock_response = Mock()
        mock_response.json.return_value = {
            "data": {
                "indexers": [
                    {"id": "0x123...", "stakedTokens": "1000000", "defaultDisplayName": "Indexer 1"},
                    {"id": "0x456...", "stakedTokens": "500000", "defaultDisplayName": "Indexer 2"},
                ]
            }
        }
        mock_response.raise_for_status = Mock()

        # Act & Assert: We'll implement retrieveActiveIndexers to pass this test
        with patch('requests.post', return_value=mock_response) as mock_post:
            # This will fail initially - the function doesn't have a clean testable interface yet
            from generate_dashboard import retrieveActiveIndexers

            result = retrieveActiveIndexers(
                graph_api_key="test-key",
                output_file="/tmp/test_active_indexers.json"
            )

            # Verify the first request (network subgraph) was made to the correct
            # endpoint. A second call also fires for ENS name resolution, so we
            # check the first call specifically rather than asserting call count.
            assert mock_post.call_count >= 1
            call_args = mock_post.call_args_list[0]
            assert "gateway.thegraph.com" in call_args[0][0]
            assert "stakedTokens_gt" in call_args[1]['json']['query']

            # Verify the function succeeded
            assert result is True

            # Verify output file was created with correct structure
            with open("/tmp/test_active_indexers.json", "r") as f:
                output = json.load(f)
                assert "indexers" in output
                assert len(output["indexers"]) == 2
                assert output["indexers"][0]["address"] == "0x123..."

    def test_handles_empty_indexer_list_gracefully(self):
        """
        RED Test: Should return False when no indexers are found.

        Verifies error handling when subgraph returns empty results.
        """
        # Arrange: Mock empty response
        mock_response = Mock()
        mock_response.json.return_value = {"data": {"indexers": []}}
        mock_response.raise_for_status = Mock()

        # Act & Assert
        with patch('requests.post', return_value=mock_response):
            from generate_dashboard import retrieveActiveIndexers

            result = retrieveActiveIndexers(
                graph_api_key="test-key",
                output_file="/tmp/test_empty.json"
            )

            # Should return False when no indexers found
            assert result is False

    def test_handles_graphql_errors_gracefully(self):
        """
        RED Test: Should return False when GraphQL query returns errors.

        Verifies error handling for malformed queries or API errors.
        """
        # Arrange: Mock error response
        mock_response = Mock()
        mock_response.json.return_value = {
            "errors": [{"message": "Invalid query"}]
        }

        # Act & Assert
        with patch('requests.post', return_value=mock_response):
            from generate_dashboard import retrieveActiveIndexers

            result = retrieveActiveIndexers(
                graph_api_key="test-key",
                output_file="/tmp/test_error.json"
            )

            # Should return False on GraphQL errors
            assert result is False

    def test_queries_ens_subgraph_for_name_resolution(self):
        """
        RED Test: Should query ENS Subgraph to resolve indexer addresses to ENS names.

        This test verifies that:
        - ENS subgraph is queried with indexer addresses
        - ENS names are correctly mapped to addresses
        - ENS cache is saved for future use
        """
        # Arrange: Mock both Network and ENS subgraph responses
        network_response = Mock()
        network_response.json.return_value = {
            "data": {
                "indexers": [
                    {"id": "0x1234567890123456789012345678901234567890", "stakedTokens": "1000000"}
                ]
            }
        }
        network_response.raise_for_status = Mock()

        ens_response = Mock()
        ens_response.json.return_value = {
            "data": {
                "domains": [
                    {"name": "indexer.eth", "resolvedAddress": {"id": "0x1234567890123456789012345678901234567890"}}
                ]
            }
        }
        ens_response.raise_for_status = Mock()

        # Act & Assert
        import os
        import tempfile
        import shutil
        import database

        tmp_dir = tempfile.mkdtemp()
        try:
            test_db_path = os.path.join(tmp_dir, "test_reo.db")
            with patch('database.DB_PATH', test_db_path), patch('requests.post') as mock_post:
                mock_post.side_effect = [network_response, ens_response]

                database.init_db()

                from generate_dashboard import retrieveActiveIndexers

                result = retrieveActiveIndexers(
                    graph_api_key="test-key",
                    output_file="/tmp/test_ens.json",
                    use_cached_ens=False
                )

                # Should make 2 calls: Network + ENS
                assert mock_post.call_count == 2

                # Verify ENS query format
                ens_call = mock_post.call_args_list[1]
                assert "domains" in ens_call[1]['json']['query']
                assert "resolvedAddress_in" in ens_call[1]['json']['query']

                # Verify the resolved name was cached in the database (ENS
                # caching moved from ens_resolution.json to the ens_cache table)
                cache = database.load_ens_cache()
                assert cache.get("0x1234567890123456789012345678901234567890") == "indexer.eth"
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)
