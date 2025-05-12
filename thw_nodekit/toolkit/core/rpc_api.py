"""
Unified API for Solana RPC interactions.

This module serves as the central entry point for all Solana blockchain
access, providing a clean and consistent interface that abstracts away
implementation details of the underlying RPC system.
"""

from typing import Any, Dict, List, Optional, Union
from thw_nodekit.toolkit.core.rpc_client import RPC_Client, get_rpc_client

# Global client instance cache to avoid creating multiple clients
_client_cache: Dict[str, RPC_Client] = {}


def get_client(cluster: Optional[str] = None) -> RPC_Client:
    """
    Get a properly configured RPC client.
    
    This function ensures that only one client is created per cluster,
    improving performance and resource usage.
    
    Args:
        cluster: Cluster name (defaults to configuration)
        
    Returns:
        RPC_Client: Configured client instance
    """
    cache_key = cluster or "default"
    
    if (cache_key not in _client_cache):
        _client_cache[cache_key] = get_rpc_client(cluster)
        
    return _client_cache[cache_key]


# ==============================
# Validator and Node Information
# ==============================

def get_vote_accounts(cluster: Optional[str] = None, include_delinquent: bool = True) -> Dict[str, Any]:
    """
    Get vote accounts with optional filtering.
    
    Args:
        cluster: Optional cluster name
        include_delinquent: If True, returns both current and delinquent accounts.
                           If False, returns only current accounts as a flat list.
        
    Returns:
        If include_delinquent is True: Dictionary containing 'current' and 'delinquent' vote accounts
        If include_delinquent is False: List of current (non-delinquent) validators
    """
    client = get_client(cluster)
    # Use direct method call to bypass the RPC client's own caching
    response = client.methods.get_vote_accounts()
    
    if not include_delinquent and response and "current" in response:
        return response["current"]
    
    return response


def get_cluster_nodes(cluster: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Get information about all nodes participating in the cluster.
    
    Args:
        cluster: Optional cluster name
        
    Returns:
        List of node information dictionaries
    """
    client = get_client(cluster)
    return client.methods.get_cluster_nodes()


def get_validator_info(cluster: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Get validator information.
    
    Args:
        cluster: Optional cluster name
        
    Returns:
        List of validator information entries
    """
    client = get_client(cluster)
    return client.get_validator_info()


def get_leader_schedule(slot: Optional[int] = None, identity: Optional[str] = None, 
                        cluster: Optional[str] = None) -> Dict[str, Any]:
    """
    Get leader schedule for current or specified epoch.
    
    Args:
        slot: Optional slot number
        identity: Optional validator identity pubkey to filter results
        cluster: Optional cluster name
        
    Returns:
        Dictionary mapping validator pubkeys to their leader slots
    """
    client = get_client(cluster)
    return client.methods.get_leader_schedule(slot, identity=identity)


def get_epoch_info(cluster: Optional[str] = None) -> Dict[str, Any]:
    """
    Get information about the current epoch.
    
    Args:
        cluster: Optional cluster name
        
    Returns:
        Dictionary containing epoch information
    """
    client = get_client(cluster)
    return client.methods.get_epoch_info()


def get_block_production(identity: Optional[str] = None, cluster: Optional[str] = None) -> Dict[str, Any]:
    """
    Get block production for current epoch
    
    Args:
        identity: Optional validator identity pubkey to filter results
        cluster: Optional cluster name
        
    Returns:
        Dictionary containing block production information for the validator identity pubkey
    """
    client = get_client(cluster)
    return client.methods.get_block_production(identity=identity)


# ====================
# Account Information
# ====================

def get_balance(account: str, cluster: Optional[str] = None) -> int:
    """
    Get account balance in lamports.
    
    Args:
        account: Account public key (base58 encoded)
        cluster: Optional cluster name
        
    Returns:
        Balance in lamports
    """
    client = get_client(cluster)
    return client.methods.get_balance(account)


def get_account_info(account: str, encoding: str = "base64", cluster: Optional[str] = None) -> Dict[str, Any]:
    """
    Get account information.
    
    Args:
        account: Account public key (base58 encoded)
        encoding: Response encoding format
        cluster: Optional cluster name
        
    Returns:
        Account information
    """
    client = get_client(cluster)
    return client.methods.get_account_info(account, encoding=encoding)


# ====================
# Blocks and Slots
# ====================

def get_slot(cluster: Optional[str] = None) -> int:
    """
    Get current slot number.
    
    Args:
        cluster: Optional cluster name
        
    Returns:
        Current slot number
    """
    client = get_client(cluster)
    # Use direct method call to bypass caching for real-time data
    return client.methods.get_slot()


def get_block_time(slot: int, cluster: Optional[str] = None) -> int:
    """
    Get estimated production time of a block.
    
    Args:
        slot: Slot number
        cluster: Optional cluster name
        
    Returns:
        Estimated production time as Unix timestamp
    """
    client = get_client(cluster)
    return client.methods.get_block_time(slot)


def get_recent_performance_samples(limit: int = 100, cluster: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Get recent performance samples for calculating slot timing.
    
    Args:
        limit: Maximum number of samples to return (1-720)
        cluster: Optional cluster name
        
    Returns:
        List of performance sample dictionaries
    """
    client = get_client(cluster)
    return client.methods.get_recent_performance_samples(limit)


# ====================
# Cache Management
# ====================

def clear_cache(method_name: Optional[str] = None, cluster: Optional[str] = None) -> None:
    """
    Clear the RPC cache.
    
    Args:
        method_name: Optional method name to clear specific cache entries
        cluster: Optional cluster name
    """
    client = get_client(cluster)
    client.clear_cache(method_name)


# ====================
# Migration Helpers
# ====================

def get_legacy_client_adapter(cluster: Optional[str] = None):
    """
    Get adapter compatible with original RPCClient.
    
    This helps with gradual migration from old code to new RPC system.
    
    Args:
        cluster: Optional cluster name
        
    Returns:
        Object with same interface as original RPCClient
    """
    new_client = get_client(cluster)
    
    class LegacyAdapter:
        def call(self, method, params=None, max_retries=3):
            """Legacy method call with RPC method name."""
            params = params or []
            return new_client.rpc.call(method, params)
            
        def run_solana_command(self, command):
            """Simulate CLI command with warning."""
            print("WARNING: run_solana_command is deprecated. Use RPC methods instead.")
            # Simplified implementation that tries to map common commands to RPC calls
            if command[0] == "validator-info" and command[1] == "get":
                return new_client.get_validator_info()
            
            raise NotImplementedError(
                f"Command {command} not implemented in new RPC system. "
                "Please use direct RPC methods instead."
            )
    
    return LegacyAdapter()