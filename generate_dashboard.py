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
from datetime import datetime, timezone
from typing import List, Tuple, Optional
from dotenv import load_dotenv
import threading

# Import database module
from database import (
    save_indexers, get_all_indexers, update_eligibility, log_status_change,
    get_previous_indexers, update_status_changes, save_ens_cache, load_ens_cache,
    save_transaction, get_last_transaction, update_sync_state, set_metadata, get_metadata
)

# Version of the dashboard generator
VERSION = "0.0.19"


class RoundRobinRPC:
    """
    Round-robin RPC endpoint manager.
    Cycles through multiple RPC endpoints for load balancing and failover.
    """
    def __init__(self):
        self.endpoints = []
        self.current_index = 0
        self.lock = threading.Lock()
        self._load_endpoints()
    
    def _load_endpoints(self):
        """Load RPC endpoints from environment variables."""
        # Try RPC_ENDPOINT first (backward compatibility)
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
        
        if not self.endpoints:
            print("⚠ Warning: No RPC endpoints found in environment variables")
        else:
            print(f"✓ Loaded {len(self.endpoints)} RPC endpoint(s) for round-robin")
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
    return get_last_transaction()


def save_transaction_to_json(transaction_data: dict, json_file: str = 'last_transaction.json') -> None:
    """Wrapper: now uses database instead of JSON file."""
    if save_transaction(transaction_data):
        print(f"✓ Transaction data saved to database")
    else:
        print(f"⚠ Failed to save transaction data")


def get_last_transaction(contract_address: str, api_key: str) -> Optional[dict]:
    """
    Get the last transaction for a contract from Arbiscan API (Sepolia).
    Uses Etherscan API V2 endpoint with txlist action, descending sort, and limit 1 for efficiency.
    
    Args:
        contract_address: The contract address to query
        api_key: Arbiscan/Etherscan API key
        
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
        "chainid": "421614",  # Arbitrum Sepolia chain ID
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


def retrieveActiveIndexers(graph_api_key: str, output_file: str = 'active_indexers.json', use_cached_ens: bool = False, contract_address: Optional[str] = None, rpc_manager: Optional[RoundRobinRPC] = None, transaction_hash: Optional[str] = None) -> bool:
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
                "transaction_hash": transaction_hash if transaction_hash else None
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
        
        # Process each indexer without ENS name
        for indexer in indexers_raw:
            address = indexer.get("id", "")
            
            # Get previous last_renewed_on_tx value if exists
            previous_tx = previous_indexers_map.get(address.lower(), "")
            
            indexer_data = {
                "address": address,
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


def checkEligibility(contract_address: str, rpc_manager: Optional[RoundRobinRPC] = None, input_file: str = 'active_indexers.json', grace_buffer_hours: int = 24) -> bool:
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
            elif eligibility_renewal_time < grace_buffer_cutoff and eligibility_period and eligibility_renewal_time > 0:
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
        
        # Write updated data back to JSON file
        with open(input_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        
        print(f"✓ Eligibility check complete:")
        print(f"  - Total indexers: {len(indexers)}")
        print(f"  - Eligible indexers: {eligible_count}")
        print(f"  - Renewal times retrieved: {updated_count}")
        print(f"  - Status breakdown: {eligible_status_count} eligible, {grace_status_count} grace, {ineligible_status_count} ineligible")
        print(f"✓ Results written to {input_file}")
        return True
        
    except Exception as e:
        print(f"Error in checkEligibility: {e}")
        return False


def updateStatusChangeDates(current_file: str = 'active_indexers.json', previous_file: str = 'active_indexers_previous_run.json') -> bool:
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


def logStatusChanges(current_file: str = 'active_indexers.json', previous_file: str = 'active_indexers_previous_run.json', log_file: str = 'activity_log_indexers_status_changes.json') -> bool:
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


def renderIndexerTable(json_file: str = 'active_indexers.json') -> List[dict]:
    """
    Read all indexers from the active_indexers.json file and merge with ENS data.
    Returns all indexers regardless of eligibility status.
    
    Args:
        json_file: Path to the active_indexers.json file
        
    Returns:
        List of dictionaries containing all indexer data with ENS names
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


def generate_html_dashboard(indexers: List[Tuple[str, str]], contract_address: str, api_key: Optional[str] = None, rpc_manager: Optional[RoundRobinRPC] = None) -> str:
    """
    Generate the HTML dashboard content.
    
    Args:
        indexers: List of (address, ens_name) tuples (legacy parameter, not used)
        contract_address: The Sepolia contract address
        api_key: Arbiscan API key
        
    Returns:
        Complete HTML content as string
    """
    current_time = datetime.now(timezone.utc).strftime("%d %b %Y at %H:%M (UTC)")
    
    # Load all indexers from JSON file
    print("Loading indexers for dashboard...")
    all_indexers = renderIndexerTable()
    
    # Fetch last transaction data
    print("Fetching last transaction data...")
    last_transaction: Optional[dict] = None
    
    # Fetch via Arbiscan API
    if api_key:
        last_transaction = get_last_transaction(contract_address, api_key)
    
    # Fallback: load from local JSON file (cached data)
    if not last_transaction:
        print("⚠ Warning: Could not fetch fresh transaction data from API, using cached data")
        last_transaction = get_last_transaction_from_json()
    
    # Save transaction data with script run timestamp
    if last_transaction:
        save_transaction_to_json(last_transaction)
    
    # Fetch oracle update time from contract
    print("Fetching oracle update time from contract...")
    oracle_update_time: Optional[int] = None
    if rpc_manager is None:
        rpc_manager = get_rpc_manager()
    if rpc_manager.endpoints:
        oracle_update_time = get_oracle_update_time(contract_address, rpc_manager)
    
    # Fetch eligibility period from contract
    print("Fetching eligibility period from contract...")
    eligibility_period: Optional[int] = None
    if rpc_manager.endpoints:
        eligibility_period = get_eligibility_period(contract_address, rpc_manager)
    
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Eligibility Dashboard</title>
    <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600&display=swap" rel="stylesheet">
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: 'Poppins', 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #0C0A1D;
            min-height: 100vh;
            padding: 20px;
        }}
        
        .breadcrumb {{
            max-width: 1200px;
            margin: 0 auto 15px auto;
            padding: 12px 20px;
            background: rgba(12, 10, 29, 0.6);
            border-radius: 8px;
            border: 1px solid #9CA3AF;
            color: #F8F6FF;
            font-size: 14px;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        
        .breadcrumb a {{
            color: #9CA3AF;
            text-decoration: none;
            transition: color 0.3s ease;
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }}
        
        .breadcrumb a:hover {{
            color: #F8F6FF;
        }}
        
        .breadcrumb-separator {{
            color: #9CA3AF;
            margin: 0 4px;
            font-weight: 300;
        }}
        
        .home-icon {{
            width: 16px;
            height: 16px;
            display: inline-block;
            position: relative;
        }}
        
        .home-icon::before {{
            content: '';
            position: absolute;
            left: 50%;
            top: 0;
            transform: translateX(-50%);
            width: 0;
            height: 0;
            border-left: 8px solid transparent;
            border-right: 8px solid transparent;
            border-bottom: 8px solid currentColor;
        }}
        
        .home-icon::after {{
            content: '';
            position: absolute;
            left: 2px;
            bottom: 0;
            width: 12px;
            height: 9px;
            background-color: currentColor;
        }}
        
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: #0C0A1D;
            border-radius: 15px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.3);
            overflow: hidden;
            border: 1px solid #9CA3AF;
        }}
        
        .header {{
            background: #0C0A1D;
            color: #F8F6FF;
            padding: 30px;
            border-bottom: 1px solid #9CA3AF;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }}
        
        .title-container {{
            display: flex;
            align-items: center;
            gap: 15px;
        }}
        
        .header-icon {{
            width: 50px;
            height: 50px;
            object-fit: contain;
        }}
        
        .header h1 {{
            font-size: 2.2em;
            margin: 0;
            font-weight: 300;
        }}
        
        .header .subtitle {{
            font-size: 0.95em;
            opacity: 0.9;
            font-weight: 300;
            white-space: nowrap;
        }}
        
        .search-container {{
            padding: 25px 30px;
            background: #0C0A1D;
            border-bottom: 1px solid #9CA3AF;
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 20px;
            flex-wrap: wrap;
        }}
        
        .search-wrapper {{
            flex: 0 0 45%;
            min-width: 300px;
            max-width: 500px;
        }}
        
        .search-box {{
            width: 100%;
            padding: 15px 20px;
            border: 2px solid #9CA3AF;
            border-radius: 25px;
            font-size: 16px;
            outline: none;
            transition: all 0.3s ease;
            background: #0C0A1D;
            color: #F8F6FF;
        }}
        
        .search-box:focus {{
            border-color: #F8F6FF;
            box-shadow: 0 0 0 3px rgba(248, 246, 255, 0.1);
        }}
        
        .search-box::placeholder {{
            color: #9CA3AF;
        }}
        
        .filter-wrapper {{
            display: flex;
            align-items: center;
            gap: 10px;
            flex-wrap: wrap;
        }}
        
        .legend {{
            padding: 20px 30px;
            background: #0C0A1D;
            border-bottom: 1px solid #9CA3AF;
        }}
        
        .legend-title {{
            color: #F8F6FF;
            font-size: 14px;
            font-weight: 600;
            margin-bottom: 10px;
            text-align: center;
        }}
        
        .legend-items {{
            display: flex;
            gap: 20px;
            flex-wrap: wrap;
            justify-content: center;
        }}
        
        .legend-item {{
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 13px;
        }}
        
        .legend-badge {{
            padding: 4px 12px;
            border-radius: 12px;
            font-weight: 500;
            font-size: 11px;
        }}
        
        .legend-badge.good {{
            background: rgba(34, 197, 94, 0.2);
            color: #22c55e;
            border: 1px solid #22c55e;
        }}
        
        .legend-badge.grace {{
            background: rgba(251, 191, 36, 0.2);
            color: #fbbf24;
            border: 1px solid #fbbf24;
        }}
        
        .legend-badge.ineligible {{
            background: rgba(239, 68, 68, 0.2);
            color: #ef4444;
            border: 1px solid #ef4444;
        }}
        
        .legend-description {{
            color: #9CA3AF;
        }}
        
        .gip-banner {{
            padding: 15px 30px;
            background: #0C0A1D;
            border-bottom: 1px solid #9CA3AF;
            text-align: center;
            font-size: 14px;
            color: #9CA3AF;
        }}
        
        .gip-banner a {{
            color: #9CA3AF;
            text-decoration: none;
            transition: color 0.3s ease;
        }}
        
        .gip-banner a:hover {{
            color: #F8F6FF;
            text-decoration: underline;
        }}
        
        .counters-section {{
            padding: 25px 30px;
            background: #0C0A1D;
            border-bottom: 1px solid #9CA3AF;
            display: flex;
            justify-content: space-around;
            align-items: center;
            flex-wrap: wrap;
            gap: 20px;
            overflow: visible;
        }}
        
        .counter-item {{
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 8px;
            position: relative;
        }}
        
        .counter-label {{
            color: #9CA3AF;
            font-size: 14px;
            font-weight: 500;
            text-align: center;
            cursor: help;
            position: relative;
        }}
        
        .counter-label[data-tooltip]::after {{
            content: attr(data-tooltip);
            position: absolute;
            bottom: 100%;
            left: 50%;
            transform: translateX(-50%);
            margin-bottom: 8px;
            padding: 8px 12px;
            background: #1a1825;
            color: #F8F6FF;
            font-size: 12px;
            font-weight: 400;
            white-space: nowrap;
            border-radius: 6px;
            opacity: 0;
            pointer-events: none;
            transition: opacity 0.2s ease;
            border: 1px solid #9CA3AF;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
            z-index: 9999;
        }}
        
        .counter-label[data-tooltip]:hover::after {{
            opacity: 1;
        }}
        
        .counter-label[data-tooltip]::before {{
            content: '';
            position: absolute;
            bottom: 100%;
            left: 50%;
            transform: translateX(-50%);
            margin-bottom: 2px;
            border: 6px solid transparent;
            border-top-color: #9CA3AF;
            opacity: 0;
            pointer-events: none;
            transition: opacity 0.2s ease;
            z-index: 9999;
        }}
        
        .counter-label[data-tooltip]:hover::before {{
            opacity: 1;
        }}
        
        .counter-value {{
            color: #F8F6FF;
            font-size: 32px;
            font-weight: 600;
            text-align: center;
        }}
        
        .counter-value.eligible-count {{
            color: #22c55e;
        }}
        
        .counter-value.grace-count {{
            color: #eab308;
        }}
        
        .counter-value.ineligible-count {{
            color: #ef4444;
        }}
        
        .filter-label {{
            color: #9CA3AF;
            font-size: 14px;
            font-weight: 500;
            margin-right: 5px;
        }}
        
        .filter-btn {{
            padding: 6px 14px;
            border-radius: 12px;
            font-weight: 500;
            font-size: 12px;
            border: none;
            cursor: pointer;
            transition: all 0.3s ease;
            position: relative;
        }}
        
        .filter-btn:hover {{
            opacity: 0.8;
            transform: translateY(-1px);
        }}
        
        .filter-btn[data-tooltip]::after {{
            content: attr(data-tooltip);
            position: absolute;
            bottom: 100%;
            left: 50%;
            transform: translateX(-50%);
            margin-bottom: 8px;
            padding: 8px 12px;
            background: #1a1825;
            color: #F8F6FF;
            font-size: 12px;
            font-weight: 400;
            white-space: nowrap;
            border-radius: 6px;
            opacity: 0;
            pointer-events: none;
            transition: opacity 0.2s ease;
            border: 1px solid #9CA3AF;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
            z-index: 9999;
        }}
        
        .filter-btn[data-tooltip]:hover::after {{
            opacity: 1;
        }}
        
        .filter-btn[data-tooltip]::before {{
            content: '';
            position: absolute;
            bottom: 100%;
            left: 50%;
            transform: translateX(-50%);
            margin-bottom: 2px;
            border: 6px solid transparent;
            border-top-color: #9CA3AF;
            opacity: 0;
            pointer-events: none;
            transition: opacity 0.2s ease;
            z-index: 9999;
        }}
        
        .filter-btn[data-tooltip]:hover::before {{
            opacity: 1;
        }}
        
        .filter-btn.eligible {{
            background: rgba(34, 197, 94, 0.2);
            color: #22c55e;
            border: 1px solid #22c55e;
        }}
        
        .filter-btn.eligible.active {{
            background: #22c55e;
            color: #0C0A1D;
        }}
        
        .filter-btn.grace {{
            background: rgba(251, 191, 36, 0.2);
            color: #fbbf24;
            border: 1px solid #fbbf24;
        }}
        
        .filter-btn.grace.active {{
            background: #fbbf24;
            color: #0C0A1D;
        }}
        
        .filter-btn.ineligible {{
            background: rgba(239, 68, 68, 0.2);
            color: #ef4444;
            border: 1px solid #ef4444;
        }}
        
        .filter-btn.ineligible.active {{
            background: #ef4444;
            color: #0C0A1D;
        }}
        
        .filter-btn.reset {{
            background: rgba(156, 163, 175, 0.2);
            color: #9CA3AF;
            border: 1px solid #9CA3AF;
        }}
        
        .filter-btn.reset:hover {{
            background: rgba(156, 163, 175, 0.3);
        }}
        
        .table-container {{
            padding: 0 30px 30px;
            overflow-x: auto;
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
            background: #0C0A1D;
            border-radius: 10px;
            overflow: hidden;
            box-shadow: 0 5px 15px rgba(0,0,0,0.3);
            border: 1px solid #9CA3AF;
        }}
        
        th {{
            background: #0C0A1D;
            color: #9CA3AF;
            padding: 20px 15px;
            text-align: left;
            font-weight: 600;
            font-size: 14px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            cursor: pointer;
            user-select: none;
            position: relative;
            border-bottom: 1px solid #9CA3AF;
        }}
        
        th:hover {{
            background: #1a1825;
        }}
        
        th.sortable::after {{
            content: ' ↕';
            opacity: 0.5;
            font-size: 12px;
        }}
        
        th.sort-asc::after {{
            content: ' ↑';
            opacity: 1;
        }}
        
        th.sort-desc::after {{
            content: ' ↓';
            opacity: 1;
        }}
        
        td {{
            padding: 18px 15px;
            border-bottom: 1px solid #9CA3AF;
            font-size: 14px;
            color: #F8F6FF;
        }}
        
        /* Date hover tooltip styles */
        .date-hover {{
            position: relative;
            cursor: help;
        }}
        
        .date-hover[data-full-date]:hover::after {{
            content: attr(data-full-date);
            position: absolute;
            bottom: 100%;
            left: 50%;
            transform: translateX(-50%);
            margin-bottom: 8px;
            padding: 8px 12px;
            background: #1a1825;
            color: #F8F6FF;
            font-size: 12px;
            font-weight: 400;
            white-space: nowrap;
            border-radius: 6px;
            border: 1px solid #9CA3AF;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
            z-index: 1000;
            pointer-events: none;
        }}
        
        .date-hover[data-full-date]:hover::before {{
            content: '';
            position: absolute;
            bottom: 100%;
            left: 50%;
            transform: translateX(-50%);
            margin-bottom: 2px;
            border: 6px solid transparent;
            border-top-color: #9CA3AF;
            z-index: 1000;
            pointer-events: none;
        }}
        
        tr:hover {{
            background-color: #1a1825;
        }}
        
        tr:nth-child(even) {{
            background-color: #0C0A1D;
        }}
        
        tr:nth-child(even):hover {{
            background-color: #1a1825;
        }}
        
        .address {{
            font-family: 'Courier New', monospace;
            font-size: 13px;
            color: #F8F6FF;
            word-break: break-all;
        }}
        
        .address-link {{
            text-decoration: none;
            transition: opacity 0.3s ease;
            display: inline-flex;
            align-items: center;
            gap: 5px;
        }}
        
        .address-link:hover .address {{
            color: #9CA3AF;
        }}
        
        .external-link-icon {{
            width: 12px;
            height: 12px;
            opacity: 0.8;
            transition: opacity 0.3s ease;
            color: #9CA3AF;
        }}
        
        .address-link:hover .external-link-icon {{
            opacity: 1;
        }}
        
        .ens-name {{
            color: #F8F6FF;
            font-weight: 500;
        }}
        
        .empty-ens {{
            color: #9CA3AF;
            font-style: italic;
        }}
        
        .stats {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 20px 30px;
            background: #0C0A1D;
            border-top: 1px solid #9CA3AF;
            font-size: 14px;
            color: #F8F6FF;
        }}
        
        .total-count {{
            font-weight: 600;
            color: #F8F6FF;
        }}
        
        .filtered-count {{
            color: #F8F6FF;
        }}
        
        .transaction-hash {{
            color: #F8F6FF;
            text-decoration: none;
            transition: color 0.3s ease;
            display: inline-flex;
            align-items: center;
            gap: 5px;
        }}
        
        .transaction-hash:hover {{
            color: #9CA3AF;
        }}
        
        .transaction-hash:hover .external-link-icon {{
            opacity: 1;
        }}
        
        .footer {{
            padding: 20px 30px;
            background: #0C0A1D;
            color: #9CA3AF;
            font-size: 14px;
            margin-top: 0;
        }}
        
        .footer-content {{
            max-width: 1140px;
            margin: 0 auto;
        }}
        
        .footer-top {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
            flex-wrap: wrap;
            gap: 10px;
        }}
        
        .footer-left {{
            text-align: left;
            flex: 0 0 auto;
        }}
        
        .footer-right {{
            text-align: right;
            flex: 0 0 auto;
        }}
        
        .footer a {{
            color: #9CA3AF;
            text-decoration: none;
            transition: color 0.3s ease;
        }}
        
        .footer a:hover {{
            color: #F8F6FF;
            text-decoration: underline;
        }}
        
        .version {{
            font-weight: 600;
            color: #9CA3AF;
        }}
        
        .footer-separator {{
            color: #9CA3AF;
        }}
        
        .github-icon {{
            display: inline-block;
            width: 16px;
            height: 16px;
            vertical-align: middle;
            margin-right: 5px;
        }}
        
        .bell-icon {{
            fill: #F8F6FF;
            width: 16px;
            height: 16px;
            vertical-align: middle;
            margin-right: 5px;
        }}
        
        @media (max-width: 768px) {{
            .container {{
                margin: 10px;
                border-radius: 10px;
            }}
            
            .header {{
                padding: 20px;
                flex-direction: column;
                align-items: flex-start;
                gap: 15px;
            }}
            
            .title-container {{
                gap: 10px;
            }}
            
            .header-icon {{
                width: 40px;
                height: 40px;
            }}
            
            .header h1 {{
                font-size: 1.8em;
            }}
            
            .search-container, .table-container {{
                padding: 20px;
            }}
            
            .footer-top {{
                flex-direction: column;
                align-items: flex-start;
                gap: 12px;
            }}
            
            .footer-left,
            .footer-right {{
                text-align: left;
                width: 100%;
            }}
            
            .counters-section {{
                flex-direction: column;
                padding: 20px;
            }}
            
            .stats {{
                flex-direction: column;
                gap: 10px;
                text-align: center;
            }}
        }}
    </style>
</head>
<body>
    <div class="breadcrumb">
        <a href="../index.html">
            <span class="home-icon"></span>
            <b>Home</b>
        </a>
        <span class="breadcrumb-separator">>></span>
        <span>REO Eligibility Dashboard</span>
    </div>
    
    <div class="container">
        <div class="header">
            <div class="title-container">
                <img src="grt.png" alt="GRT" class="header-icon">
                <h1>Eligibility Dashboard</h1>
            </div>
            <div class="subtitle">Last Update: {current_time}</div>
        </div>"""
    
    # Calculate counters
    total_indexers = len(all_indexers)
    eligible_count = sum(1 for indexer in all_indexers if indexer.get("status") == "eligible-active")
    grace_count = sum(1 for indexer in all_indexers if indexer.get("status") == "eligible-grace")
    ineligible_count = sum(1 for indexer in all_indexers if indexer.get("status") in ["ineligible-expired", "ineligible-unqualified"])
    
    html_content += f"""
        
        <div class="gip-banner">
            <svg class="bell-icon" viewBox="0 0 24 24" fill="currentColor"><path d="M12 22c1.1 0 2-.9 2-2h-4c0 1.1.9 2 2 2zm6-6v-5c0-3.07-1.63-5.64-4.5-6.32V4c0-.83-.67-1.5-1.5-1.5s-1.5.67-1.5 1.5v.68C7.64 5.36 6 7.92 6 11v5l-2 2v1h16v-1l-2-2zm-2 1H8v-6c0-2.48 1.51-4.5 4-4.5s4 2.02 4 4.5v6z"/></svg><a href="https://t.me/reo_dashboard_bot" target="_blank">Subscribe to real-time notifications on Telegram</a>
        </div>
        
        <div class="counters-section">
            <div class="counter-item">
                <span class="counter-label" data-tooltip="Active indexers in The Graph Network">Active Indexers</span>
                <span class="counter-value">{total_indexers}</span>
            </div>
            <div class="counter-item">
                <span class="counter-label" data-tooltip="Eligible (Active): Indexers who are fully compliant">Eligible Indexers (Active)</span>
                <span class="counter-value eligible-count">{eligible_count}</span>
            </div>
            <div class="counter-item">
                <span class="counter-label" data-tooltip="Eligible (Grace): Indexers still eligible for rewards but need to renew soon to stay compliant">Eligible Indexers (Grace)</span>
                <span class="counter-value grace-count">{grace_count}</span>
            </div>
            <div class="counter-item">
                <span class="counter-label" data-tooltip="Ineligible: Either expired (previously eligible) or unqualified (never been eligible)">Ineligible Indexers</span>
                <span class="counter-value ineligible-count">{ineligible_count}</span>
            </div>
        </div>
        
        <div class="search-container">
            <div class="search-wrapper">
                <input type="text" 
                       class="search-box" 
                       id="searchInput" 
                       placeholder="Search by indexer address or ENS name..."
                       autocomplete="off">
            </div>
            <div class="filter-wrapper">
                <span class="filter-label">Filter by Status:</span>
                <button class="filter-btn eligible" onclick="filterByStatus('eligible')" data-tooltip="Fully compliant indexers">Eligible - Active</button>"""
    
    # Add grace period tooltip if eligibility_period is available
    grace_tooltip = ""
    if eligibility_period:
        days = int(eligibility_period / 86400)
        grace_tooltip = f' data-tooltip="Still eligible but need to renew within {days} days"'
    else:
        grace_tooltip = ' data-tooltip="Still eligible but need to renew soon"'
    
    html_content += f"""
                <button class="filter-btn grace" onclick="filterByStatus('grace')"{grace_tooltip}>Eligible - Grace</button>
                <button class="filter-btn ineligible" onclick="filterByStatus('ineligible')" data-tooltip="Expired (previously eligible) or Unqualified (never eligible)">Ineligible</button>
                <button class="filter-btn reset" onclick="resetFilter()" data-tooltip="Show All">Reset</button>
            </div>
        </div>
        
        <div class="table-container">
            <table id="indexersTable">
                <thead>
                    <tr>
                        <th class="sortable" data-column="0">Indexer Address</th>
                        <th class="sortable" data-column="1">ENS Name</th>
                        <th class="sortable" data-column="2">Status</th>
                        <th class="sortable" data-column="3">Last Renewed</th>
                        <th class="sortable" data-column="4">Eligible Until</th>
                    </tr>
                </thead>
                <tbody id="tableBody">
"""

    # Sort indexers: first by status (eligible-active, eligible-grace, ineligible-expired, ineligible-unqualified), then by ENS name
    def sort_key(indexer):
        status = indexer.get("status", "ineligible-unqualified")
        ens_name = indexer.get("ens_name", "")
        # Status order: eligible-active (0), eligible-grace (1), ineligible-expired (2), ineligible-unqualified (3), then by ENS (empty ENS last)
        status_priority = {"eligible-active": 0, "eligible-grace": 1, "ineligible-expired": 2, "ineligible-unqualified": 3}
        return (status_priority.get(status, 4), ens_name.lower() if ens_name else "zzzzzzzzz")
    
    all_indexers_sorted = sorted(all_indexers, key=sort_key)

    # Add table rows from sorted indexers
    for i, indexer in enumerate(all_indexers_sorted, 1):
        address = indexer.get("address", "")
        ens_name = indexer.get("ens_name", "")
        status = indexer.get("status", "ineligible")
        ens_display = ens_name if ens_name else "No ENS"
        ens_class = "ens-name" if ens_name else "empty-ens"
        explorer_url = f"https://thegraph.com/explorer/profile/{address}?view=Indexing&chain=arbitrum-one"
        
        # Get date formats
        eligibility_renewal_time_short = indexer.get("eligibility_renewal_time_short", "Never")
        eligibility_renewal_time_readable = indexer.get("eligibility_renewal_time_readable", "Never")
        eligible_until_short = indexer.get("eligible_until_short", "")
        eligible_until_readable = indexer.get("eligible_until_readable", "")
        last_renewed_on_tx = indexer.get("last_renewed_on_tx", "")
        
        # Set status badge based on status
        if status == "eligible-active":
            status_badge = '<span class="legend-badge good">Active</span>'
        elif status == "eligible-grace":
            status_badge = '<span class="legend-badge grace">Eligible - Grace</span>'
        elif status == "ineligible-expired":
            status_badge = '<span class="legend-badge ineligible">Expired</span>'
        else:  # ineligible-unqualified
            status_badge = '<span class="legend-badge ineligible">Unqualified</span>'
        
        # Format Last Renewed cell with transaction link (no tooltip)
        if eligibility_renewal_time_short == "Never":
            last_renewed_cell = eligibility_renewal_time_short
        else:
            # If we have a transaction hash, make the date a link with external icon
            if last_renewed_on_tx:
                last_renewed_cell = f'<a href="https://sepolia.arbiscan.io/tx/{last_renewed_on_tx}" target="_blank" class="transaction-hash">{eligibility_renewal_time_short}<svg class="external-link-icon" viewBox="0 0 16 16" fill="currentColor"><path d="M14 2.5a.5.5 0 0 0-.5-.5h-6a.5.5 0 0 0 0 1h4.793L8.146 7.146a.5.5 0 0 0 .708.708L13 3.707V8.5a.5.5 0 0 0 1 0v-6z"/><path d="M4.5 4a.5.5 0 0 0-.5.5v8a.5.5 0 0 0 .5.5h8a.5.5 0 0 0 .5-.5V9a.5.5 0 0 0-1 0v3H5V5h3a.5.5 0 0 0 0-1h-3.5z"/></svg></a>'
            else:
                last_renewed_cell = eligibility_renewal_time_short
        
        # Format Eligible Until cell with hover tooltip
        if eligible_until_short:
            eligible_until_cell = f'<span class="date-hover" data-full-date="{eligible_until_readable}">{eligible_until_short}</span>'
        else:
            eligible_until_cell = ""
        
        html_content += f"""                    <tr>
                        <td><a href="{explorer_url}" target="_blank" class="address-link"><span class="address">{address}</span><svg class="external-link-icon" viewBox="0 0 16 16" fill="currentColor"><path d="M14 2.5a.5.5 0 0 0-.5-.5h-6a.5.5 0 0 0 0 1h4.793L8.146 7.146a.5.5 0 0 0 .708.708L13 3.707V8.5a.5.5 0 0 0 1 0v-6z"/><path d="M4.5 4a.5.5 0 0 0-.5.5v8a.5.5 0 0 0 .5.5h8a.5.5 0 0 0 .5-.5V9a.5.5 0 0 0-1 0v3H5V5h3a.5.5 0 0 0 0-1h-3.5z"/></svg></a></td>
                        <td><span class="{ens_class}">{ens_display}</span></td>
                        <td>{status_badge}</td>
                        <td>{last_renewed_cell}</td>
                        <td>{eligible_until_cell}</td>
                    </tr>
"""

    html_content += """                </tbody>
            </table>
        </div>
        
        <div class="stats">
            <div class="total-count">Total Indexers: <span id="totalCount">""" + str(len(all_indexers)) + """</span></div>
            <div class="filtered-count">Showing: <span id="filteredCount">""" + str(len(all_indexers)) + """</span></div>
        </div>
    </div>

    <script>
        // Table data
        const originalData = [
"""

    # Sort indexers: first by status (eligible-active, eligible-grace, ineligible-expired, ineligible-unqualified), then by ENS name
    def sort_key(indexer):
        status = indexer.get("status", "ineligible-unqualified")
        ens_name = indexer.get("ens_name", "")
        # Status order: eligible-active (0), eligible-grace (1), ineligible-expired (2), ineligible-unqualified (3), then by ENS (empty ENS last)
        status_priority = {"eligible-active": 0, "eligible-grace": 1, "ineligible-expired": 2, "ineligible-unqualified": 3}
        return (status_priority.get(status, 4), ens_name.lower() if ens_name else "zzzzzzzzz")
    
    all_indexers_sorted = sorted(all_indexers, key=sort_key)

    # Add JavaScript data from all indexers
    for indexer in all_indexers_sorted:
        address = indexer.get("address", "")
        ens_name = indexer.get("ens_name", "")
        status = indexer.get("status", "ineligible")
        eligibility_renewal_time_short = indexer.get("eligibility_renewal_time_short", "Never")
        eligibility_renewal_time_readable = indexer.get("eligibility_renewal_time_readable", "Never")
        eligible_until_short = indexer.get("eligible_until_short", "")
        eligible_until_readable = indexer.get("eligible_until_readable", "")
        last_renewed_on_tx = indexer.get("last_renewed_on_tx", "")
        
        # Set status badge based on status
        if status == "eligible-active":
            status_badge = '<span class="legend-badge good">Active</span>'
        elif status == "eligible-grace":
            status_badge = '<span class="legend-badge grace">Eligible - Grace</span>'
        elif status == "ineligible-expired":
            status_badge = '<span class="legend-badge ineligible">Expired</span>'
        else:  # ineligible-unqualified
            status_badge = '<span class="legend-badge ineligible">Unqualified</span>'
        
        html_content += f"""            ["{address}", "{ens_name}", '{status_badge}', "{eligibility_renewal_time_short}", "{eligibility_renewal_time_readable}", "{eligible_until_short}", "{eligible_until_readable}", "{status}", "{last_renewed_on_tx}"],
"""

    html_content += """        ];
        
        let currentData = [...originalData];
        let sortColumn = -1;
        let sortDirection = 'asc';
        let activeFilter = null;
        
        // Search functionality
        const searchInput = document.getElementById('searchInput');
        const tableBody = document.getElementById('tableBody');
        const totalCount = document.getElementById('totalCount');
        const filteredCount = document.getElementById('filteredCount');
        
        // Apply both search and filter
        function applyFilters() {
            const searchTerm = searchInput.value.toLowerCase();
            
            currentData = originalData.filter(row => {
                // Check search term
                const matchesSearch = row[0].toLowerCase().includes(searchTerm) || 
                                     row[1].toLowerCase().includes(searchTerm);
                
                // Check status filter (row[7] is the status string)
                // Map filter buttons to actual status values
                let matchesFilter = true;
                if (activeFilter) {
                    if (activeFilter === 'eligible') {
                        matchesFilter = row[7] === 'eligible-active';
                    } else if (activeFilter === 'grace') {
                        matchesFilter = row[7] === 'eligible-grace';
                    } else if (activeFilter === 'ineligible') {
                        matchesFilter = row[7] === 'ineligible-expired' || row[7] === 'ineligible-unqualified';
                    }
                }
                
                return matchesSearch && matchesFilter;
            });
            
            renderTable();
            updateStats();
        }
        
        searchInput.addEventListener('input', applyFilters);
        
        // Filter by status functionality
        function filterByStatus(status) {
            // Toggle filter
            if (activeFilter === status) {
                activeFilter = null;
                // Remove active class from all buttons
                document.querySelectorAll('.filter-btn').forEach(btn => btn.classList.remove('active'));
            } else {
                activeFilter = status;
                // Remove active class from all buttons
                document.querySelectorAll('.filter-btn').forEach(btn => btn.classList.remove('active'));
                // Add active class to clicked button
                document.querySelector(`.filter-btn.${status}`).classList.add('active');
            }
            
            applyFilters();
        }
        
        // Reset filter
        function resetFilter() {
            activeFilter = null;
            searchInput.value = '';
            // Remove active class from all buttons
            document.querySelectorAll('.filter-btn').forEach(btn => btn.classList.remove('active'));
            applyFilters();
        }
        
        // Sorting functionality
        function sortTable(column) {
            if (sortColumn === column) {
                sortDirection = sortDirection === 'asc' ? 'desc' : 'asc';
            } else {
                sortColumn = column;
                sortDirection = 'asc';
            }
            
            // Special handling when sorting by ENS name column (index 1)
            if (column === 1) {
                // Separate rows with ENS from rows without ENS
                const withENS = [];
                const withoutENS = [];
                
                currentData.forEach(row => {
                    const ens = row[1].toLowerCase();
                    if (ens === '' || ens === 'no ens') {
                        withoutENS.push(row);
                    } else {
                        withENS.push(row);
                    }
                });
                
                // Sort only the rows with ENS
                withENS.sort((a, b) => {
                    const aENS = a[1].toLowerCase();
                    const bENS = b[1].toLowerCase();
                    
                    if (aENS < bENS) return sortDirection === 'asc' ? -1 : 1;
                    if (aENS > bENS) return sortDirection === 'asc' ? 1 : -1;
                    return 0;
                });
                
                // Combine: sorted ENS rows + unsorted no-ENS rows at the end
                if (sortDirection === 'asc') {
                    currentData = [...withENS, ...withoutENS];
                } else {
                    // In descending order, put no-ENS at beginning
                    currentData = [...withoutENS, ...withENS];
                }
                
                renderTable();
                updateSortHeaders();
                return;
            }
            
            // For all other columns, use regular sort
            currentData.sort((a, b) => {
                // Special handling when sorting by status column (index 2)
                if (column === 2) {
                    // Use the plain text status (row[7]) for sorting
                    const aStatus = a[7].toLowerCase();
                    const bStatus = b[7].toLowerCase();
                    
                    if (aStatus < bStatus) return sortDirection === 'asc' ? -1 : 1;
                    if (aStatus > bStatus) return sortDirection === 'asc' ? 1 : -1;
                    return 0;
                }
                
                // For other columns, always maintain status priority first
                // Status order: eligible-active (0), eligible-grace (1), ineligible-expired (2), ineligible-unqualified (3)
                const getStatusPriority = (statusString) => {
                    if (statusString === 'eligible-active') return 0;
                    if (statusString === 'eligible-grace') return 1;
                    if (statusString === 'ineligible-expired') return 2;
                    if (statusString === 'ineligible-unqualified') return 3;
                    return 4;
                };
                
                const aStatusPriority = getStatusPriority(a[7]);
                const bStatusPriority = getStatusPriority(b[7]);
                
                // If status priority differs, sort by priority
                if (aStatusPriority !== bStatusPriority) {
                    return aStatusPriority - bStatusPriority;
                }
                
                // Within same status group, sort by the selected column
                let aVal = a[column];
                let bVal = b[column];
                
                // All columns are now text, so convert to lowercase for comparison
                aVal = aVal.toLowerCase();
                bVal = bVal.toLowerCase();
                
                if (aVal < bVal) return sortDirection === 'asc' ? -1 : 1;
                if (aVal > bVal) return sortDirection === 'asc' ? 1 : -1;
                return 0;
            });
            
            renderTable();
            updateSortHeaders();
        }
        
        function renderTable() {
            tableBody.innerHTML = '';
            currentData.forEach((row, index) => {
                const [address, ensName, status, lastRenewedShort, lastRenewedFull, eligibleUntilShort, eligibleUntilFull, statusString, lastRenewedOnTx] = row;
                const ensDisplay = ensName || 'No ENS';
                const ensClass = ensName ? 'ens-name' : 'empty-ens';
                const explorerUrl = `https://thegraph.com/explorer/profile/${address}?view=Indexing&chain=arbitrum-one`;
                
                // Format Last Renewed cell with transaction link (no tooltip)
                let lastRenewedCell;
                if (lastRenewedShort === 'Never') {
                    lastRenewedCell = lastRenewedShort;
                } else {
                    // If we have a transaction hash, make the date a link with external icon
                    if (lastRenewedOnTx) {
                        lastRenewedCell = `<a href="https://sepolia.arbiscan.io/tx/${lastRenewedOnTx}" target="_blank" class="transaction-hash">${lastRenewedShort}<svg class="external-link-icon" viewBox="0 0 16 16" fill="currentColor"><path d="M14 2.5a.5.5 0 0 0-.5-.5h-6a.5.5 0 0 0 0 1h4.793L8.146 7.146a.5.5 0 0 0 .708.708L13 3.707V8.5a.5.5 0 0 0 1 0v-6z"/><path d="M4.5 4a.5.5 0 0 0-.5.5v8a.5.5 0 0 0 .5.5h8a.5.5 0 0 0 .5-.5V9a.5.5 0 0 0-1 0v3H5V5h3a.5.5 0 0 0 0-1h-3.5z"/></svg></a>`;
                } else {
                    lastRenewedCell = lastRenewedShort;
                    }
                }
                
                // Format Eligible Until cell with hover tooltip
                let eligibleUntilCell = '';
                if (eligibleUntilShort) {
                    eligibleUntilCell = `<span class="date-hover" data-full-date="${eligibleUntilFull}">${eligibleUntilShort}</span>`;
                }
                
                const rowHTML = `
                    <tr>
                        <td><a href="${explorerUrl}" target="_blank" class="address-link"><span class="address">${address}</span><svg class="external-link-icon" viewBox="0 0 16 16" fill="currentColor"><path d="M14 2.5a.5.5 0 0 0-.5-.5h-6a.5.5 0 0 0 0 1h4.793L8.146 7.146a.5.5 0 0 0 .708.708L13 3.707V8.5a.5.5 0 0 0 1 0v-6z"/><path d="M4.5 4a.5.5 0 0 0-.5.5v8a.5.5 0 0 0 .5.5h8a.5.5 0 0 0 .5-.5V9a.5.5 0 0 0-1 0v3H5V5h3a.5.5 0 0 0 0-1h-3.5z"/></svg></a></td>
                        <td><span class="${ensClass}">${ensDisplay}</span></td>
                        <td>${status}</td>
                        <td>${lastRenewedCell}</td>
                        <td>${eligibleUntilCell}</td>
                    </tr>
                `;
                tableBody.innerHTML += rowHTML;
            });
        }
        
        function updateSortHeaders() {
            const headers = document.querySelectorAll('th.sortable');
            headers.forEach((header, index) => {
                header.className = 'sortable';
                if (index === sortColumn) {
                    header.classList.add(sortDirection === 'asc' ? 'sort-asc' : 'sort-desc');
                }
            });
        }
        
        function updateStats() {
            totalCount.textContent = originalData.length;
            filteredCount.textContent = currentData.length;
        }
        
        // Add click handlers to sortable headers
        document.querySelectorAll('th.sortable').forEach((header, index) => {
            header.addEventListener('click', () => sortTable(index));
        });
        
        // Initialize
        renderTable();
        updateStats();
    </script>
"""
    
    # Add legend section before footer (commented out - using filter section instead)
    # html_content += """
    # <div class="legend">
    #     <div class="legend-title">Status Legend</div>
    #     <div class="legend-items">
    #         <div class="legend-item">
    #             <span class="legend-badge good">eligible</span>
    #             <span class="legend-description">Indexer is eligible for rewards</span>
    #         </div>
    #         <div class="legend-item">
    #             <span class="legend-badge grace">grace</span>
    #             <span class="legend-description">Grace period active (coming soon)</span>
    #         </div>
    #         <div class="legend-item">
    #             <span class="legend-badge ineligible">ineligible</span>
    #             <span class="legend-description">Indexer is not eligible for rewards</span>
    #         </div>
    #     </div>
    # </div>
    # """
    
    # Add footer with version, GitHub link, and Telegram bot
    html_content += f"""    
    <div class="footer">
        <div class="footer-content">
            <div class="footer-top">
                <div class="footer-left">
                    This dashboard is based on the <a href="https://forum.thegraph.com/t/gip-0079-indexer-rewards-eligibility-oracle/6734" target="_blank">GIP-0079: Indexer Rewards Eligibility Oracle</a>
                </div>
                <div class="footer-right">
                    <span class="version">v{VERSION}</span>
                    <span class="footer-separator">-</span>
                    <svg class="github-icon" viewBox="0 0 16 16" fill="currentColor"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"/></svg><a href="https://github.com/graphprotocol/rewards-eligibility-oracle-dashboard" target="_blank">View repo on GitHub</a>
                </div>
            </div>
        </div>
    </div>
    
    <!-- Contract Information Section - Commented out as requested -->
    """
    
    # Contract Information Section - Commented out as requested
    # html_content += f"""
    # <div class="contract-info">
    #     <div class="contract-info-header" onclick="toggleContractInfo()">
    #         <h3>Contract Information (FOR DEBUG ONLY - will be removed in the future)</h3>
    #         <svg class="contract-info-arrow" id="contractInfoArrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
    #             <polyline points="6 9 12 15 18 9"></polyline>
    #         </svg>
    #     </div>
    #     <div class="contract-info-content" id="contractInfoContent">
    #         <div class="info-item">
    #             <span class="info-label">Sepolia Contract on Arbitrum:</span>
    #             <span class="info-value"><a href="https://sepolia.arbiscan.io/address/{contract_address}" target="_blank" class="transaction-hash">{contract_address}</a></span>
    #         </div>"""
    # 
    # # Add oracle update time
    # if oracle_update_time:
    #     try:
    #         oracle_readable_time = datetime.fromtimestamp(oracle_update_time, tz=timezone.utc).strftime("%d %b %Y at %H:%M:%S (UTC)")
    #         html_content += f"""
    #     <div class="info-item">
    #         <span class="info-label">Last Oracle Update Time:</span>
    #         <span class="info-value">{oracle_readable_time}</span>
    #     </div>"""
    #     except Exception as e:
    #         print(f"Error formatting oracle update time: {e}")
    #         html_content += """
    #     <div class="info-item">
    #         <span class="info-label">Last Oracle Update Time:</span>
    #         <span class="info-value"><span class="error-message">Error formatting oracle update time</span></span>
    #     </div>"""
    # else:
    #     html_content += """
    #     <div class="info-item">
    #         <span class="info-label">Last Oracle Update Time:</span>
    #         <span class="info-value"><span class="error-message">Unable to fetch oracle update time</span></span>
    #     </div>"""
    # 
    # # Add last transaction data (without transaction time)
    # if last_transaction:
    #     tx_hash = last_transaction.get('hash', 'N/A')
    #     block_number = last_transaction.get('blockNumber', 'N/A')
    #     
    #     html_content += f"""
    #     <div class="info-item">
    #         <span class="info-label">Last Transaction ID:</span>
    #         <span class="info-value"><a href="https://sepolia.arbiscan.io/tx/{tx_hash}" target="_blank" class="transaction-hash">{tx_hash}</a></span>
    #     </div>
    #     <div class="info-item">
    #         <span class="info-label">Block Number:</span>
    #         <span class="info-value">{block_number}</span>
    #     </div>"""
    # else:
    #     html_content += """
    #     <div class="info-item">
    #         <span class="info-label">Last Transaction ID:</span>
    #         <span class="info-value"><span class="error-message">Unable to fetch transaction data</span></span>
    #     </div>"""
    # 
    # # Add eligibility period
    # if eligibility_period:
    #     # Convert seconds to days
    #     days = eligibility_period / 86400
    #     html_content += f"""
    #     <div class="info-item">
    #         <span class="info-label">Eligibility Period:</span>
    #         <span class="info-value">{eligibility_period} seconds ({days:.1f} days)</span>
    #     </div>"""
    # else:
    #     html_content += """
    #     <div class="info-item">
    #         <span class="info-label">Eligibility Period:</span>
    #         <span class="info-value"><span class="error-message">Unable to fetch eligibility period</span></span>
    #     </div>"""
    # 
    # html_content += """
    #     </div>
    # </div>
    # 
    # <script>
    #     function toggleContractInfo() {
    #         const content = document.getElementById('contractInfoContent');
    #         const arrow = document.getElementById('contractInfoArrow');
    #         content.classList.toggle('expanded');
    #         arrow.classList.toggle('expanded');
    #     }
    # </script>
    # """
    
    html_content += """
</body>
</html>"""

    return html_content


def main():
    """Main function to generate the dashboard."""
    start_time = datetime.now(timezone.utc)
    print("=" * 70)
    print(f"Script started at {start_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 70)
    print()
    print("Generating Eligibility Dashboard...")
    
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
    
    # Load environment variables (no hardcoded fallbacks)
    graph_api_key = os.getenv("GRAPH_API_KEY")
    use_cached_ens = os.getenv("USE_CACHED_ENS", "N").upper() == "Y"
    contract_address = os.getenv("CONTRACT_ADDRESS")
    api_key = os.getenv("ARBISCAN_API_KEY")
    grace_buffer_hours = int(os.getenv("GRACE_BUFFER_PERIOD_HOURS", "24"))
    
    # Initialize round-robin RPC manager
    rpc_manager = get_rpc_manager()
    
    # Get transaction hash first (before retrieving active indexers)
    # Always fetch fresh data, don't use cached JSON for initial metadata
    transaction_hash = None
    if contract_address and api_key:
        # Fetch transaction data via Arbiscan API
        last_transaction = get_last_transaction(contract_address, api_key)
        
        # Fallback to cached JSON if API fails
        if not last_transaction:
            print("⚠ Warning: Could not fetch fresh transaction data from API, using cached data")
            last_transaction = get_last_transaction_from_json()
        
        if last_transaction:
            transaction_hash = last_transaction.get("hash")
    
    # Retrieve active indexers by querying network subgraph
    if graph_api_key and graph_api_key != "your_graph_api_key_here":
        print()
        print("=" * 60)
        if use_cached_ens:
            print("🔄 ENS Cache Mode: ENABLED")
            print("   Using cached ENS data from ens_resolution.json")
        else:
            print("🌐 ENS Cache Mode: DISABLED")
            print("   Fetching fresh ENS data from subgraph")
        print("=" * 60)
        print()
        retrieveActiveIndexers(graph_api_key, use_cached_ens=use_cached_ens, contract_address=contract_address, rpc_manager=rpc_manager, transaction_hash=transaction_hash)
        print()
    else:
        print("⚠ GRAPH_API_KEY not set, skipping active indexers retrieval")
        print()
    
    # Read indexer data from active_indexers.json (generated by retrieveActiveIndexers)
    if not os.path.exists('active_indexers.json'):
        print("❌ Error: active_indexers.json not found!")
        print("   The indexer retrieval may have failed. Check the logs above for errors.")
        return

    with open('active_indexers.json', 'r') as f:
        indexers_data = json.load(f)
        indexers = indexers_data.get('indexers', [])
        indexers_count = len(indexers)

    print(f"Found {indexers_count} indexers")
    
    # Validate required environment variables
    missing_vars = []
    if not contract_address:
        missing_vars.append("CONTRACT_ADDRESS")
    if not api_key:
        missing_vars.append("ARBISCAN_API_KEY")
    if not rpc_manager.endpoints:
        missing_vars.append("RPC_ENDPOINT or RPC_ENDPOINT_1, RPC_ENDPOINT_2, etc.")
    
    if missing_vars:
        print("❌ Error: Required environment variables are missing:")
        for var in missing_vars:
            print(f"  - {var}")
        print()
        print("Please set these variables in your .env file.")
        print("For RPC endpoints, you can use:")
        print("  - RPC_ENDPOINT (single endpoint, backward compatible)")
        print("  - RPC_ENDPOINT_1, RPC_ENDPOINT_2, etc. (multiple endpoints for round-robin)")
        print("See .env.example for the required format.")
        return
    
    print("✓ Configuration loaded successfully")
    print()
    
    # Check eligibility for each indexer by calling the contract
    checkEligibility(contract_address, rpc_manager=rpc_manager, grace_buffer_hours=grace_buffer_hours)
    print()
    
    # Update status change dates by comparing with previous run
    updateStatusChangeDates()
    print()
    
    # Log status changes to activity log
    logStatusChanges()
    print()
    
    # Send Telegram notifications about oracle update and status changes
    if TELEGRAM_AVAILABLE:
        try:
            print("Sending Telegram notifications...")
            telegram_notifier.send_notifications()
            print()
        except Exception as e:
            print(f"⚠ Warning: Could not send Telegram notifications: {e}")
            print()
    else:
        print("ℹ️ Telegram notifications disabled (module not available)")
        print()
    
    html_content = generate_html_dashboard(indexers, contract_address=contract_address, api_key=api_key, rpc_manager=rpc_manager)

    # Write to index.html (in output directory if in production environment)
    output_dir = os.getenv('REO_OUTPUT_DIR', 'output')
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, 'index.html')

    with open(output_path, 'w', encoding='utf-8') as file:
        file.write(html_content)

    print(f"Dashboard generated successfully at {output_path}!")
    print(f"Open '{output_path}' in your browser to view the dashboard.")
    
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
