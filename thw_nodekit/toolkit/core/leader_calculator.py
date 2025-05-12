"""
Solana leader slot and block production calculations and analysis.

Provides metrics and utilities for working with Solana epoch data.
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from thw_nodekit.toolkit.core import rpc_api


class LeaderCalculator:
    """
    Calculates and analyses leader slots and block production for current epoch.
    """
    
    def __init__(self, cluster: Optional[str] = None):
        """
        Initialize calculator.
        
        Args:
            cluster: Optional cluster name to use for RPC calls
        """
        self.cluster = cluster
    
    def calculate_leader_metrics(self, identity: str) -> Dict[str, Any]:
        """
        Calculate leader slot and block production metrics for a validator.
        
        This method focuses on collecting core leadership data.
        
        Args:
            identity: Validator identity pubkey
            
        Returns:
            Dictionary containing leader slot and block production metrics
        """
        # Get necessary data from RPC API
        epoch_info = rpc_api.get_epoch_info(self.cluster)
        current_slot = epoch_info["absoluteSlot"]
        slot_index = epoch_info["slotIndex"]
        slots_in_epoch = epoch_info["slotsInEpoch"]
        
        # Calculate average slot time using performance samples
        avg_slot_time = self._calculate_avg_slot_time()
        
        # Get leader schedule
        leader_schedule = rpc_api.get_leader_schedule(None, identity, self.cluster)
        
        # Get block production information
        block_production = rpc_api.get_block_production(identity, self.cluster)
        
        # Process leader slots
        leader_slots_total = 0
        leader_slots_upcoming = []
        leader_slots_completed = []
        
        if leader_schedule and identity in leader_schedule:
            # Extract leader slots
            leader_slots = [int(slot) for slot in leader_schedule[identity]]
            leader_slots_total = len(leader_slots)
            
            # Separate upcoming and completed slots
            leader_slots_completed = [slot for slot in leader_slots if slot <= slot_index]
            leader_slots_upcoming = [slot for slot in leader_slots if slot > slot_index]
        else:
            leader_slots = []
        
        # Process block production data
        blocks_produced = 0
        leader_slots_skipped = 0
        
        if block_production and "value" in block_production:
            by_identity = block_production["value"].get("byIdentity", {})
            if identity in by_identity:
                # slots_assigned, blocks_produced
                slots_assigned, blocks_produced = by_identity[identity]
                leader_slots_skipped = slots_assigned - blocks_produced
        
        # Calculate skip rate
        skip_rate = 0
        if len(leader_slots_completed) > 0:
            skip_rate = (leader_slots_skipped / len(leader_slots_completed)) * 100
        
        # Get next leader slot
        leader_slot_next = None
        if leader_slots_upcoming:
            leader_slot_next = min(leader_slots_upcoming)
            
        # Calculate time estimates based on current data
        leader_slot_time_data = None
        if leader_slot_next is not None:
            leader_slot_time_data = self.calculate_leader_time_metrics(
                leader_slot_next, slot_index, avg_slot_time
            )
        
        # Compile all metrics into a dictionary
        metrics = {
            # Core metrics
            "leader_slots_total": leader_slots_total,
            "leader_slots_upcoming": leader_slots_upcoming,
            "leader_slots_completed": len(leader_slots_completed),
            "leader_slots_skipped": leader_slots_skipped,
            "blocks_produced": blocks_produced,
            "blocks_produced_upcoming": len(leader_slots_upcoming),
            "skip_rate": skip_rate,
            "leader_slot_next": leader_slot_next,
            "current_slot_index": slot_index,
            "avg_slot_time": avg_slot_time,
        }
        
        # Add time metrics if available
        if leader_slot_time_data:
            metrics.update(leader_slot_time_data)
        
        return metrics
    
    def calculate_leader_time_metrics(self, next_slot: int, current_slot_index: int, 
                                     avg_slot_time: Optional[float] = None) -> Dict[str, Any]:
        """
        Calculate time-based metrics for leader slots.
        
        This method can be called at high frequency to update time displays
        without needing to refresh the core leader data.
        
        Args:
            next_slot: The next leader slot
            current_slot_index: Current slot index in the epoch
            avg_slot_time: Average slot time; if None, calculated from performance samples
            
        Returns:
            Dictionary with time-based metrics:
            - leader_slot_time_remaining: Seconds until next leader slot
            - leader_slot_time: Datetime of next leader slot
        """
        # Calculate avg_slot_time if not provided
        if avg_slot_time is None:
            avg_slot_time = self._calculate_avg_slot_time()
        
        # Calculate time until next leader slot
        slots_until_next = next_slot - current_slot_index
        leader_slot_time_remaining = slots_until_next * avg_slot_time
        leader_slot_time = datetime.now() + timedelta(seconds=leader_slot_time_remaining)
        
        return {
            "leader_slot_time_remaining": leader_slot_time_remaining,
            "leader_slot_time": leader_slot_time,
        }
    
    def update_leader_time_metrics(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update only the time-based metrics in an existing leader metrics dictionary.
        
        This method is useful for high-frequency updates to time displays.
        
        Args:
            metrics: Existing leader metrics dictionary from calculate_leader_metrics()
            
        Returns:
            Updated metrics dictionary with fresh time calculations
        """
        # Get current epoch info
        try:
            epoch_info = rpc_api.get_epoch_info(self.cluster)
            current_slot_index = epoch_info["slotIndex"]
            
            # Update the slot index in metrics
            metrics["current_slot_index"] = current_slot_index
            
            # Update time-based metrics if we have a next leader slot
            if metrics.get("leader_slot_next") is not None:
                time_metrics = self.calculate_leader_time_metrics(
                    metrics["leader_slot_next"], 
                    current_slot_index,
                    metrics.get("avg_slot_time")
                )
                metrics.update(time_metrics)
                
            return metrics
        except Exception as e:
            print(f"Error updating leader time metrics: {e}")
            return metrics
    
    def _calculate_avg_slot_time(self, num_samples: int = 500) -> float:
        """
        Calculate average slot time from performance samples.
        
        Args:
            num_samples: Number of performance samples to use
            
        Returns:
            Average slot time in seconds
        """
        # Get performance samples
        performance_samples = rpc_api.get_recent_performance_samples(num_samples, self.cluster)
        
        # Filter out samples with 0 slots to avoid division by zero
        valid_samples = [s for s in performance_samples if s["numSlots"] > 0]
        
        if not valid_samples:
            return 0.4  # Solana's target slot time as fallback
        
        # Calculate weighted average of slot times
        total_slots = sum(sample["numSlots"] for sample in valid_samples)
        total_time = sum(sample["samplePeriodSecs"] for sample in valid_samples)
        
        return total_time / total_slots if total_slots > 0 else 0.4