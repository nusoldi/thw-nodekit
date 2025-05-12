"""
Collection of Solana API method implementations.

This module provides a clean interface to Solana JSON-RPC API methods.
Methods are organized by functional categories for clarity.
"""

from typing import Any, Dict, List, Optional, Union


class RPC_Methods:
    """
    Organized collection of Solana RPC method implementations.
    
    Methods are grouped by functional categories:
    - Validator/Node information
    - Account information
    - Transaction processing
    - Blocks and slots
    """
    
    def __init__(self, rpc_client):
        """
        Initialize with RPC client.
        
        Args:
            rpc_client: Instance of RPC_Client
        """
        self.rpc = rpc_client
        
    # ==============================
    # Validator and Node Information
    # ==============================
    
    def get_vote_accounts(self) -> Dict[str, Any]:
        """
        Get information about all active vote accounts.
        
        Returns:
            Dictionary containing 'current' and 'delinquent' vote accounts
        """
        return self.rpc.call("getVoteAccounts")
    
    def get_cluster_nodes(self) -> List[Dict[str, Any]]:
        """
        Get information about all the nodes participating in the cluster.
        
        Returns:
            List of node info dictionaries
        """
        return self.rpc.call("getClusterNodes")
    
    def get_validator_info(self) -> List[Dict[str, Any]]:
        """
        Get validator information.
        
        This uses the Solana CLI command 'validator-info get' as there's
        no direct RPC equivalent that provides the same metadata.
        
        Returns:
            List of validator information objects
        """
        from thw_nodekit.toolkit.core.cli_commands import get_validator_info_cli
        
        try:
            # Get cluster from config if possible
            from thw_nodekit.config import get_config
            config = get_config()
            # Try to determine which cluster we're using based on the RPC URL
            current_url = self.rpc.current_url if hasattr(self.rpc, 'current_url') else None
            
            # Find which cluster this URL belongs to
            cluster = None
            if current_url:
                for cluster_name, cluster_config in config.get("rpc_urls", {}).items():
                    if current_url in cluster_config.get("urls", []):
                        cluster = cluster_name
                        break
            
            # Get validator info via CLI
            validator_info = get_validator_info_cli(cluster)
            
            # Return the list directly - this matches CLI output structure
            return validator_info
            
        except Exception as e:
            print(f"Warning: Validator info unavailable via CLI: {e}")
            
            # Fall back to limited info from getClusterNodes for compatibility
            try:
                nodes = self.rpc.call("getClusterNodes")
                
                # Transform to match expected structure as closely as possible
                return [
                    {
                        "identityPubkey": node.get("pubkey", ""),
                        "info": {
                            "name": f"Node {node.get('pubkey', '')[:8]}...",
                        },
                        "nodeInfo": node  # Add the node technical info for reference
                    }
                    for node in nodes
                ]
            except Exception:
                # In case even RPC fails, return empty list
                return []
    
    # ====================
    # Account Information
    # ====================
    
    def get_balance(self, account: str) -> int:
        """
        Get balance of an account.
        
        Args:
            account: Public key of account as base58 string
            
        Returns:
            Account balance in lamports
        """
        return self.rpc.call("getBalance", [account])
    
    def get_account_info(self, account: str, encoding: str = "base64") -> Dict[str, Any]:
        """
        Get account information.
        
        Args:
            account: Public key of account as base58 string
            encoding: Data encoding format
            
        Returns:
            Account information
        """
        params = [
            account,
            {"encoding": encoding}
        ]
        return self.rpc.call("getAccountInfo", params)
    
    # ====================
    # Blocks and Slots
    # ====================
    
    def get_slot(self) -> int:
        """
        Get the current slot.
        
        Returns:
            Current slot
        """
        return self.rpc.call("getSlot")
    
    def get_block_time(self, slot: int) -> int:
        """
        Get estimated production time of a block.
        
        Args:
            slot: Slot number
            
        Returns:
            Estimated production time as Unix timestamp
        """
        return self.rpc.call("getBlockTime", [slot])
    
    def get_epoch_info(self) -> Dict[str, Any]:
        """
        Returns information about the current epoch.
        
        Returns:
            Dictionary containing epoch information:
            - absoluteSlot: the current slot
            - blockHeight: the current block height
            - epoch: the current epoch
            - slotIndex: the current slot relative to the start of the current epoch
            - slotsInEpoch: the number of slots in this epoch
        """
        return self.rpc.call("getEpochInfo")
    
    def get_recent_performance_samples(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get recent performance samples.
        
        Args:
            limit: Maximum number of samples to return (max 720)
            
        Returns:
            List of performance sample dictionaries
        """
        limit = min(limit, 720)  # Enforce maximum limit
        return self.rpc.call("getRecentPerformanceSamples", [limit])

    def get_leader_schedule(self, slot: Optional[int] = None, identity: Optional[str] = None) -> Dict[str, Any]:
        """
        Get the leader schedule for the current or specified epoch.
        
        Args:
            slot: Optional slot, uses current slot if None
            identity: Optional validator identity to filter results
            
        Returns:
            Dictionary of leader schedule
        """
        params = []
        if slot is not None:
            params.append(slot)
            
        if identity is not None:
            config = {"identity": identity}
            if len(params) == 0:
                params.append(None)  # Add null placeholder for slot
            params.append(config)
            
        return self.rpc.call("getLeaderSchedule", params)
    
    def get_block_production(self, identity: Optional[str] = None) -> Dict[str, Any]:
        """
        Get the block production for the current epoch.
        
        Args:
            identity: Optional validator identity to filter results
            
        Returns:
            Dictionary containing block production information
        """
        params = []
        
        if identity is not None:
            params.append({"identity": identity})
            
        return self.rpc.call("getBlockProduction", params)