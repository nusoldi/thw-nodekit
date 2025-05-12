"""
CLI command execution module for Solana interactions.

This module provides functions to execute Solana CLI commands when
there's no direct RPC equivalent available.
"""

import subprocess
import json
from typing import Any, Dict, List, Optional, Union
from thw_nodekit.config import get_config

def execute_solana_command(command: List[str], cluster: Optional[str] = None) -> str:
    """
    Execute a solana CLI command and return its output.
    
    Args:
        command: List containing the command and its arguments
        cluster: Cluster identifier ('um' for mainnet, 'ut' for testnet)
        
    Returns:
        Command output as string
        
    Raises:
        RuntimeError: If command execution fails
    """
    try:
        # Add the common parts of the command
        full_command = ["solana"]
        
        # Add cluster parameter if provided
        if cluster:
            # Get config to determine the URL
            config = get_config()
            urls = config.get("rpc_urls", {}).get(cluster, {}).get("urls", [])
            if urls:
                # Use the first URL for the CLI command
                full_command.extend(["--url", urls[0]])
            else:
                # Use the cluster name directly (solana CLI can understand um/ut)
                full_command.extend(["--url", cluster])
            
        # Add the actual command parts
        full_command.extend(command)
        
        # Execute command and capture output
        result = subprocess.run(
            full_command,
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout
        
    except subprocess.CalledProcessError as e:
        # If command failed, include error output in exception
        error_msg = e.stderr if e.stderr else str(e)
        raise RuntimeError(f"Solana CLI command failed: {error_msg}")
    except Exception as e:
        # Handle any other exceptions
        raise RuntimeError(f"Failed to execute Solana command: {str(e)}")

def get_validator_info_cli(cluster: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Get validator information using the Solana CLI.
    
    Args:
        cluster: Cluster identifier ('um' for mainnet, 'ut' for testnet)
        
    Returns:
        List of validator information objects
    """
    try:
        output = execute_solana_command(
            ["validator-info", "get", "--output", "json"],
            cluster
        )
        return json.loads(output)
    except Exception as e:
        print(f"Warning: Failed to get validator info via CLI: {e}")
        return []