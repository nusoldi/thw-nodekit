"""
Solana epoch calculation and analysis.

Provides metrics and utilities for working with Solana epoch data.
"""

from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from thw_nodekit.toolkit.core import rpc_api


class EpochCalculator:
    """
    Calculates and analyses Solana epoch metrics.
    
    This class handles all epoch-related calculations including:
    - Epoch progress and timing
    - Slot timing analysis
    """
    
    def __init__(self, cluster: Optional[str] = None):
        """
        Initialize epoch calculator.
        
        Args:
            cluster: Optional cluster name to use for RPC calls
        """
        self.cluster = cluster
        
    def calculate_epoch_metrics(self, identity: Optional[str] = None, 
                               num_samples: int = 720) -> Dict[str, Any]:
        """
        Calculate various epoch-related metrics including timing and progress.
        
        Args:
            identity: Optional validator identity (not used in this method)
            num_samples: Number of performance samples to use
            
        Returns:
            Dictionary containing epoch metrics
        """
        # Get necessary data from RPC API
        epoch_info = rpc_api.get_epoch_info(self.cluster)
        
        # Calculate slot timing
        avg_slot_time = self._calculate_avg_slot_time(num_samples)
        
        # Extract basic epoch information
        current_slot = epoch_info["absoluteSlot"]
        epoch = epoch_info["epoch"]
        slot_index = epoch_info["slotIndex"]
        slots_in_epoch = epoch_info["slotsInEpoch"]
        
        # Calculate progress percentage
        percent_complete = round((slot_index / slots_in_epoch) * 100, 4)
        
        # Calculate time remaining
        remaining_slots = slots_in_epoch - slot_index
        time_remaining_seconds = remaining_slots * avg_slot_time
        time_remaining = str(timedelta(seconds=round(time_remaining_seconds)))
        
        # Calculate estimated end time
        current_time = datetime.now()
        estimated_end_time = current_time + timedelta(seconds=time_remaining_seconds)
        
        # Compile all metrics into a dictionary
        metrics = {
            "epoch": epoch,
            "current_slot": current_slot,
            "slot_index": slot_index,
            "slots_in_epoch": slots_in_epoch,
            "remaining_slots": remaining_slots,
            "avg_slot_time": avg_slot_time,
            "percent_complete": percent_complete,
            "time_remaining": time_remaining,
            "time_remaining_seconds": time_remaining_seconds,
            "estimated_end_time": estimated_end_time,
        }
        
        return metrics
    
    def _calculate_avg_slot_time(self, num_samples: int = 720) -> float:
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