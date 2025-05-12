"""
High-level Solana client combining RPC communication with caching and methods.
"""

import time
import threading
from typing import Any, Dict, List, Optional, Union, Callable
from thw_nodekit.config import get_config
from thw_nodekit.toolkit.core.rpc_core import RPC_Core
from thw_nodekit.toolkit.core.rpc_methods import RPC_Methods


class RPC_Client:
    """
    High-level Solana client that integrates RPC communication with caching.
    
    This client serves as the main entry point for Solana blockchain
    interactions and provides:
    - Method-specific caching
    - Easy access to all Solana API methods
    - Configuration from application settings
    """
    
    def __init__(self, urls: Optional[List[str]] = None, cluster: Optional[str] = None):
        """
        Initialize Solana client.
        
        Args:
            urls: List of RPC endpoint URLs (optional if cluster is provided)
            cluster: Cluster name to load URLs from config (optional if urls provided)
        """
        # Get URLs either directly or from config
        if urls is None and cluster is None:
            config = get_config()
            cluster = config.get("default_cluster", "um")
            urls = config.get(f"rpc_urls.{cluster}.urls", [])
            
        elif urls is None and cluster is not None:
            config = get_config()
            urls = config.get(f"rpc_urls.{cluster}.urls", [])
        
        if not urls:
            raise ValueError(f"No RPC URLs provided or configured for cluster '{cluster}'")
            
        # Initialize core components
        self.rpc = RPC_Core(urls)
        self.methods = RPC_Methods(self.rpc)
        
        # Initialize thread lock for cache
        self.cache_lock = threading.RLock()
        
        # Initialize cache
        self.cache = {}
        self.cache_ttl = {
            # High-frequency data (sub-second updates)
            "get_vote_accounts": 0.5,     # 500ms
            "get_slot": 0.2,              # 200ms
            "get_epoch_info": 0.5,        # 500ms
            
            # Medium-frequency data (seconds)
            "get_cluster_nodes": 15.0,    # 15 seconds
            "get_leader_schedule": 5.0,   # 5 seconds
            "get_block_production": 5.0,  # 5 seconds 
            
            # Low-frequency data (tens of seconds)
            "get_validator_info": 60.0,   # 60 seconds
            "get_balance": 5.0,           # 5 seconds
        }
        
    def cached_call(self, method_name: str, *args, ttl: Optional[float] = None, **kwargs) -> Any:
        """
        Call a method with caching based on method name and arguments.
        
        Args:
            method_name: Name of the method to call on self.methods
            *args: Arguments to pass to the method
            ttl: Custom TTL override (in seconds)
            **kwargs: Keyword arguments to pass to the method
            
        Returns:
            Method result (from cache if valid, otherwise fresh)
        """
        # Get the actual method
        method = getattr(self.methods, method_name)
        
        # Create cache key from method name and arguments
        arg_str = str(args) + str(sorted(kwargs.items()))
        cache_key = f"{method_name}:{arg_str}"
        
        # Get TTL for this method
        method_ttl = ttl if ttl is not None else self.cache_ttl.get(method_name, 30)
        
        # Check cache with proper locking
        with self.cache_lock:
            current_time = time.time()
            if cache_key in self.cache:
                entry = self.cache[cache_key]
                if current_time - entry["timestamp"] < method_ttl:
                    return entry["data"]
        
            # Call method
            try:
                result = method(*args, **kwargs)
                
                # Cache result with lock
                with self.cache_lock:
                    self.cache[cache_key] = {
                        "data": result,
                        "timestamp": current_time
                    }
                return result
            except Exception as e:
                # If error and cached data available, return cached data
                if cache_key in self.cache:
                    print(f"Error refreshing {method_name}, using cached data: {e}")
                    return self.cache[cache_key]["data"]
                raise
    
    def clear_cache(self, method_name: Optional[str] = None) -> None:
        """
        Clear cache entries.
        
        Args:
            method_name: If provided, only clear entries for this method
        """
        with self.cache_lock:
            if method_name:
                prefix = f"{method_name}:"
                self.cache = {k: v for k, v in self.cache.items() if not k.startswith(prefix)}
            else:
                self.cache.clear()
    
    # Convenience cached methods
    
    def get_vote_accounts(self) -> Dict[str, Any]:
        """Get cached vote accounts information."""
        return self.cached_call("get_vote_accounts")
    
    def get_cluster_nodes(self) -> List[Dict[str, Any]]:
        """Get cached cluster nodes information."""
        return self.cached_call("get_cluster_nodes")
    
    def get_validator_info(self) -> List[Dict[str, Any]]:
        """Get validator information."""
        # Call methods.get_validator_info which handles the CLI execution
        return self.methods.get_validator_info()
    
    def get_leader_schedule(self, slot: Optional[int] = None) -> Dict[str, Any]:
        """Get cached leader schedule."""
        return self.cached_call("get_leader_schedule", slot)
    
    def get_slot(self) -> int:
        """Get current slot (brief cache)."""
        return self.cached_call("get_slot")
    
    def get_block_production(self, identity: Optional[str] = None) -> Dict[str, Any]:
        """Get block production information."""
        return self.cached_call("get_block_production", identity=identity)


# Factory function for convenient access
def get_rpc_client(cluster: Optional[str] = None) -> RPC_Client:
    """
    Create a properly configured Solana client instance.
    
    Args:
        cluster: Cluster name to use ("um" for mainnet, "ut" for testnet, etc.)
                Default is taken from config if not provided
    
    Returns:
        Configured SolanaClient instance
    """
    return RPC_Client(cluster=cluster)
