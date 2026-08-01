#!/usr/bin/env python3
"""
Eligibility Dashboard Generator

Fetches indexer data from The Graph Network subgraph, checks eligibility via
smart contract, and generates a static HTML dashboard.

Uses SQLite database for production-ready data persistence.
"""

import os
import json
import requests
import shutil
import re
import subprocess
import tempfile
from datetime import datetime, timezone
from typing import List, Tuple, Optional
from dotenv import load_dotenv
import threading

# Import database module
from database import (
    save_indexers, get_all_indexers, update_eligibility, log_status_change,
    get_previous_indexers, update_status_changes, save_ens_cache, load_ens_cache,
    save_transaction, get_last_transaction as db_get_last_transaction, update_sync_state, set_metadata, get_metadata,
    calculate_continuous_streak, get_status_change_history
)

# Version of the dashboard generator
VERSION = "0.2.1"

# GitHub JSON Registry URL for contract addresses
CONTRACT_ADDRESSES_URL = "https://raw.githubusercontent.com/graphprotocol/contracts/refs/heads/main/packages/issuance/addresses.json"


def fetch_contract_addresses() -> dict:
    """
    Fetch contract addresses from the GitHub JSON registry.

    Returns:
        dict: Network IDs mapped to contract addresses
        e.g., {"42161": {"RewardsEligibilityOracle": {"address": "0x..."}}, ...}
    """
    try:
        response = requests.get(CONTRACT_ADDRESSES_URL, timeout=10)
        response.raise_for_status()
        data = response.json()

        # Log successful fetch
        network_count = len([k for k in data.keys() if k.isdigit()])
        print(f"✓ Fetched contract addresses from GitHub ({network_count} networks)")

        return data
    except requests.exceptions.RequestException as e:
        print(f"⚠ Warning: Failed to fetch contract addresses from GitHub: {e}")
        print(f"  Will use fallback environment variables")
        return {}
    except json.JSONDecodeError as e:
        print(f"⚠ Warning: Invalid JSON from GitHub registry: {e}")
        print(f"  Will use fallback environment variables")
        return {}


def _find_reo_entry(network_data: dict) -> Optional[dict]:
    """
    Locate the Rewards Eligibility Oracle entry within a network's registry block.

    The addresses.json registry is inconsistent across networks: testnet (421614)
    exposes the oracle under "RewardsEligibilityOracle", while mainnet (42161)
    uses "RewardsEligibilityOracleA". Prefer the canonical key, then fall back to
    any key that starts with "RewardsEligibilityOracle".

    Args:
        network_data: The registry block for a single network (e.g. registry["42161"])

    Returns:
        The oracle entry dict, or None if not found.
    """
    if not isinstance(network_data, dict):
        return None
    if "RewardsEligibilityOracle" in network_data:
        return network_data["RewardsEligibilityOracle"]
    for key, value in network_data.items():
        if key.startswith("RewardsEligibilityOracle"):
            return value
    return None


def _environment_data_to_json(environment_data: Optional[dict]) -> str:
    """
    Serialize environment_data for embedding in the dashboard page.

    Each environment's ``config`` carries a live ``RoundRobinRPC`` instance (see
    get_environments_config), which is not JSON-serializable. Drop it — and any
    other non-serializable config value — so the client-side ``environmentData``
    object can be embedded without crashing HTML generation.

    Returns:
        A JSON string (``"{}"`` when there is no environment data).
    """
    if not environment_data:
        return "{}"

    safe: dict = {}
    for env_key, env in environment_data.items():
        env_copy = dict(env)
        config = env_copy.get("config")
        if isinstance(config, dict):
            env_copy["config"] = {
                k: v for k, v in config.items() if k != "rpc_manager"
            }
        safe[env_key] = env_copy

    # default=str is a belt-and-suspenders guard against any future
    # non-serializable value sneaking into the embedded data.
    return json.dumps(safe, default=str)


def parse_contract_address_from_registry(registry: dict, network_id: str) -> Optional[str]:
    """
    Parse contract address from registry for a specific network.

    Args:
        registry: The full addresses.json dict
        network_id: Network ID as string (e.g., "42161", "421614")

    Returns:
        Contract address or None if not found
    """
    if network_id in registry:
        reo = _find_reo_entry(registry[network_id])
        if reo:
            return reo.get("address")

    return None


def parse_deployment_block_from_registry(registry: dict, network_id: str) -> Optional[int]:
    """
    Parse deployment block number from registry for a specific network.

    Args:
        registry: The full addresses.json dict
        network_id: Network ID as string (e.g., "42161", "421614")

    Returns:
        Deployment block number or None if not found
    """
    if network_id in registry:
        reo = _find_reo_entry(registry[network_id])
        if reo:
            proxy_deployment = reo.get("proxyDeployment", {})
            block_number = proxy_deployment.get("blockNumber")
            if block_number:
                try:
                    return int(block_number, 16)  # Try hex first
                except (ValueError, TypeError):
                    try:
                        return int(block_number)  # Fallback to decimal
                    except (ValueError, TypeError):
                        return None

    return None


def get_environments_config() -> dict:
    """
    Build the ENVIRONMENTS config dict with dynamic contract addresses and
    per-network RPC managers.

    Each environment gets its own RoundRobinRPC instance so that mainnet
    (Arbitrum One) and testnet (Arbitrum Sepolia) use separate RPC endpoints.

    RPC endpoint resolution per environment:
        1. RPC_ENDPOINT_MAINNET / RPC_ENDPOINT_TESTNET (network-specific)
        2. Falls back to generic RPC_ENDPOINT if no network-specific endpoint is set

    Returns:
        dict: ENVIRONMENTS configuration with per-environment rpc_manager
    """
    # Fetch from GitHub JSON
    addresses = fetch_contract_addresses()

    # Get Sepolia address from JSON registry
    sepolia_address = parse_contract_address_from_registry(addresses, "421614")
    sepolia_deployment_block = parse_deployment_block_from_registry(addresses, "421614")

    # Resolve the testnet contract address. The Sepolia (421614) registry block
    # holds several oracle variants (RewardsEligibilityOracleA/B/Mock) with no
    # canonical "RewardsEligibilityOracle" key, so the registry auto-pick is
    # ambiguous. TESTNET_CONTRACT_ADDRESS lets you pin an explicit address
    # (e.g. the RewardsEligibilityOracleMock deployment) and takes precedence.
    testnet_address = (
        os.getenv("TESTNET_CONTRACT_ADDRESS")
        or sepolia_address
        or "0x62c2305739cc75f19a3a6d52387ceb3690d99a99"
    )

    # Get mainnet address from registry (handles the "RewardsEligibilityOracleA"
    # key), falling back to .env if the registry doesn't have it.
    mainnet_address = parse_contract_address_from_registry(addresses, "42161")
    if not mainnet_address:
        # Try to get from environment variable
        mainnet_address = os.getenv("MAINNET_CONTRACT_ADDRESS", "")

    environments = {
        "mainnet": {
            "name": "Arbitrum One",
            "network_id": 42161,
            "rpc_manager": RoundRobinRPC(network="mainnet"),
            "contract_address": mainnet_address,
            "deployment_block": parse_deployment_block_from_registry(addresses, "42161"),
            "explorer_url": "https://arbiscan.io",
        },
        "testnet": {
            "name": "Arbitrum Sepolia",
            "network_id": 421614,
            "rpc_manager": RoundRobinRPC(network="testnet"),
            "contract_address": testnet_address,
            "deployment_block": sepolia_deployment_block,
            "explorer_url": "https://sepolia.arbiscan.io",
        },
    }

    return environments


# Global placeholder - will be populated in main()
ENVIRONMENTS = {}


def get_block_timestamp(rpc_manager: 'RoundRobinRPC', block_number: int) -> Optional[str]:
    """
    Fetch block timestamp for contract deployment.

    Args:
        rpc_manager: RoundRobinRPC instance to make RPC calls
        block_number: Block number to fetch timestamp for

    Returns:
        ISO 8601 timestamp string (UTC) or None if failed
    """
    if not block_number or not rpc_manager:
        return None

    try:
        # Convert block number to hex
        block_hex = hex(block_number)

        # Try eth_getBlockByNumber RPC call
        result = rpc_manager.rpc_call("eth_getBlockByNumber", [block_hex, False], timeout=10)

        if result and isinstance(result, dict):
            timestamp_hex = result.get("timestamp")
            if timestamp_hex:
                # Convert hex timestamp to datetime
                timestamp_int = int(timestamp_hex, 16)
                dt = datetime.fromtimestamp(timestamp_int, tz=timezone.utc)
                return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")
    except Exception as e:
        print(f"⚠ Warning: Failed to fetch block {block_number} timestamp: {e}")

    return None


def calculate_stats(indexers: List[dict]) -> dict:
    """
    Calculate statistics from a list of indexers.

    Args:
        indexers: List of indexer dicts with status field

    Returns:
        Dict with counts: eligible, grace, ineligible, total
    """
    stats = {
        "total": len(indexers),
        "eligible": 0,
        "grace": 0,
        "ineligible": 0
    }

    for indexer in indexers:
        status = indexer.get("status", "unknown")
        if status == "eligible-active":
            stats["eligible"] += 1
        elif status == "eligible-grace":
            stats["grace"] += 1
        else:
            stats["ineligible"] += 1

    return stats


class RoundRobinRPC:
    """
    Round-robin RPC endpoint manager.
    Cycles through multiple RPC endpoints for load balancing and failover.
    """
    def __init__(self, network=None):
        self.endpoints = []
        self.current_index = 0
        self.network = network
        self.lock = threading.Lock()
        self._load_endpoints()

    def _load_endpoints(self):
        """Load RPC endpoints from environment variables.

        If a network is specified (e.g. 'mainnet', 'testnet'), loads from
        RPC_ENDPOINT_MAINNET, RPC_ENDPOINT_MAINNET_2, etc. first.
        Falls back to generic RPC_ENDPOINT only if no network-specific
        endpoints are found (backward compatibility).
        """
        if self.network:
            network_key = self.network.upper()
            # Try RPC_ENDPOINT_{NETWORK} (primary)
            primary = os.getenv(f"RPC_ENDPOINT_{network_key}")
            if primary:
                self.endpoints.append(primary)
            # Try RPC_ENDPOINT_{NETWORK}_2, _3, etc.
            i = 2
            while True:
                endpoint = os.getenv(f"RPC_ENDPOINT_{network_key}_{i}")
                if endpoint:
                    self.endpoints.append(endpoint)
                    i += 1
                else:
                    break

        # Fall back to generic endpoints if no network-specific ones found
        if not self.endpoints:
            rpc_endpoint = os.getenv("RPC_ENDPOINT")
            if rpc_endpoint:
                self.endpoints.append(rpc_endpoint)
            # Try RPC_ENDPOINT_1, RPC_ENDPOINT_2, etc.
            i = 1
            while True:
                endpoint = os.getenv(f"RPC_ENDPOINT_{i}")
                if endpoint:
                    self.endpoints.append(endpoint)
                    i += 1
                else:
                    break

        # Remove duplicates while preserving order
        seen = set()
        self.endpoints = [x for x in self.endpoints if not (x in seen or seen.add(x))]

        network_label = f" ({self.network})" if self.network else ""
        if not self.endpoints:
            print(f"⚠ Warning: No RPC endpoints found{network_label}")
        else:
            print(f"✓ Loaded {len(self.endpoints)} RPC endpoint(s){network_label}")
            for i, endpoint in enumerate(self.endpoints, 1):
                # Mask API keys in display using the same logic as _mask_endpoint
                display_endpoint = self._mask_endpoint(endpoint)
                print(f"  {i}. {display_endpoint}")
    
    def get_next(self) -> Optional[str]:
        """
        Get the next RPC endpoint in round-robin fashion.
        
        Returns:
            RPC endpoint URL or None if no endpoints available
        """
        with self.lock:
            if not self.endpoints:
                return None
            
            endpoint = self.endpoints[self.current_index]
            self.current_index = (self.current_index + 1) % len(self.endpoints)
            return endpoint
    
    def get_all(self) -> List[str]:
        """Get all available RPC endpoints."""
        return self.endpoints.copy()
    
    def rpc_call(self, method: str, params: list, timeout: int = 15, retry_all: bool = False) -> Optional[dict]:
        """
        Make an RPC call using round-robin endpoint selection.
        If retry_all is True, will try all endpoints before giving up.
        
        Args:
            method: RPC method name (e.g., 'eth_call', 'eth_blockNumber')
            params: RPC method parameters
            timeout: Request timeout in seconds
            retry_all: If True, try all endpoints on failure; if False, try only one
            
        Returns:
            RPC response result or None if all attempts failed
        """
        if not self.endpoints:
            print(f"❌ No RPC endpoints available for {method}")
            return None
        
        endpoints_to_try = self.endpoints.copy() if retry_all else [self.get_next()]
        
        for endpoint in endpoints_to_try:
            try:
                response = requests.post(
                    endpoint,
                    json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
                    timeout=timeout,
                )
                response.raise_for_status()
                data = response.json()
                
                if isinstance(data, dict) and data.get("error"):
                    error_msg = data['error'].get('message', 'Unknown error')
                    print(f"⚠ RPC error for {method} on {self._mask_endpoint(endpoint)}: {error_msg}")
                    if retry_all:
                        continue
                    return None
                
                return data.get("result")
            except requests.exceptions.Timeout:
                print(f"⚠ Timeout for {method} on {self._mask_endpoint(endpoint)}")
                if retry_all:
                    continue
                return None
            except requests.exceptions.RequestException as e:
                print(f"⚠ Request exception for {method} on {self._mask_endpoint(endpoint)}: {e}")
                if retry_all:
                    continue
                return None
            except Exception as e:
                print(f"⚠ Exception for {method} on {self._mask_endpoint(endpoint)}: {e}")
                if retry_all:
                    continue
                return None
        
        print(f"❌ All RPC endpoints failed for {method}")
        return None
    
    def _mask_endpoint(self, endpoint: str) -> str:
        """Mask sensitive parts of endpoint URL for logging."""
        try:
            # Handle URLs with API keys in query parameters (e.g., ?apikey=xxx)
            if 'apikey=' in endpoint.lower():
                # Split on '?' to separate base URL from query params
                if '?' in endpoint:
                    base_url = endpoint.split('?')[0]
                    return base_url + '?***'
                # If apikey is in path (unlikely but possible)
                parts = endpoint.split('/')
                if len(parts) > 0:
                    return '/'.join(parts[:3]) + '/***'
            
            # Handle URLs with API keys in path (e.g., /v2/xxx or /v3/xxx)
            if '/v3/' in endpoint or '/v2/' in endpoint:
                parts = endpoint.split('/')
                if len(parts) > 0:
                    # Find the index of /v2/ or /v3/
                    v_index = -1
                    for i, part in enumerate(parts):
                        if part in ['v2', 'v3']:
                            v_index = i
                            break
                    if v_index >= 0 and v_index + 1 < len(parts):
                        # Mask everything after /v2/ or /v3/
                        return '/'.join(parts[:v_index + 2]) + '/***'
                    else:
                        # Fallback: mask after first 3 parts
                        return '/'.join(parts[:3]) + '/***'
        except Exception:
            # If masking fails, return original endpoint (better than crashing)
            pass
        
        return endpoint


# Global round-robin RPC manager instance
_rpc_manager = None


def get_rpc_manager() -> RoundRobinRPC:
    """Get or create the global RPC manager instance."""
    global _rpc_manager
    if _rpc_manager is None:
        _rpc_manager = RoundRobinRPC()
    return _rpc_manager

# Import telegram notifier (will be skipped if module not available)
try:
    import telegram_notifier
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False


def get_last_transaction_from_json(json_file: str = 'last_transaction.json') -> Optional[dict]:
    """Wrapper: now uses database instead of JSON file."""
    return db_get_last_transaction()


def save_transaction_to_json(transaction_data: dict, json_file: str = 'last_transaction.json') -> None:
    """Wrapper: now uses database instead of JSON file."""
    if save_transaction(transaction_data):
        print(f"✓ Transaction data saved to database")
    else:
        print(f"⚠ Failed to save transaction data")


def get_last_transaction(contract_address: str, api_key: str, chainid: str = "421614") -> Optional[dict]:
    """
    Get the last transaction for a contract from the Etherscan V2 API.
    Uses txlist action, descending sort, and limit 1 for efficiency.

    Args:
        contract_address: The contract address to query
        api_key: Arbiscan/Etherscan API key (Etherscan V2 keys are chain-agnostic)
        chainid: Target chain ID as a string. Defaults to "421614" (Arbitrum
            Sepolia); pass "42161" for Arbitrum One (mainnet).

    Returns:
        Dictionary with transaction data (keys: 'hash', 'blockNumber', 'timeStamp', 'from') or None if error
    """
    base_url = "https://api.etherscan.io/v2/api"
    params = {
        "module": "account",
        "action": "txlist",
        "address": contract_address,
        "sort": "desc",  # Descending order (most recent first)
        "page": 1,
        "offset": 1,  # Only get the last transaction
        "chainid": chainid,
        "apikey": api_key
    }
        
    try:
        print(f"Fetching latest transaction from Arbiscan API (Etherscan V2)...")
        response = requests.get(base_url, params=params, timeout=15)
        response.raise_for_status()  # Raise error for bad status codes
        data = response.json()
        
        if data.get("status") == "1" and data.get("result"):
            tx = data["result"][0]
            tx_hash = tx["hash"]
            block_num = tx["blockNumber"]
            timestamp = int(tx["timeStamp"])
            
            print(f"✓ Found latest transaction via Arbiscan API!")
            print(f"  Hash: {tx_hash}")
            print(f"  Block: {block_num}")
            
            dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
            print(f"  Date: {dt.strftime('%Y-%m-%d %H:%M:%S UTC')}")
            
            return tx
        else:
            print("No transactions found or API error:", data.get("message"))
            return None
            
    except requests.RequestException as e:
        print(f"Request failed: {e}")
        return None
    except Exception as e:
        print(f"Error in get_last_transaction: {e}")
        import traceback
        traceback.print_exc()
        return None


def get_last_transaction_via_rpc(contract_address: str, rpc_manager: Optional[RoundRobinRPC] = None) -> Optional[dict]:
    """
    Get the last transaction touching the contract using an RPC endpoint.
    Strategy: Scan recent blocks and find transactions where 'to' == contract address.
    Skips eth_getLogs entirely as it causes 413 errors on contracts with many events.
    Returns a dict with 'hash', 'blockNumber' (as decimal string), and 'timeStamp' (as decimal string) or None.
    
    Args:
        contract_address: The contract address to query
        rpc_manager: RoundRobinRPC instance (if None, uses global instance)
    """
    if rpc_manager is None:
        rpc_manager = get_rpc_manager()

    def hex_to_dec_str(hex_str: Optional[str]) -> str:
        try:
            return str(int(hex_str, 16)) if hex_str else "0"
        except Exception:
            return "0"

    try:
        print("Fetching latest block number...")
        latest_hex = rpc_manager.rpc_call("eth_blockNumber", [])
        if not latest_hex:
            return None
        latest_int = int(latest_hex, 16)
        print(f"Latest block: {latest_int}")

        # Scan recent blocks for transactions to the contract
        # Based on QuickNode guide: iterate backwards from latest block
        # On Arbitrum Sepolia, blocks are ~250ms apart
        # 50,000 blocks = roughly 3-4 hours of history
        scan_window = 50000
        starting_block = max(0, latest_int - scan_window)
        
        print(f"Searching for last transaction to {contract_address}")
        print(f"Scanning blocks {starting_block} to {latest_int} ({scan_window:,} blocks)...")
        
        # Iterate backwards from latest block to find most recent transaction
        for i in range(scan_window):
            block_num = latest_int - i
            if block_num < starting_block:
                break
            
            # Get block with FULL transaction objects (True flag)
            block = rpc_manager.rpc_call("eth_getBlockByNumber", [hex(block_num), True])
            if not isinstance(block, dict):
                continue
            
            timestamp_hex = block.get("timestamp")
            transactions = block.get("transactions") or []
            
            if not isinstance(transactions, list):
                continue
            
            # Check each transaction in the block
            for tx in transactions:
                if not isinstance(tx, dict):
                    continue
                
                to_addr = (tx.get("to") or "").lower()
                from_addr = (tx.get("from") or "").lower()
                
                # Check if transaction involves our contract (to or from)
                if (to_addr and to_addr == contract_address.lower()) or \
                   (from_addr and from_addr == contract_address.lower()):
                    tx_hash = tx.get("hash", "")
                    block_number = hex_to_dec_str(block.get("number"))
                    timestamp = hex_to_dec_str(timestamp_hex)
                    
                    print(f"\n✓ Found latest transaction!")
                    print(f"  Hash: {tx_hash}")
                    print(f"  Block: {block_number}")
                    print(f"  Timestamp: {timestamp}")
                    
                    from datetime import datetime, timezone
                    dt = datetime.fromtimestamp(int(timestamp), tz=timezone.utc)
                    print(f"  Date: {dt.strftime('%Y-%m-%d %H:%M:%S UTC')}")
                    
                    return {
                        "hash": tx_hash,
                        "blockNumber": block_number,
                        "timeStamp": timestamp,
                    }
            
            # Progress indicator every 500 blocks
            if i > 0 and i % 500 == 0:
                print(f"  Scanned {i:,} blocks...", end='\r')
        
        print(f"\nNo transactions found in last {scan_window:,} blocks")
        return None
    except Exception as e:
        print(f"Error in get_last_transaction_via_rpc: {e}")
        import traceback
        traceback.print_exc()
        return None


def get_oracle_update_time(contract_address: str, rpc_manager: Optional[RoundRobinRPC] = None) -> Optional[int]:
    """
    Get the last oracle update time from the contract by calling getLastOracleUpdateTime().
    
    Args:
        contract_address: The contract address
        rpc_manager: RoundRobinRPC instance (if None, uses global instance)
        
    Returns:
        Unix timestamp of last oracle update or None if error
    """
    if rpc_manager is None:
        rpc_manager = get_rpc_manager()
    
    try:
        # Function selector for getLastOracleUpdateTime()
        # keccak256("getLastOracleUpdateTime()") = 0xbe626dd2...
        function_selector = '0xbe626dd2' + '0' * 56  # Padded to 32 bytes
        
        result = rpc_manager.rpc_call('eth_call', [{
            'to': contract_address,
            'data': function_selector
        }, 'latest'], timeout=10, retry_all=True)
        
        if result and result != '0x':
            timestamp = int(result, 16)
            print(f"Oracle update time retrieved: {timestamp}")
            return timestamp
        else:
            print(f"Error getting oracle update time: No valid result")
            return None
    except Exception as e:
        print(f"Exception getting oracle update time: {e}")
        return None


def get_eligibility_period(contract_address: str, rpc_manager: Optional[RoundRobinRPC] = None) -> Optional[int]:
    """
    Get the eligibility period from the contract by calling getEligibilityPeriod().
    
    Args:
        contract_address: The contract address
        rpc_manager: RoundRobinRPC instance (if None, uses global instance)
        
    Returns:
        Eligibility period in seconds or None if error
    """
    if rpc_manager is None:
        rpc_manager = get_rpc_manager()
    
    try:
        # Function selector for getEligibilityPeriod()
        # keccak256("getEligibilityPeriod()") = 0xd0a5379e...
        function_selector = '0xd0a5379e' + '0' * 56  # Padded to 32 bytes
        
        result = rpc_manager.rpc_call('eth_call', [{
            'to': contract_address,
            'data': function_selector
        }, 'latest'], timeout=10, retry_all=True)
        
        if result and result != '0x':
            period = int(result, 16)
            print(f"Eligibility period retrieved: {period} seconds")
            return period
        else:
            print(f"Error getting eligibility period: No valid result")
            return None
    except Exception as e:
        print(f"Exception getting eligibility period: {e}")
        return None


def save_ens_cache_db(ens_mapping: dict, cache_file: str = 'ens_resolution.json') -> None:
    """Wrapper: Saves ENS cache to database."""
    try:
        count = save_ens_cache(ens_mapping)
        resolved_count = len([k for k, v in ens_mapping.items() if v])
        print(f"✓ ENS cache updated and saved to database")
        print(f"  - Total addresses: {count}")
        print(f"  - ENS names resolved: {resolved_count}")
    except Exception as e:
        print(f"❌ Error saving ENS cache to database: {e}")


def load_ens_cache_db(cache_file: str = 'ens_resolution.json') -> Optional[dict]:
    """Wrapper: Loads ENS cache from database."""
    try:
        ens_mapping = load_ens_cache()
        if ens_mapping:
            print(f"✓ Loaded ENS cache from database")
            print(f"  - Total addresses: {len(ens_mapping)}")
        else:
            print(f"ENS cache not found in database")
        return ens_mapping
    except Exception as e:
        print(f"❌ Error loading ENS cache from database: {e}")
        return None


def load_ens_cache(cache_file: str = 'ens_resolution.json') -> Optional[dict]:
    """
    Load ENS resolution data from cache file.
    
    Args:
        cache_file: Path to the cache file
        
    Returns:
        Dictionary mapping addresses (lowercase) to ENS names, or None if cache doesn't exist
    """
    try:
        if not os.path.exists(cache_file):
            print(f"ENS cache file {cache_file} not found")
            return None
        
        with open(cache_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        ens_mapping = data.get("ens_resolutions", {})
        metadata = data.get("metadata", {})
        retrieved = metadata.get("retrieved", "unknown")
        
        print(f"✓ Loaded ENS cache from {cache_file} (retrieved: {retrieved})")
        print(f"  - Total entries: {metadata.get('total_count', 0)}")
        print(f"  - ENS resolved: {metadata.get('ens_resolved', 0)}")
        
        return ens_mapping
    except Exception as e:
        print(f"Error loading ENS cache from {cache_file}: {e}")
        return None


def retrieveActiveIndexers(graph_api_key: str, output_file: str = 'active_indexers.json', use_cached_ens: bool = False, contract_address: Optional[str] = None, rpc_manager: Optional[RoundRobinRPC] = None, transaction_hash: Optional[str] = None, network_id: str = 'testnet') -> bool:
    """
    Retrieve the list of active indexers with self stake > 0 from The Graph's network subgraph.
    ENS resolution can be cached or fetched from subgraph based on use_cached_ens parameter.

    This function retrieves the list of active indexers. ENS names are either loaded from
    cache or fetched from the ENS subgraph, then saved separately.

    Args:
        graph_api_key: The Graph API key for querying the network subgraph
        output_file: Path to the output file (default: active_indexers.json)
        use_cached_ens: If True, use cached ENS data; if False, fetch from subgraph
        contract_address: The contract address to query oracle update time
        rpc_manager: RoundRobinRPC instance (if None, uses global instance)
        transaction_hash: Transaction hash to store in metadata (optional)
        network_id: Network identifier for multi-environment support (default: 'testnet')

    Returns:
        True if successful, False otherwise
    """
    try:
        # The Graph Network subgraph deployment ID
        network_deployment_id = "DZz4kDTdmzWLWsV373w2bSmoar3umKKH9y82SUKr5qmp"
        
        # ENS subgraph deployment ID
        ens_deployment_id = "5XqPmWe6gjyrJtFn9cLy237i4cWw2j9HcUJEXsP5qGtH"
        
        # Construct the Gateway API URLs
        network_url = f"https://gateway.thegraph.com/api/{graph_api_key}/subgraphs/id/{network_deployment_id}"
        ens_url = f"https://gateway.thegraph.com/api/{graph_api_key}/subgraphs/id/{ens_deployment_id}"
        
        # GraphQL query to get indexers with self stake > 0
        indexers_query = """
        {
          indexers(first: 1000, where: {stakedTokens_gt: "0"}) {
            id
            stakedTokens
            defaultDisplayName
          }
        }
        """
        
        print(f"Querying network subgraph for active indexers...")
        
        # Make the GraphQL request to network subgraph
        response = requests.post(
            network_url,
            json={"query": indexers_query},
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        response.raise_for_status()
        
        data = response.json()
        
        # Check for errors in the response
        if "errors" in data:
            print(f"GraphQL Error: {data['errors']}")
            return False
        
        # Extract indexers from the response
        indexers_raw = data.get("data", {}).get("indexers", [])
        
        if not indexers_raw:
            print("No active indexers found with self stake > 0")
            return False
        
        print(f"✓ Retrieved {len(indexers_raw)} active indexers")
        
        # Extract all addresses for ENS lookup
        addresses = [indexer.get("id", "").lower() for indexer in indexers_raw]
        
        # Determine ENS resolution strategy
        ens_mapping = {}
        
        if use_cached_ens:
            print(f"Using cached ENS data...")
            cached_ens = load_ens_cache_db()
            if cached_ens:
                ens_mapping = cached_ens
            else:
                print(f"⚠ Cache not available, will fetch from subgraph")
                use_cached_ens = False
        
        if not use_cached_ens:
            # Query ENS subgraph to resolve names
            print(f"Querying ENS subgraph for name resolution...")
            
            # Build ENS query - query in batches if needed
            batch_size = 100
            
            for i in range(0, len(addresses), batch_size):
                batch_addresses = addresses[i:i+batch_size]
                
                # Build the where clause for this batch
                addresses_filter = '", "'.join(batch_addresses)
                ens_query = f"""
                {{
                  domains(first: 1000, where: {{resolvedAddress_in: ["{addresses_filter}"]}}) {{
                    name
                    resolvedAddress {{
                      id
                    }}
                  }}
                }}
                """
                
                try:
                    ens_response = requests.post(
                        ens_url,
                        json={"query": ens_query},
                        headers={"Content-Type": "application/json"},
                        timeout=30
                    )
                    ens_response.raise_for_status()
                    
                    ens_data = ens_response.json()
                    
                    if "errors" in ens_data:
                        print(f"⚠ ENS query error for batch {i//batch_size + 1}: {ens_data['errors']}")
                        continue
                    
                    # Map addresses to ENS names
                    domains = ens_data.get("data", {}).get("domains", [])
                    for domain in domains:
                        resolved_addr = domain.get("resolvedAddress", {})
                        if resolved_addr:
                            addr_id = resolved_addr.get("id", "").lower()
                            ens_name = domain.get("name", "")
                            if addr_id and ens_name:
                                ens_mapping[addr_id] = ens_name
                    
                except Exception as e:
                    print(f"⚠ Error querying ENS for batch {i//batch_size + 1}: {e}")
                    continue
            
            print(f"✓ Resolved {len(ens_mapping)} ENS names")
            
            # Save ENS cache for future use
            save_ens_cache_db(ens_mapping)
        
        # Build the JSON structure (without ENS names)
        current_timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
        
        # Get oracle update time and eligibility period from contract if available
        last_oracle_update_time = None
        eligibility_period = None
        if contract_address:
            if rpc_manager is None:
                rpc_manager = get_rpc_manager()
            if rpc_manager.endpoints:
                print(f"Fetching last oracle update time from contract...")
                last_oracle_update_time = get_oracle_update_time(contract_address, rpc_manager)
                print(f"Fetching eligibility period from contract...")
                eligibility_period = get_eligibility_period(contract_address, rpc_manager)
        
        output_data = {
            "metadata": {
                "retrieved": current_timestamp,
                "total_count": len(indexers_raw),
                "last_oracle_update_time": last_oracle_update_time,
                "eligibility_period": eligibility_period,
                "transaction_hash": transaction_hash if transaction_hash else None,
                "network_id": network_id
            },
            "indexers": []
        }
        
        # Load previous run data to preserve last_renewed_on_tx
        previous_indexers_map = {}
        backup_file = output_file.replace('.json', '_previous_run.json')
        if os.path.exists(output_file):
            try:
                with open(output_file, 'r', encoding='utf-8') as f:
                    previous_data = json.load(f)
                previous_indexers = previous_data.get("indexers", [])
                previous_indexers_map = {
                    indexer.get("address", "").lower(): indexer.get("last_renewed_on_tx", "")
                    for indexer in previous_indexers
                }
                print(f"✓ Loaded {len(previous_indexers_map)} indexers from previous run")
            except Exception as e:
                print(f"⚠ Warning: Could not load previous file: {e}")
        
        # Process each indexer, attaching the resolved ENS name so it persists
        # into the per-environment JSON (and thus the embedded environmentData
        # used by the environment-toggle view, not just the static table).
        for indexer in indexers_raw:
            address = indexer.get("id", "")

            # Get previous last_renewed_on_tx value if exists
            previous_tx = previous_indexers_map.get(address.lower(), "")

            indexer_data = {
                "address": address,
                "ens_name": ens_mapping.get(address.lower(), ""),
                "is_eligible": False,
                "status": "",
                "eligible_until": "",
                "eligible_until_readable": "",
                "eligibility_renewal_time": "",
                "last_status_change_date": "",
                "last_renewed_on_tx": previous_tx
            }
            output_data["indexers"].append(indexer_data)
        
        # Backup the previous run's file before writing the new one
        if os.path.exists(output_file):
            try:
                shutil.copy(output_file, backup_file)
                print(f"✓ Backed up previous run to {backup_file}")
            except Exception as e:
                print(f"⚠ Warning: Could not backup previous file: {e}")
        
        # Write to JSON file
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2)
        
        print(f"✓ Results written to {output_file}")
        return True
        
    except requests.exceptions.RequestException as e:
        print(f"Request error querying subgraphs: {e}")
        return False
    except Exception as e:
        print(f"Error in retrieveActiveIndexers: {e}")
        return False


def checkEligibility(contract_address: str, rpc_manager: Optional[RoundRobinRPC] = None, input_file: str = 'active_indexers.json', grace_buffer_hours: int = 24, network_id: str = 'testnet') -> bool:
    """
    Check eligibility for each indexer using a two-pass approach:
    1. First pass: Call isEligible(address) for all indexers and store the result
    2. Second pass: Only for eligible indexers, call getEligibilityRenewalTime(address)

    Reads indexer addresses from the JSON file and updates each indexer's is_eligible
    and eligibility_renewal_time fields.

    Args:
        contract_address: The contract address (0x9BED32d2b562043a426376b99d289fE821f5b04E)
        rpc_manager: RoundRobinRPC instance (if None, uses global instance)
        input_file: Path to the active_indexers.json file
        grace_buffer_hours: Buffer period in hours to apply before last_oracle_update_time (default: 24)
        network_id: Network identifier for multi-environment support (default: 'testnet')

    Returns:
        True if successful, False otherwise
    """
    if rpc_manager is None:
        rpc_manager = get_rpc_manager()
    try:
        # Check if input file exists
        if not os.path.exists(input_file):
            print(f"⚠ {input_file} not found, skipping eligibility check")
            return False
        
        # Read the JSON file
        print(f"Reading indexer data from {input_file}...")
        with open(input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        indexers = data.get("indexers", [])
        if not indexers:
            print("No indexers found in JSON file")
            return False
        
        # ========== PASS 1: Check isEligible for all indexers ==========
        print(f"Pass 1: Checking isEligible status for {len(indexers)} indexers...")
        
        # Function selector for isEligible(address)
        # From contract: 0x66e305fd
        is_eligible_selector = '0x66e305fd'
        
        eligible_count = 0
        
        # First pass: Check isEligible for each indexer
        for i, indexer in enumerate(indexers):
            address = indexer.get("address", "")
            if not address:
                continue
            
            try:
                # Prepare the function call data
                # Remove '0x' prefix from address and pad to 32 bytes (64 hex chars)
                address_param = address[2:] if address.startswith('0x') else address
                address_param = address_param.lower().zfill(64)
                
                data_payload = is_eligible_selector + address_param
                
                # Make the eth_call using round-robin RPC manager
                result = rpc_manager.rpc_call("eth_call", [
                    {
                        "to": contract_address,
                        "data": data_payload
                    },
                    "latest"
                ], timeout=10)
                
                if result and result != "0x":
                    # Parse the result (bool)
                    # The result is a 32-byte hex string, bool is the last byte
                    is_eligible = int(result, 16) != 0
                    indexer["is_eligible"] = is_eligible
                    if is_eligible:
                        eligible_count += 1
                else:
                    indexer["is_eligible"] = False
                
            except Exception as e:
                print(f"⚠ Error checking isEligible for {address}: {e}")
                indexer["is_eligible"] = False
                continue
            
            # Progress indicator every 10 indexers
            if (i + 1) % 10 == 0:
                print(f"  Processed {i + 1}/{len(indexers)} indexers...")
        
        print(f"✓ Pass 1 complete: {eligible_count} eligible indexers found")
        
        # ========== PASS 2: Get renewal times for eligible indexers ==========
        print(f"Pass 2: Getting eligibility renewal times for {eligible_count} eligible indexers...")
        
        # Function selector for getEligibilityRenewalTime(address)
        # From contract: 0xd353402d
        renewal_time_selector = '0xd353402d'
        
        updated_count = 0
        processed_count = 0
        
        # Second pass: Get renewal time only for eligible indexers
        for i, indexer in enumerate(indexers):
            # Skip if not eligible
            if not indexer.get("is_eligible", False):
                indexer["eligibility_renewal_time"] = 0
                continue
            
            address = indexer.get("address", "")
            if not address:
                continue
            
            try:
                # Prepare the function call data
                address_param = address[2:] if address.startswith('0x') else address
                address_param = address_param.lower().zfill(64)
                
                data_payload = renewal_time_selector + address_param
                
                # Make the eth_call using round-robin RPC manager
                result = rpc_manager.rpc_call("eth_call", [
                    {
                        "to": contract_address,
                        "data": data_payload
                    },
                    "latest"
                ], timeout=10)
                
                if result and result != "0x":
                    # Parse the result (uint256 timestamp)
                    renewal_time = int(result, 16)
                    indexer["eligibility_renewal_time"] = renewal_time
                    updated_count += 1
                else:
                    indexer["eligibility_renewal_time"] = 0
                
            except Exception as e:
                print(f"⚠ Error getting renewal time for {address}: {e}")
                indexer["eligibility_renewal_time"] = 0
                continue
            
            processed_count += 1
            
            # Progress indicator every 10 eligible indexers
            if processed_count % 10 == 0:
                print(f"  Processed {processed_count}/{eligible_count} eligible indexers...")
        
        print(f"✓ Pass 2 complete: {updated_count} renewal times updated")
        
        # ========== PASS 3: Update status based on eligibility_renewal_time comparison ==========
        print(f"Pass 3: Updating status based on eligibility renewal time and grace period...")
        
        # Get last_oracle_update_time, eligibility_period, and transaction_hash from metadata
        metadata = data.get("metadata", {})
        last_oracle_update_time = metadata.get("last_oracle_update_time")
        eligibility_period = metadata.get("eligibility_period")
        transaction_hash = metadata.get("transaction_hash", "")
        
        # Calculate grace period buffer cutoff time
        # This makes the eligibility check more forgiving by allowing indexers who renewed
        # within grace_buffer_hours before the oracle update to still be considered eligible
        grace_buffer_seconds = grace_buffer_hours * 3600
        grace_buffer_cutoff = last_oracle_update_time - grace_buffer_seconds if last_oracle_update_time else None
        
        if grace_buffer_cutoff:
            dt_buffer = datetime.fromtimestamp(grace_buffer_cutoff, tz=timezone.utc)
            print(f"✓ Grace buffer: {grace_buffer_hours} hours ({grace_buffer_seconds:,} seconds)")
            print(f"  Indexers renewed after {dt_buffer.strftime('%-d-%b-%Y at %H:%M:%S UTC')} are considered eligible")
        
        # Get current timestamp
        current_time = int(datetime.now(timezone.utc).timestamp())
        
        eligible_status_count = 0
        grace_status_count = 0
        ineligible_status_count = 0
        
        for indexer in indexers:
            eligibility_renewal_time = indexer.get("eligibility_renewal_time", 0)
            
            # Format eligibility_renewal_time to readable format (both short and full)
            if eligibility_renewal_time > 0:
                dt = datetime.fromtimestamp(eligibility_renewal_time, tz=timezone.utc)
                indexer["eligibility_renewal_time_readable"] = dt.strftime("%-d-%b-%Y at %H:%M:%S UTC")
                indexer["eligibility_renewal_time_short"] = dt.strftime("%-d-%b-%Y")
            else:
                indexer["eligibility_renewal_time_readable"] = "Never"
                indexer["eligibility_renewal_time_short"] = "Never"
            
            # Set status based on comparison with grace_buffer_cutoff and grace period
            # Eligible: renewed at or after (last_oracle_update_time - buffer)
            if grace_buffer_cutoff and eligibility_renewal_time >= grace_buffer_cutoff:
                # Indexer is eligible (within buffer period)
                indexer["status"] = "eligible-active"
                indexer["eligible_until"] = ""
                indexer["eligible_until_readable"] = ""
                indexer["eligible_until_short"] = ""
                # Update last_renewed_on_tx with current transaction hash when eligible
                if transaction_hash:
                    indexer["last_renewed_on_tx"] = transaction_hash
                eligible_status_count += 1
            elif grace_buffer_cutoff and eligibility_renewal_time < grace_buffer_cutoff and eligibility_period and eligibility_renewal_time > 0:
                # Check if in grace period
                grace_period_end = eligibility_renewal_time + eligibility_period
                if current_time < grace_period_end:
                    indexer["status"] = "eligible-grace"
                    indexer["eligible_until"] = grace_period_end
                    # Format: 2-Nov-2025 at 19:25:55 UTC (day without leading zero)
                    dt = datetime.fromtimestamp(grace_period_end, tz=timezone.utc)
                    indexer["eligible_until_readable"] = dt.strftime("%-d-%b-%Y at %H:%M:%S UTC")
                    indexer["eligible_until_short"] = dt.strftime("%-d-%b-%Y")
                    grace_status_count += 1
                    # Keep previous last_renewed_on_tx (don't update when in grace)
                else:
                    # Indexer was eligible before but eligibility expired
                    indexer["status"] = "ineligible-expired"
                    indexer["eligible_until"] = ""
                    indexer["eligible_until_readable"] = ""
                    indexer["eligible_until_short"] = ""
                    ineligible_status_count += 1
                    # Keep previous last_renewed_on_tx (don't update when ineligible)
            else:
                # Indexer has never been eligible (renewal time is 0 or invalid)
                indexer["status"] = "ineligible-unqualified"
                indexer["eligible_until"] = ""
                indexer["eligible_until_readable"] = ""
                indexer["eligible_until_short"] = ""
                ineligible_status_count += 1
                # Keep previous last_renewed_on_tx (don't update when ineligible)
        
        print(f"✓ Pass 3 complete:")
        print(f"  - Eligible: {eligible_status_count}")
        print(f"  - Grace: {grace_status_count}")
        print(f"  - Ineligible: {ineligible_status_count}")

        # ========== PASS 4: Log status changes to database ==========
        print(f"Pass 4: Logging status changes to database...")

        # Load previous indexers from database
        previous_indexers_db = get_all_indexers(network_id)
        previous_indexers_map = {
            idx.get('id', idx.get('address', '')).lower(): idx
            for idx in previous_indexers_db
        }

        # Log status changes
        status_changes_logged = 0
        for indexer in indexers:
            address = indexer.get("address", "").lower()
            current_status = indexer.get("status", "")

            if address in previous_indexers_map:
                previous_indexer = previous_indexers_map[address]
                previous_status = previous_indexer.get("status", "")

                if current_status != previous_status:
                    # Get transaction hash if this indexer renewed in this run
                    tx_hash = indexer.get("last_renewed_on_tx", "")
                    log_status_change(address, previous_status, current_status, tx_hash=tx_hash, network_id=network_id)
                    status_changes_logged += 1

        print(f"✓ Pass 4 complete: {status_changes_logged} status changes logged to database")

        # Write updated data back to JSON file
        with open(input_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

        print(f"✓ Eligibility check complete:")
        print(f"  - Total indexers: {len(indexers)}")
        print(f"  - Eligible indexers: {eligible_count}")
        print(f"  - Renewal times retrieved: {updated_count}")
        print(f"  - Status breakdown: {eligible_status_count} eligible, {grace_status_count} grace, {ineligible_status_count} ineligible")
        print(f"✓ Results written to {input_file}")

        # Save current indexer states to database for streak calculation
        print("✓ Saving indexer states to database...")
        saved_count = save_indexers(indexers, network_id=network_id)
        print(f"  - Saved {saved_count} indexers to database")

        return True
        
    except Exception as e:
        print(f"Error in checkEligibility: {e}")
        return False


def updateStatusChangeDates(current_file: str = 'active_indexers.json', previous_file: str = 'active_indexers_previous_run.json', network_id: str = 'testnet') -> bool:
    """
    Compare the current and previous run files to detect status changes.
    Updates the last_status_change_date field for indexers whose status has changed.
    
    Args:
        current_file: Path to the current active_indexers.json file
        previous_file: Path to the previous run's backup file
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Check if current file exists
        if not os.path.exists(current_file):
            print(f"⚠ {current_file} not found, skipping status change detection")
            return False
        
        # Read current file
        print(f"Reading current file: {current_file}...")
        with open(current_file, 'r', encoding='utf-8') as f:
            current_data = json.load(f)
        
        current_indexers = current_data.get("indexers", [])
        if not current_indexers:
            print("No indexers found in current file")
            return False
        
        # Try to read previous file
        previous_indexers_map = {}
        if os.path.exists(previous_file):
            print(f"Reading previous file: {previous_file}...")
            with open(previous_file, 'r', encoding='utf-8') as f:
                previous_data = json.load(f)
            
            previous_indexers = previous_data.get("indexers", [])
            # Create a map of address -> indexer data for quick lookup
            previous_indexers_map = {
                indexer.get("address", "").lower(): indexer 
                for indexer in previous_indexers
            }
            print(f"✓ Loaded {len(previous_indexers_map)} indexers from previous run")
        else:
            print(f"⚠ {previous_file} not found, treating all as new indexers")
        
        # Get current date in format like "21/Oct/2025"
        current_date = datetime.now(timezone.utc).strftime("%-d/%b/%Y")
        
        # Track changes
        status_changed_count = 0
        status_unchanged_count = 0
        new_indexers_count = 0
        
        # Compare each indexer
        for indexer in current_indexers:
            address = indexer.get("address", "").lower()
            current_status = indexer.get("status", "")
            
            if address in previous_indexers_map:
                # Indexer existed in previous run
                previous_indexer = previous_indexers_map[address]
                previous_status = previous_indexer.get("status", "")
                previous_date = previous_indexer.get("last_status_change_date", "")
                
                if current_status != previous_status:
                    # Status changed - update with current date
                    indexer["last_status_change_date"] = current_date
                    status_changed_count += 1
                else:
                    # Status unchanged - keep previous date (could be empty or a date)
                    indexer["last_status_change_date"] = previous_date
                    status_unchanged_count += 1
            else:
                # New indexer not in previous run - leave empty (no previous status to compare)
                indexer["last_status_change_date"] = ""
                new_indexers_count += 1
        
        # Write updated data back to current file
        with open(current_file, 'w', encoding='utf-8') as f:
            json.dump(current_data, f, indent=2)
        
        print(f"✓ Status change detection complete:")
        print(f"  - Status changed: {status_changed_count}")
        print(f"  - Status unchanged: {status_unchanged_count}")
        print(f"  - New indexers: {new_indexers_count}")
        print(f"✓ Updated {current_file} with status change dates")
        return True
        
    except Exception as e:
        print(f"Error in updateStatusChangeDates: {e}")
        return False


def logStatusChanges(current_file: str = 'active_indexers.json', previous_file: str = 'active_indexers_previous_run.json', log_file: str = 'activity_log_indexers_status_changes.json', network_id: str = 'testnet') -> bool:
    """
    Track and log status changes for indexers in an activity log file.
    Updates metadata on each run and appends status change entries.
    
    Args:
        current_file: Path to the current active_indexers.json file
        previous_file: Path to the previous run's backup file
        log_file: Path to the activity log file
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Check if current file exists
        if not os.path.exists(current_file):
            print(f"⚠ {current_file} not found, skipping status change logging")
            return False
        
        # Read current file
        with open(current_file, 'r', encoding='utf-8') as f:
            current_data = json.load(f)
        
        current_indexers = current_data.get("indexers", [])
        current_metadata = current_data.get("metadata", {})
        
        if not current_indexers:
            print("No indexers found in current file")
            return False
        
        # Try to read previous file
        previous_indexers_map = {}
        if os.path.exists(previous_file):
            with open(previous_file, 'r', encoding='utf-8') as f:
                previous_data = json.load(f)
            
            previous_indexers = previous_data.get("indexers", [])
            # Create a map of address -> status for quick lookup
            previous_indexers_map = {
                indexer.get("address", "").lower(): indexer.get("status", "")
                for indexer in previous_indexers
            }
        
        # Load existing activity log or create new one
        activity_log = {"metadata": {}, "status_changes": []}
        if os.path.exists(log_file):
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    activity_log = json.load(f)
                    # Ensure status_changes list exists
                    if "status_changes" not in activity_log:
                        activity_log["status_changes"] = []
            except Exception as e:
                print(f"⚠ Error reading existing log file, creating new one: {e}")
                activity_log = {"metadata": {}, "status_changes": []}
        
        # Update metadata section (always overwrite)
        current_check = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
        last_oracle_update_time = current_metadata.get("last_oracle_update_time")
        
        activity_log["metadata"] = {
            "last_check": current_check,
            "last_oracle_update_time": last_oracle_update_time
        }
        
        # Get current date for status changes
        current_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        
        # Track status changes
        changes_count = 0
        
        for indexer in current_indexers:
            address = indexer.get("address", "").lower()
            current_status = indexer.get("status", "")
            
            if address in previous_indexers_map:
                previous_status = previous_indexers_map[address]
                
                if current_status != previous_status and previous_status and current_status:
                    # Status changed - append to log
                    change_entry = {
                        "address": indexer.get("address", ""),  # Keep original case
                        "previous_status": previous_status,
                        "new_status": current_status,
                        "date_status_change": current_date
                    }
                    activity_log["status_changes"].append(change_entry)
                    changes_count += 1
        
        # Write updated activity log back to file
        with open(log_file, 'w', encoding='utf-8') as f:
            json.dump(activity_log, f, indent=2)
        
        print(f"✓ Activity log updated:")
        print(f"  - Last check: {current_check}")
        print(f"  - Status changes detected: {changes_count}")
        print(f"  - Total entries in log: {len(activity_log['status_changes'])}")
        print(f"✓ Activity log saved to {log_file}")
        return True
        
    except Exception as e:
        print(f"Error in logStatusChanges: {e}")
        return False


def read_indexers_data(filename: str = 'indexers.txt') -> List[Tuple[str, str]]:
    """
    Read indexer data from the text file.
    
    Args:
        filename: Path to the indexers.txt file
        
    Returns:
        List of tuples containing (address, ens_name)
    """
    indexers = []
    
    if not os.path.exists(filename):
        print(f"Error: {filename} not found!")
        return []
    
    with open(filename, 'r', encoding='utf-8') as file:
        for line_num, line in enumerate(file, 1):
            line = line.strip()
            if not line:
                continue
                
            # Split by comma, handle empty ENS names
            parts = line.split(',', 1)
            if len(parts) == 2:
                address, ens_name = parts
                indexers.append((address.strip(), ens_name.strip()))
            else:
                # Handle case where there's no comma (just address)
                indexers.append((line.strip(), ''))
    
    return indexers


def renderIndexerTable(json_file: str = 'active_indexers.json', network_id: str = 'testnet') -> List[dict]:
    """
    Read all indexers from the active_indexers.json file and merge with ENS data.
    Returns all indexers regardless of eligibility status.
    Calculates continuous eligibility streaks for all indexers.

    Args:
        json_file: Path to the active_indexers.json file
        network_id: Network identifier for database queries

    Returns:
        List of dictionaries containing all indexer data with ENS names and streak days
    """
    all_indexers = []
    
    try:
        if not os.path.exists(json_file):
            print(f"⚠ {json_file} not found, no indexers to display")
            return []
        
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        indexers = data.get("indexers", [])
        
        # Load ENS data from cache
        ens_mapping = load_ens_cache() or {}

        # Get current time for streak calculations
        current_time = int(datetime.now(timezone.utc).timestamp())

        # Process all indexers and merge with ENS data
        eligible_count = 0
        grace_count = 0
        ineligible_count = 0

        for indexer in indexers:
            address = indexer.get("address", "")
            address_lower = address.lower()

            # Create a copy of the indexer data and add ENS name
            indexer_with_ens = indexer.copy()
            indexer_with_ens["ens_name"] = ens_mapping.get(address_lower, "")

            # Use status from JSON file (already calculated by checkEligibility)
            status = indexer.get("status", "ineligible")
            indexer_with_ens["status"] = status

            # Calculate continuous eligibility streak
            streak_result = calculate_continuous_streak(address, current_time, network_id)
            indexer_with_ens["continuous_streak_days"] = streak_result["days"]

            # Set is_eligible based on status
            if status == "eligible-active":
                indexer_with_ens["is_eligible"] = True
                eligible_count += 1
            elif status == "eligible-grace":
                indexer_with_ens["is_eligible"] = True  # Grace period indexers are still considered eligible
                grace_count += 1
            else:
                # All ineligible statuses (ineligible-expired, ineligible-unqualified)
                indexer_with_ens["is_eligible"] = False
                ineligible_count += 1

            all_indexers.append(indexer_with_ens)
        
        print(f"✓ Loaded {len(all_indexers)} indexers from {json_file}")
        print(f"  - Eligible: {eligible_count}")
        print(f"  - Grace: {grace_count}")
        print(f"  - Ineligible: {ineligible_count}")
        return all_indexers
        
    except Exception as e:
        print(f"Error reading {json_file}: {e}")
        return []


ELIGIBILITY_CRITERIA_URL = (
    "https://github.com/graphprotocol/rewards-eligibility-oracle"
    "/blob/main/ELIGIBILITY_CRITERIA.md#active-eligibility-criteria"
)

_ELIGIBILITY_CRITERIA_RAW = (
    "https://raw.githubusercontent.com/graphprotocol/rewards-eligibility-oracle"
    "/main/ELIGIBILITY_CRITERIA.md"
)

# Used only when the document cannot be fetched. Kept deliberately short: a
# stale criteria list is worse than an honest link, so the UI labels this as a
# fallback when it is used.
_ELIGIBILITY_CRITERIA_FALLBACK = [
    {"label": "Days Online", "detail": "Active for 5+ days in a given 28 day period.", "children": []},
    {"label": "Daily Query", "detail": "At least 1 qualifying query on each active day.", "children": []},
    {
        "label": "Query Quality",
        "detail": "A qualifying query must meet all of the following:",
        "children": [
            "HTTP status: 200 OK.",
            "Latency: under 5,000 ms.",
            "Freshness: fewer than 50,000 blocks behind chainhead.",
        ],
    },
]


def _strip_markdown(text: str) -> str:
    """Flatten the small subset of markdown used in the criteria bullets."""
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)   # links -> label
    text = text.replace("**", "").replace("*", "")
    return " ".join(text.split())


def fetch_eligibility_criteria() -> dict:
    """
    Fetch the Active Eligibility Criteria that the oracle actually applies.

    The criteria live in the oracle's own repository and change over time (the
    document carries an explicit "Upcoming" section), so they are read at
    generation time rather than hardcoded here. Indexers seeing stale
    requirements would be worse than showing none.

    Returns a dict with the parsed bullets, the canonical source URL, and
    whether the built-in fallback had to be used.
    """
    try:
        response = requests.get(_ELIGIBILITY_CRITERIA_RAW, timeout=15)
        response.raise_for_status()
        body = response.text
    except Exception as exc:                                  # noqa: BLE001
        print(f"⚠ Could not fetch eligibility criteria ({exc}); using built-in fallback.")
        return {
            "items": _ELIGIBILITY_CRITERIA_FALLBACK,
            "source_url": ELIGIBILITY_CRITERIA_URL,
            "is_fallback": True,
        }

    # Take only the "Active Eligibility Criteria" section, stopping at the next
    # heading or horizontal rule so the changelog below is never included.
    match = re.search(
        r"^##\s+Active Eligibility Criteria\s*$(.*?)^(?:##\s|---\s*$)",
        body,
        re.MULTILINE | re.DOTALL,
    )
    section = match.group(1) if match else ""

    items: List[dict] = []
    for line in section.splitlines():
        if re.match(r"^\s*-\s+", line):
            indent = len(line) - len(line.lstrip())
            text = _strip_markdown(re.sub(r"^\s*-\s+", "", line))
            if indent >= 2 and items:
                items[-1]["children"].append(text)
            else:
                # The source writes each rule as "Label: detail". Splitting them
                # lets the UI lead with the label and keep the block scannable
                # instead of presenting three full sentences.
                label, _, detail = text.partition(":")
                if detail.strip():
                    label = re.sub(r"\s*Requirements?$", "", label.strip())
                    items.append({"label": label, "detail": detail.strip(), "children": []})
                else:
                    items.append({"label": "", "detail": text, "children": []})

    if not items:
        print("⚠ Eligibility criteria document had no parsable bullets; using built-in fallback.")
        return {
            "items": _ELIGIBILITY_CRITERIA_FALLBACK,
            "source_url": ELIGIBILITY_CRITERIA_URL,
            "is_fallback": True,
        }

    print(f"✓ Fetched {len(items)} active eligibility criteria")
    return {"items": items, "source_url": ELIGIBILITY_CRITERIA_URL, "is_fallback": False}


def write_dashboard_data(environment_data: dict, output_dir: str) -> str:
    """
    Write the single JSON file that is the contract between the two halves of
    this project: Python fetches on-chain data, the React frontend renders it.

    Everything the UI needs lives here, so the frontend never has to reach into
    the working files at the repository root. Written atomically, because the
    renderer or a deploy may read it at any moment.
    """
    payload = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "eligibility_criteria": fetch_eligibility_criteria(),
        "environments": [],
    }

    for env_key, env_data in environment_data.items():
        config = env_data.get("config", {})
        contract_info = env_data.get("contract_info", {})

        # eligibility_period and the oracle update time are written into the
        # per-environment working file by checkEligibility(), so read them back
        # from there rather than duplicating the derivation here.
        env_meta = {}
        try:
            with open(f"active_indexers_{env_key}.json", encoding="utf-8") as handle:
                env_meta = json.load(handle).get("metadata", {})
        except (OSError, ValueError):
            pass

        payload["environments"].append({
            "id": env_key,
            "label": config.get("name", env_key),
            "network_id": str(config.get("network_id", "")),
            "contract_address": contract_info.get("address"),
            "deployment_block": contract_info.get("deployment_block"),
            "deployment_time": contract_info.get("deployment_time"),
            # eligibility_period is the oracle's renewal window in seconds
            # (1209600 = 14 days). The UI needs it to compute the grace
            # countdown, which the previous dashboard never displayed.
            "eligibility_period": env_meta.get("eligibility_period"),
            "last_oracle_update_time": env_meta.get("last_oracle_update_time"),
            "stats": env_data.get("stats", {}),
            "indexers": env_data.get("indexers", []),
        })

    data_path = os.path.join(output_dir, "data.json")
    _write_atomic(data_path, json.dumps(payload, indent=2))

    total = sum(len(e["indexers"]) for e in payload["environments"])
    print(f"Wrote {data_path} — {len(payload['environments'])} networks, {total} indexers")
    return data_path


def copy_gds_assets(output_dir: str) -> None:
    """
    Place the compiled GDS stylesheet and Euclid Circular fonts next to
    index.html so Caddy serves them. In Docker these come from the frontend
    build stage at /app/static/gds; locally, scripts/build_frontend.sh writes
    them straight into the output dir.
    """
    gds_src = '/app/static/gds'
    if os.path.isdir(gds_src):
        css_src = os.path.join(gds_src, 'gds.css')
        fonts_src = os.path.join(gds_src, 'fonts')
        if os.path.isfile(css_src):
            shutil.copy2(css_src, os.path.join(output_dir, 'gds.css'))
            print(f"Copied GDS stylesheet to {output_dir}/gds.css")
        if os.path.isdir(fonts_src):
            shutil.copytree(fonts_src, os.path.join(output_dir, 'fonts'), dirs_exist_ok=True)
            print(f"Copied GDS fonts to {output_dir}/fonts/")
    elif not os.path.isfile(os.path.join(output_dir, 'gds.css')):
        print("Info: compiled GDS assets not found. Run scripts/build_frontend.sh "
              "for local development, or build via Docker.")


def render_dashboard(output_dir: str) -> bool:
    """
    Render output/index.html from output/data.json via the prerenderer.

    The renderer is a self-contained bundle produced at image-build time, so no
    node_modules are needed here — only a node binary.

    A failed render is deliberately non-fatal: the previously rendered
    index.html keeps being served rather than being replaced by a blank or
    half-written page. Because the page displays its own "generated at"
    timestamp, a stalled render ages visibly instead of failing silently.
    """
    renderer = os.getenv('REO_RENDERER', os.path.join('frontend', 'scripts', 'prerender.mjs'))
    if not os.path.isfile(renderer):
        print(f"⚠ Renderer not found at {renderer}; leaving existing index.html untouched.")
        return False

    try:
        result = subprocess.run(
            ['node', renderer],
            capture_output=True,
            text=True,
            timeout=120,
            env={**os.environ, 'REO_OUTPUT_DIR': output_dir},
        )
    except FileNotFoundError:
        print("⚠ `node` is not available; leaving existing index.html untouched.")
        return False
    except subprocess.TimeoutExpired:
        print("⚠ Renderer timed out after 120s; leaving existing index.html untouched.")
        return False

    if result.returncode != 0:
        print(f"⚠ Renderer failed (exit {result.returncode}); "
              f"leaving existing index.html untouched.")
        if result.stderr:
            print(result.stderr.strip())
        return False

    if result.stdout:
        print(result.stdout.strip())
    return True


def _write_atomic(path: str, content: str) -> None:
    """
    Write via a temporary file in the same directory, then os.replace().

    os.replace() is atomic on POSIX, so a reader (Caddy, the renderer) never
    observes a partially written file.
    """
    directory = os.path.dirname(path) or '.'
    fd, tmp_path = tempfile.mkstemp(dir=directory, suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            handle.write(content)
        os.replace(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise

def main():
    """Main function to generate the multi-environment dashboard."""
    start_time = datetime.now(timezone.utc)
    print("=" * 70)
    print(f"Script started at {start_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 70)
    print()
    print("Generating Multi-Environment Eligibility Dashboard...")

    # Check if .env file exists
    env_file_path = '.env'
    if os.path.exists(env_file_path):
        print(f"✓ Loading environment variables from {env_file_path}")
        load_dotenv()
    else:
        print(f"⚠ Warning: {env_file_path} file not found!")
        print("  Using default/fallback configuration values.")
        print("  To use custom values:")
        print("    1. Copy .env.example to .env")
        print("    2. Edit .env with your API keys")
        print()

    # Load environment variables
    graph_api_key = os.getenv("GRAPH_API_KEY")
    use_cached_ens = os.getenv("USE_CACHED_ENS", "N").upper() == "Y"
    api_key = os.getenv("ARBISCAN_API_KEY")
    grace_buffer_hours = int(os.getenv("GRACE_BUFFER_PERIOD_HOURS", "24"))

    # Fallback contract address (if JSON fetch fails)
    fallback_contract_address = os.getenv("CONTRACT_ADDRESS")

    print("✓ Configuration loaded successfully")
    print()

    # Initialize ENVIRONMENTS with per-network RPC managers
    global ENVIRONMENTS
    ENVIRONMENTS = get_environments_config()

    # Validate we have at least one environment with a contract address
    valid_environments = {k: v for k, v in ENVIRONMENTS.items() if v.get('contract_address')}
    if not valid_environments:
        # Use fallback if no valid addresses from JSON
        if fallback_contract_address:
            print(f"⚠ Warning: No contract addresses from JSON, using fallback CONTRACT_ADDRESS")
            ENVIRONMENTS['testnet']['contract_address'] = fallback_contract_address
            valid_environments = {'testnet': ENVIRONMENTS['testnet']}
        else:
            print("❌ Error: No contract addresses available and no CONTRACT_ADDRESS fallback")
            return

    # Validate that each environment has RPC endpoints
    for env_key, env_config in list(valid_environments.items()):
        env_rpc = env_config.get('rpc_manager')
        if not env_rpc or not env_rpc.endpoints:
            print(f"⚠ Warning: No RPC endpoints for {env_key}, skipping")
            print(f"  Set RPC_ENDPOINT_{env_key.upper()} or RPC_ENDPOINT in your .env file")
            del valid_environments[env_key]

    if not valid_environments:
        print("❌ Error: No environments have RPC endpoints configured")
        print("Please set RPC_ENDPOINT_MAINNET and/or RPC_ENDPOINT_TESTNET in your .env file")
        return

    print(f"✓ Processing {len(valid_environments)} environment(s): {', '.join(valid_environments.keys())}")
    print()

    # Validate API key
    if not graph_api_key or graph_api_key == "your_graph_api_key_here":
        print("⚠ GRAPH_API_KEY not set, skipping active indexers retrieval")
        print()

    # Multi-environment data storage
    environment_data = {}

    # Process each environment
    for env_key, env_config in valid_environments.items():
        env_rpc_manager = env_config['rpc_manager']

        print("=" * 70)
        print(f"Processing {env_config['name']} (Network ID: {env_config['network_id']})")
        print(f"Contract: {env_config['contract_address']}")
        print("=" * 70)
        print()

        # Environment-specific file paths
        output_file = f"active_indexers_{env_key}.json"
        previous_file = f"active_indexers_{env_key}_previous_run.json"
        log_file = f"activity_log_indexers_status_changes_{env_key}.json"

        # Initialize environment data
        environment_data[env_key] = {
            "config": env_config,
            "indexers": [],
            "stats": {},
            "contract_info": {
                "address": env_config['contract_address'],
                "deployment_block": env_config.get('deployment_block'),
                "deployment_time": None
            }
        }

        # Get deployment timestamp if deployment block is known
        if env_config.get('deployment_block'):
            deployment_time = get_block_timestamp(env_rpc_manager, env_config['deployment_block'])
            environment_data[env_key]["contract_info"]["deployment_time"] = deployment_time
            if deployment_time:
                print(f"✓ Contract deployment time: {deployment_time}")

        # Retrieve active indexers for this environment
        if graph_api_key and graph_api_key != "your_graph_api_key_here":
            print()
            if use_cached_ens:
                print("🔄 ENS Cache Mode: ENABLED")
            else:
                print("🌐 ENS Cache Mode: DISABLED")
            print()

            transaction_hash = None
            if api_key and env_config['contract_address']:
                # Try to get last transaction for this environment
                last_transaction = get_last_transaction(
                    env_config['contract_address'], api_key,
                    chainid=str(env_config['network_id'])
                )
                if last_transaction:
                    transaction_hash = last_transaction.get("hash")

            retrieveActiveIndexers(
                graph_api_key,
                output_file=output_file,
                use_cached_ens=use_cached_ens,
                contract_address=env_config['contract_address'],
                rpc_manager=env_rpc_manager,
                transaction_hash=transaction_hash,
                network_id=env_key
            )
            print()

        # Check if indexer file was created
        if not os.path.exists(output_file):
            print(f"⚠ Warning: {output_file} not found, skipping {env_key}")
            continue

        # Read indexer data
        with open(output_file, 'r') as f:
            indexers_data = json.load(f)
            indexers = indexers_data.get('indexers', [])
            environment_data[env_key]["indexers"] = indexers

        print(f"Found {len(indexers)} indexers for {env_key}")

        # Check eligibility for this environment
        if env_config['contract_address']:
            checkEligibility(
                env_config['contract_address'],
                rpc_manager=env_rpc_manager,
                input_file=output_file,
                grace_buffer_hours=grace_buffer_hours,
                network_id=env_key
            )
            print()

        # Update status change dates
        updateStatusChangeDates(
            current_file=output_file,
            previous_file=previous_file,
            network_id=env_key
        )
        print()

        # Log status changes
        logStatusChanges(
            current_file=output_file,
            previous_file=previous_file,
            log_file=log_file,
            network_id=env_key
        )
        print()

        # Calculate stats
        # Re-read the file to get updated eligibility data
        with open(output_file, 'r') as f:
            updated_data = json.load(f)
            updated_indexers = updated_data.get('indexers', [])
            environment_data[env_key]["indexers"] = updated_indexers
            environment_data[env_key]["stats"] = calculate_stats(updated_indexers)

        print(f"✓ {env_key} stats: {environment_data[env_key]['stats']}")
        print()

    # Send Telegram notifications (only once, using testnet data)
    if TELEGRAM_AVAILABLE and 'testnet' in environment_data:
        try:
            print("Sending Telegram notifications...")
            # Temporarily copy testnet data to default location for notifier
            if os.path.exists('active_indexers_testnet.json'):
                import shutil
                shutil.copy('active_indexers_testnet.json', 'active_indexers.json')
                if os.path.exists('active_indexers_testnet_previous_run.json'):
                    shutil.copy('active_indexers_testnet_previous_run.json', 'active_indexers_previous_run.json')
                telegram_notifier.send_notifications()
            print()
        except Exception as e:
            print(f"⚠ Warning: Could not send Telegram notifications: {e}")
            print()
    else:
        print("ℹ️ Telegram notifications disabled (module not available)")
        print()

    # Generate HTML with all environment data
    print("=" * 70)
    print("Generating HTML dashboard...")
    print("=" * 70)
    print()

    # Use the first available environment's contract address and RPC manager
    first_env = list(environment_data.keys())[0] if environment_data else 'testnet'
    if first_env in environment_data:
        env_data = environment_data[first_env]
        contract_address = env_data['contract_info']['address']
        first_env_rpc = valid_environments[first_env]['rpc_manager'] if first_env in valid_environments else None
        first_env_chainid = str(env_data['config']['network_id'])
        print(f"Using {first_env} contract address: {contract_address}")
    else:
        # Fallback to environment variable
        contract_address = os.getenv("CONTRACT_ADDRESS", "")
        first_env_rpc = None
        first_env_chainid = "421614"

    output_dir = os.getenv('REO_OUTPUT_DIR', 'output')
    os.makedirs(output_dir, exist_ok=True)

    write_dashboard_data(environment_data, output_dir)
    copy_gds_assets(output_dir)
    render_dashboard(output_dir)

    # Log execution time
    end_time = datetime.now(timezone.utc)
    duration = (end_time - start_time).total_seconds()
    print()
    print("=" * 70)
    print(f"Script completed at {end_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"Total execution time: {duration:.2f} seconds ({duration/60:.2f} minutes)")
    print("=" * 70)


if __name__ == "__main__":
    main()
