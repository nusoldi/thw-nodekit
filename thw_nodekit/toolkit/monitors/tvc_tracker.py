"""TVC tracking functionality for Solana validators."""

import time
import signal
import json
import os
import datetime
import threading
from typing import Optional, Dict, List, Any, Tuple
from thw_nodekit.toolkit.core.ip_tools import get_ip_info
from thw_nodekit.toolkit.core.rpc_api import (
    get_vote_accounts,
    get_cluster_nodes, 
    get_validator_info,
    get_client,
    clear_cache
)
from thw_nodekit.toolkit.display.tvc_tracker_display import TVCTrackerDisplay
from thw_nodekit.toolkit.core.epoch_calculator import EpochCalculator
from thw_nodekit.toolkit.core.leader_calculator import LeaderCalculator
from thw_nodekit.toolkit.display.startup_display import StartupDisplay

class TVCTracker:
    """Track timely vote credits for a validator over time."""
    
    def __init__(self, cluster=None, validator_identity=None, display=None, compare_ranks=None):
        """Initialize the Vote Tracker.
        
        Args:
            cluster: Cluster name to connect to
            validator_identity: Validator identity public key
            display: Optional display handler
            compare_ranks: List of ranks to compare against
        """
        self.cluster = cluster
        self.validator_identity = validator_identity
        self.running = True
        self.display = display or TVCTrackerDisplay()
        
        if compare_ranks is None:
            raise ValueError("compare_ranks must be provided from the config file")
        self.compare_ranks = compare_ranks
        
        # Initialize tracking variables
        self.last_validator_data = None
        
        # Lock for thread-safe data access
        self.data_lock = threading.RLock()
        
        # Cached data with timestamp - centralized storage
        self.cache = {
            # High-frequency data (sub-second updates)
            "vote_accounts": {"data": None, "timestamp": 0},
            "epoch_info": {"data": None, "timestamp": 0},
            "slot": {"data": None, "timestamp": 0},
            
            # Medium-frequency data (seconds)
            "leader_schedule": {"data": None, "timestamp": 0},
            "block_production": {"data": None, "timestamp": 0},
            
            # Low-frequency data (tens of seconds)
            "cluster_nodes": {"data": None, "timestamp": 0},
            "validator_info": {"data": None, "timestamp": 0},
            
            # Very low-frequency data (minutes+)
            "ip_info": {"data": {}, "timestamp": 0}
        }

        # Define TTL for different data types (in seconds)
        self.ttl = {
            # High-frequency data
            "vote_accounts": 0.1,        # 100ms
            "epoch_info": 0.1,           # 100ms
            "slot": 0.1,                 # 100ms
            
            # Medium-frequency data
            "leader_schedule": 60.0,     # 60 seconds
            "block_production": 5.0,     # 5 seconds
            
            # Low-frequency data
            "cluster_nodes": 60.0,       # 60 seconds
            "validator_info": 120.0,     # 120 seconds
            
            # Very low-frequency data
            "ip_info": 21600.0           # 6 hour
        }
        
        # Store processed data for efficient access
        self.processed_data = {}
        self.leader_metrics_cache = None
        
        # Setup signal handler
        signal.signal(signal.SIGINT, self._signal_handler)

        # Initialize calculators
        self.epoch_calculator = EpochCalculator(cluster)
        self.leader_calculator = LeaderCalculator(cluster)
        
        # Clear RPC caches on startup to ensure fresh data
        clear_cache(cluster=cluster)
    
    def _signal_handler(self, sig, frame):
        """Handle shutdown signals gracefully."""
        self.running = False
        # Clean up display if it's a Rich display
        if hasattr(self.display, 'cleanup'):
            self.display.cleanup()
    
    def _get_cached_data(self, data_type: str, refresh_func, *args, **kwargs) -> Any:
        """Get data from cache or refresh if expired based on TTL.
        
        Thread-safe implementation with proper locking.
        """
        with self.data_lock:
            cache_entry = self.cache[data_type]
            current_time = time.time()
            
            # Get TTL for this data type
            ttl = self.ttl.get(data_type, 30)  # Default 30 seconds
            
            # Refresh if cache is expired or empty
            if cache_entry["data"] is None or (current_time - cache_entry["timestamp"]) > ttl:
                try:
                    data = refresh_func(*args, **kwargs)
                    self.cache[data_type] = {
                        "data": data,
                        "timestamp": current_time
                    }
                except Exception as e:
                    error_msg = f"Error refreshing {data_type}: {e}"
                    print(error_msg)
                    # Keep existing data if there's an error and it exists
                    if cache_entry["data"] is None:
                        # Initialize with empty data structure appropriate for type
                        if data_type == "vote_accounts":
                            self.cache[data_type]["data"] = []
                        elif data_type in ["cluster_nodes", "validator_info"]:
                            self.cache[data_type]["data"] = []
                        elif data_type == "ip_info":
                            self.cache[data_type]["data"] = {}
                        else:
                            self.cache[data_type]["data"] = {}
                
        return self.cache[data_type]["data"]
    
    def _fetch_vote_accounts(self):
        """Fetch and process validators data with proper filtering."""
        try:
            # Get only current validators (exclude delinquent validators)
            validators = get_vote_accounts(self.cluster, include_delinquent=False)
            
            if not validators:
                return []
                
            # Get current epoch for filtering
            epoch_info = self._get_cached_data("epoch_info", self._fetch_epoch_info)
            current_epoch = epoch_info.get("epoch", 0)
            
            # Filter for validators with current epoch data
            current_validators = []
            for v in validators:
                if isinstance(v.get("epochCredits"), list) and v["epochCredits"]:
                    latest_epoch = v["epochCredits"][-1][0] if len(v["epochCredits"][-1]) >= 1 else 0
                    if latest_epoch >= current_epoch - 1:
                        current_validators.append(v)
            
            return current_validators
            
        except Exception as e:
            print(f"Error fetching vote accounts: {e}")
            return []
    
    def _fetch_validator_info(self):
        """Fetch validator info data."""
        # Use the new RPC API directly - returns list format
        return get_validator_info(self.cluster)
    
    def _fetch_cluster_nodes(self):
        """Fetch gossip data."""
        # Use the new RPC API directly
        return get_cluster_nodes(self.cluster)
    
    def _fetch_epoch_info(self):
        """Fetch epoch info."""
        client = get_client(self.cluster)
        return client.methods.get_epoch_info()
    
    def _fetch_slot(self):
        """Fetch current slot."""
        client = get_client(self.cluster)
        return client.methods.get_slot()
    
    def _fetch_leader_schedule(self):
        """Fetch leader schedule."""
        client = get_client(self.cluster)
        return client.methods.get_leader_schedule(identity=self.validator_identity)
    
    def _fetch_block_production(self):
        """Fetch block production."""
        client = get_client(self.cluster)
        return client.methods.get_block_production(identity=self.validator_identity)
    
    def _fetch_ip_info(self, ip_address):
        """Fetch IP info."""
        if not ip_address or ip_address == "Unknown":
            return {}
        try:
            return get_ip_info(ip_address)
        except Exception as e:
            print(f"Error fetching IP info: {e}")
            return {}

    def update_data(self):
        """Update all cached data based on their TTLs.
        
        This method can be called frequently and will only refresh data
        when its TTL has expired. Returns True if any data was updated.
        """
        any_updated = False
        
        # Update high-frequency data
        if self._get_cached_data("vote_accounts", self._fetch_vote_accounts) is not None:
            any_updated = True
        
        if self._get_cached_data("epoch_info", self._fetch_epoch_info) is not None:
            any_updated = True
        
        if self._get_cached_data("slot", self._fetch_slot) is not None:
            any_updated = True
        
        # Update medium-frequency data
        self._get_cached_data("leader_schedule", self._fetch_leader_schedule)
        self._get_cached_data("block_production", self._fetch_block_production)
        
        # Update low-frequency data
        cluster_nodes = self._get_cached_data("cluster_nodes", self._fetch_cluster_nodes)
        self._get_cached_data("validator_info", self._fetch_validator_info)
        
        # Update IP info if we have cluster nodes
        if cluster_nodes:
            # Try to find the IP address for our validator
            ip_address = "Unknown"
            for node in cluster_nodes:
                if node.get("pubkey") == self.validator_identity:
                    gossip = node.get("gossip")
                    if gossip and ":" in gossip:
                        ip_address = gossip.split(":")[0]
                    break
            
            # Only update IP info if we have a valid IP address
            if ip_address != "Unknown":
                self._get_cached_data(f"ip_info", self._fetch_ip_info, ip_address)
        
        return any_updated

    def process_data(self):
        """Process all cached data into a comprehensive validator data object.
        
        This method combines all the cached data into a single object ready for display.
        """
        with self.data_lock:
            # Get all required data from cache
            validators = self.cache["vote_accounts"]["data"]
            validator_info = self.cache["validator_info"]["data"]
            gossip_data = self.cache["cluster_nodes"]["data"]
            epoch_info = self.cache["epoch_info"]["data"]
            
            # Early exit if essential data is missing
            if not validators:
                print(f"No validators found. Check your RPC connection.")
                return None
            
            # Get RPC URL for display
            client = get_client(self.cluster)
            rpc_url = client.rpc.current_url if hasattr(client, 'rpc') and hasattr(client.rpc, 'current_url') else "Unknown"

            # Determine cluster type based on the cluster parameter code
            cluster_type = "Mainnet" if self.cluster == "um" else "Testnet"
                
            # Count active validators
            active_node_count = len(validators)
            
            # Find our validator by identity (try both nodePubkey and votePubkey)
            validator = None
            for v in validators:
                if v.get("nodePubkey") == self.validator_identity or v.get("votePubkey") == self.validator_identity:
                    validator = v
                    break
            
            if not validator:
                print(f"Validator {self.validator_identity} not found in the current data.")
                return None
            
            # Process epoch credits for all validators
            valid_validators = []
            all_epoch_credits = []
            
            for v in validators:
                # Process epoch credits correctly
                if isinstance(v.get("epochCredits"), list) and v["epochCredits"]:
                    try:
                        latest_entry = v["epochCredits"][-1]
                        if len(latest_entry) >= 3:
                            v["epochCredits"] = latest_entry[1] - latest_entry[2]  # per-epoch difference
                        else:
                            v["epochCredits"] = latest_entry[1] if len(latest_entry) >= 2 else 0
                        
                        # Add to our list of all credits for statistics
                        all_epoch_credits.append(int(v["epochCredits"]))
                    except (IndexError, TypeError):
                        v["epochCredits"] = 0
                
                # Add the validator to our list
                valid_validators.append(v)
            
            # Calculate statistics
            all_epoch_credits.sort()
            network_mean_credits = sum(all_epoch_credits) / len(all_epoch_credits) if all_epoch_credits else 0
            network_median_credits = all_epoch_credits[len(all_epoch_credits) // 2] if all_epoch_credits else 0
            
            # Get our validator's epoch credits
            validator_credits = int(validator.get("epochCredits", 0)) if validator else 0
            
            # Calculate percentile ranking (what percentage of validators have fewer credits)
            if all_epoch_credits:
                percentile = sum(1 for x in all_epoch_credits if x < validator_credits) / len(all_epoch_credits) * 100
            else:
                percentile = 0
            
            # Rank validators
            ranked_validators = sorted(valid_validators, key=lambda x: int(x.get("epochCredits", 0)), reverse=True)

            # Find our validator's rank
            validator_rank = None
            for i, v in enumerate(ranked_validators):
                if v.get("nodePubkey") == self.validator_identity:
                    validator_rank = i + 1  # 1-based rank
                    break

            # Get highest epoch credits
            epoch_credits_rank_1 = int(ranked_validators[0].get("epochCredits", 0)) if ranked_validators else 0

            # Update validator name handling - now validator_info is a list
            validator_name = "Unknown"
            if validator_info:
                for info in validator_info:
                    if info.get("identityPubkey") == self.validator_identity:
                        validator_name = info.get("info", {}).get("name", "Unknown")
                        break

            # Get IP address and version - FIX: Parse from getClusterNodes response
            ip_address = "Unknown"
            version = "Unknown"
            if gossip_data:
                for node in gossip_data:
                    if node.get("pubkey") == self.validator_identity:
                        # Extract IP from gossip field which has format "ip:port"
                        gossip = node.get("gossip")
                        if gossip and ":" in gossip:
                            ip_address = gossip.split(":")[0]
                        
                        # Extract version information 
                        version = node.get("version")
                        break
            
            # Use cached IP info
            ip_info = self.cache["ip_info"]["data"] or {}

            # Fix rank comparisons
            rank_comparisons = []
            # Build a proper rank-to-validator lookup dictionary
            rank_lookup = {}
            for i, v in enumerate(ranked_validators):
                # Store validator at rank position (1-based ranking)
                rank_lookup[i+1] = v

            # Generate comparisons at requested ranks
            for compare_rank in self.compare_ranks:
                if compare_rank in rank_lookup:
                    compare_validator = rank_lookup[compare_rank]
                    # Calculate how many more credits the comparison validator has than our validator
                    diff = int(compare_validator.get("epochCredits", 0)) - validator_credits
                    is_current = (compare_rank == validator_rank)
                    rank_comparisons.append({"rank": compare_rank, "diff": diff, "is_current": is_current})

            # If validator's rank is not already in the comparison list, add it
            if validator_rank and all(comp.get("rank") != validator_rank for comp in rank_comparisons):
                rank_comparisons.append({"rank": validator_rank, "diff": 0, "is_current": True})
            
            # Sort to maintain rank order after adding the validator's rank
            rank_comparisons.sort(key=lambda x: x["rank"])

            # Calculate epoch metrics
            epoch_metrics = self.epoch_calculator.calculate_epoch_metrics()
            
            # Calculate leader metrics with high-frequency time updates
            leader_metrics = self._get_leader_metrics()

            # Prepare comprehensive data object
            if validator:
                # Calculate missed credits
                epoch_credits = int(validator.get("epochCredits", 0))
                missed_credits = epoch_credits_rank_1 - epoch_credits
                
                # Extract vote and root slot from validator
                lastVote = int(validator.get("lastVote", 0))
                rootSlot = int(validator.get("rootSlot", 0))
                
                # Add metrics to the data structure
                result = {
                    "validator": validator,
                    "validator_rank": validator_rank,
                    "validator_name": validator_name,
                    "ip_address": ip_address,
                    "ip_info": ip_info,
                    "version": version,
                    "epoch_credits": epoch_credits,
                    "epoch_credits_rank_1": epoch_credits_rank_1,
                    "missed_credits": missed_credits,
                    "last_vote": lastVote,
                    "root_slot": rootSlot,
                    "rank_comparisons": rank_comparisons,
                    "rpc_url": rpc_url,
                    "cluster_type": cluster_type,
                    "active_node_count": active_node_count,
                    "cache_ages": {
                        key: int(time.time() - self.cache[key]["timestamp"])
                        for key in self.cache
                    },
                    "epoch_metrics": epoch_metrics,
                    "leader_metrics": leader_metrics,
                    "network_stats": {
                        "mean_credits": network_mean_credits,
                        "median_credits": network_median_credits,
                        "percentile": percentile
                    }
                }
                
                # Add calculated deltas if we have previous data
                if self.last_validator_data:
                    last_validator = self.last_validator_data.get("validator")
                    if last_validator:
                        # Credit delta
                        last_credits = int(last_validator.get("epochCredits", 0))
                        credit_delta = epoch_credits - last_credits
                        result["credit_delta"] = credit_delta
                        
                        # Missed credit delta
                        last_missed = self.last_validator_data.get("missed_credits", 0)
                        missed_delta = missed_credits - last_missed
                        result["missed_delta"] = missed_delta
                        
                        # Last vote slot delta
                        last_vote_slot = int(last_validator.get("lastVote", 0))
                        vote_slot_delta = lastVote - last_vote_slot
                        result["vote_slot_delta"] = vote_slot_delta
                        
                        # Root slot delta
                        last_root_slot = int(last_validator.get("rootSlot", 0))
                        root_slot_delta = rootSlot - last_root_slot
                        result["root_slot_delta"] = root_slot_delta
                
                self.processed_data = result
                return result
            
            return None
    
    def _get_leader_metrics(self):
        """Get leader metrics with high-frequency time updates.
        
        This method uses caching to optimize leader metrics access, performing
        full recalculation on medium frequency but high-frequency time updates.
        
        Returns:
            Dictionary containing leader metrics
        """
        # First check if we need to do a complete refresh
        medium_frequency_updated = False
        
        # Check if leader schedule or block production was updated
        leader_schedule_ts = self.cache["leader_schedule"]["timestamp"]
        block_production_ts = self.cache["block_production"]["timestamp"]
        
        # If we don't have cached leader metrics or medium-frequency data was updated
        if (self.leader_metrics_cache is None or
            (time.time() - self.leader_metrics_cache.get("last_full_update", 0)) > self.ttl["leader_schedule"]):
            # Do a full refresh
            leader_metrics = self.leader_calculator.calculate_leader_metrics(self.validator_identity)
            
            # Cache the result with timestamp
            self.leader_metrics_cache = {
                "metrics": leader_metrics,
                "last_full_update": time.time()
            }
            return leader_metrics
        
        # If we have cached metrics, just update the time components
        if self.leader_metrics_cache and self.leader_metrics_cache.get("metrics"):
            # Update just the time-sensitive parts at high frequency
            updated_metrics = self.leader_calculator.update_leader_time_metrics(
                self.leader_metrics_cache["metrics"].copy()
            )
            
            # Store the updated metrics
            self.leader_metrics_cache["metrics"] = updated_metrics
            return updated_metrics
        
        # Fallback - shouldn't typically reach here
        return self.leader_calculator.calculate_leader_metrics(self.validator_identity)

    def initialize_data(self, max_retries=3, retry_delay=1.0, startup_display=None):
        """Initialize all data with retry logic.
        
        This ensures that critical data is loaded before starting the display loop.
        
        Args:
            max_retries: Maximum number of retries for each data type
            retry_delay: Delay between retries in seconds
            startup_display: Optional StartupDisplay instance for showing progress
            
        Returns:
            bool: True if initialization succeeded, False otherwise
        """
        # Critical data types that must be loaded for proper operation
        critical_data = [
            ("vote_accounts", self._fetch_vote_accounts),
            ("cluster_nodes", self._fetch_cluster_nodes),
            ("validator_info", self._fetch_validator_info),
            ("epoch_info", self._fetch_epoch_info),
            ("leader_schedule", self._fetch_leader_schedule),
            ("block_production", self._fetch_block_production)
        ]
        
        # Try to load each critical data type with retries
        all_success = True
        for data_type, fetch_func in critical_data:
            success = False
            for attempt in range(max_retries):
                try:
                    data = fetch_func()
                    if data:
                        self.cache[data_type] = {
                            "data": data,
                            "timestamp": time.time()
                        }
                        if startup_display:
                            startup_display.update_initialization_status(data_type, True)
                            # Add a small delay to ensure the update is visible
                            time.sleep(0.2)
                        success = True
                        break
                except Exception as e:
                    error_msg = f"Error loading {data_type} (attempt {attempt+1}/{max_retries}): {e}"
                    if startup_display:
                        startup_display.update_initialization_status(data_type, False, error_msg)
                        # Add a small delay to ensure the update is visible
                        time.sleep(0.2)
                    if attempt < max_retries - 1:
                        if startup_display:
                            startup_display.update_retry_status(data_type, retry_delay)
                            # Add a small delay to ensure the update is visible
                            time.sleep(0.2)
                        time.sleep(retry_delay)
            
            # Check if critical data failed to load
            if not success:
                if data_type in ["vote_accounts", "cluster_nodes", "epoch_info"]:
                    all_success = False
                    if startup_display:
                        startup_display.update_critical_failure(data_type)
                        # Add a small delay to ensure the update is visible
                        time.sleep(0.5)
        
        # Initialize validator data if necessary
        if all_success:
            validator_data = self.process_data()
            if validator_data is None:
                all_success = False
                if startup_display:
                    startup_display.update_critical_failure("validator_data")
                    # Add a small delay to ensure the update is visible
                    time.sleep(0.5)
            elif startup_display:
                startup_display.update_initialization_status("validator_data", True)
                # Add a small delay to ensure the update is visible
                time.sleep(0.2)
        
        # Summarize initialization status
        if startup_display:
            startup_display.finalize_initialization(all_success)
            # Add a pause to allow the user to see the final status
            time.sleep(1.0)
        
        return all_success

    def run(self, display_interval=0.2):
        """Run the tracker with specified display refresh rate.
        
        Args:
            display_interval: How frequently to update the display (seconds)
        """
        # Initialize the startup display
        startup_display = StartupDisplay()
        
        # Start the initialization process
        startup_display.start_initialization()
        
        try:
            # Initialize data with the startup display
            initialization_successful = self.initialize_data(startup_display=startup_display)
            
            # Pause to ensure the final status is visible
            time.sleep(1.0)
            
            # Properly clean up the startup display
            startup_display.cleanup()
            
            # If initialization failed, exit
            if not initialization_successful:
                print("Initialization failed. Exiting.")
                return
            
            # Clear the terminal for a fresh start
            print("\033[2J\033[H", end="", flush=True)
            
            # Run the main tracker loop
            self._run_tracker_loop(display_interval)
                
        except KeyboardInterrupt:
            print("\nMonitoring stopped.")
            startup_display.cleanup()
        except Exception as e:
            print(f"\nError: {e}")
            startup_display.cleanup()
    
    def _run_tracker_loop(self, display_interval):
        """Run the main tracker loop."""
        last_display_time = 0
        
        try:
            while self.running:
                start_time = time.time()
                
                # Update cached data based on TTLs
                data_updated = self.update_data()
                
                # Process data
                if data_updated or self.processed_data is None:
                    validator_data = self.process_data()
                else:
                    validator_data = self.processed_data
                
                # Update display at specified interval
                current_time = time.time()
                if current_time - last_display_time >= display_interval:
                    # Display data
                    self.display.display_validator_data(validator_data, self.validator_identity)
                    last_display_time = current_time
                    
                    # Save for next iteration
                    self.last_validator_data = validator_data
                
                # Short sleep to prevent CPU spinning
                process_time = time.time() - start_time
                sleep_time = max(0.01, min(0.05, display_interval/5 - process_time))
                time.sleep(sleep_time)
                
        except KeyboardInterrupt:
            print("\nMonitoring stopped.")
        finally:
            self.running = False
            # Ensure display is cleaned up
            if hasattr(self.display, 'cleanup'):
                self.display.cleanup()


def monitor_tvc(identity=None, interval=None, cluster=None, config_path=None):
    """Run the vote tracker for a validator.
    
    Args:
        cluster: Cluster to monitor (um=mainnet, ut=testnet)
        identity: Validator identity to monitor (uses config default if not provided)
        interval: Display refresh interval in seconds (from CLI --interval)

        config_path: Path to config file
    """
    # Use config defaults only if not provided by CLI
    from thw_nodekit.config import get_config
    config = get_config(config_path or None)
    
    # Get default identity if not provided
    if identity is None:
        # Use cluster-specific default validator identity
        default_identity_key = f"toolkit.default_identity_{cluster}"
        identity_value = config.get(default_identity_key)
        if not identity_value:
            original_error_key = f"default_identity_{cluster}"
            raise ValueError(f"No validator identity specified and no {original_error_key} found in config's [toolkit] section")
        identity = identity_value
    
    # Access trackers section using the get() method
    trackers = config.get("trackers")
    if not trackers:
        raise ValueError("Missing 'trackers' section in config file")
    
    compare_ranks_key = f"compare_ranks_{cluster}"
    compare_ranks = trackers.get(compare_ranks_key)
    
    if not compare_ranks:
        raise ValueError(f"Missing '{compare_ranks_key}' configuration in trackers section")
    
    try:
        from thw_nodekit.toolkit.display.tvc_tracker_display import TVCTrackerDisplay
        display = TVCTrackerDisplay()
    except Exception as e:
        # Print the actual error for debugging
        import traceback
        print(f"Error initializing Rich display: {e}")
        print(traceback.format_exc())
        print("Unable to initialize display. Please check that the Rich library is installed.")
        return
    
    # Run tracker
    tracker = TVCTracker(cluster=cluster, validator_identity=identity, display=display, compare_ranks=compare_ranks)
    tracker.run(display_interval=interval)