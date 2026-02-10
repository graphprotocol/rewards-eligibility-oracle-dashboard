"""
Unit tests for block number parsing in generate_dashboard.py
"""
import pytest
from generate_dashboard import parse_deployment_block_from_registry


def test_parse_block_decimal():
    """Test parsing decimal block numbers from GitHub JSON registry"""
    registry = {
        "421614": {
            "RewardsEligibilityOracle": {
                "proxyDeployment": {
                    "blockNumber": 237961353  # Decimal format (actual GitHub JSON format)
                }
            }
        }
    }
    result = parse_deployment_block_from_registry(registry, "421614")
    assert result == 237961353


def test_parse_block_hex():
    """Test parsing hex block numbers (for backward compatibility)"""
    registry = {
        "421614": {
            "RewardsEligibilityOracle": {
                "proxyDeployment": {
                    "blockNumber": "0xe28de09"  # Hex format (237559305 in decimal)
                }
            }
        }
    }
    result = parse_deployment_block_from_registry(registry, "421614")
    assert result == 237559305  # 0xe28de09 = 237559305


def test_parse_block_missing():
    """Test when blockNumber is not in JSON"""
    registry = {
        "421614": {
            "RewardsEligibilityOracle": {}
        }
    }
    result = parse_deployment_block_from_registry(registry, "421614")
    assert result is None


def test_parse_block_missing_network():
    """Test when network ID is not in registry"""
    registry = {}
    result = parse_deployment_block_from_registry(registry, "421614")
    assert result is None


def test_parse_block_missing_proxy_deployment():
    """Test when proxyDeployment is not in JSON"""
    registry = {
        "421614": {
            "RewardsEligibilityOracle": {
                # No proxyDeployment key
            }
        }
    }
    result = parse_deployment_block_from_registry(registry, "421614")
    assert result is None


def test_parse_block_invalid_value():
    """Test when blockNumber has invalid value"""
    registry = {
        "421614": {
            "RewardsEligibilityOracle": {
                "proxyDeployment": {
                    "blockNumber": "invalid"
                }
            }
        }
    }
    result = parse_deployment_block_from_registry(registry, "421614")
    assert result is None


def test_parse_block_hex_with_0x_prefix():
    """Test parsing hex block numbers with 0x prefix"""
    registry = {
        "421614": {
            "RewardsEligibilityOracle": {
                "proxyDeployment": {
                    "blockNumber": "0xe28de09"  # Hex with 0x prefix (237559305 in decimal)
                }
            }
        }
    }
    result = parse_deployment_block_from_registry(registry, "421614")
    assert result == 237559305  # 0xe28de09 = 237559305
