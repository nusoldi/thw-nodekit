"""Base display class for consistent formatting across trackers."""

import os
import sys
import datetime
import time
from typing import Dict, Any, List, Optional

from thw_nodekit.toolkit.core.utils import green, red, bold_yellow, bright_cyan, bold_green
from thw_nodekit.toolkit.display.constants import APP_NAME

class BaseTrackerDisplay:
    """Base class for tracker displays with common formatting methods."""
    
    def clear_screen(self):
        """Clear terminal screen in a cross-platform way."""
        os.system('cls' if sys.platform == "win32" else 'clear')
    
    def create_header(self, title):
        """Create a standardized header."""
        return f"{('=======================')}{bold_green(f'| {APP_NAME}: {title} |')}{bold_green('=======================')}"
    
    def create_separator(self):
        """Create a standardized separator line."""
        return f"{('-' * 84)}"
    
    def format_label(self, label, width=18):
        """Format a label with consistent width."""
        return f"{bright_cyan(label.ljust(width))}"
    
    def format_timestamp(self):
        """Format current timestamp."""
        return datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    def format_cache_age(self, cache_ages):
        """Format cache age information."""
        return (bright_cyan("Cache:") + " Credits " + str(cache_ages['validators']) + "s | "
                + "Info " + str(cache_ages['validator_info']) + "s | "
                + "Gossip " + str(cache_ages['gossip']) + "s") 
    
    def format_delta(self, value, positive_is_good=True):
        """Format delta values with appropriate colors."""
        if value > 0:
            return green(f" (+{value})") if positive_is_good else red(f" (+{value})")
        elif value < 0:
            return red(f" ({value})") if positive_is_good else green(f" ({value})")
        return " (+0)"
    
    def format_credit_diff(self, value, positive_is_good=False):
        """Format credit difference without parentheses."""
        if value > 0:
            return green(f"+{value}") if positive_is_good else red(f"+{value}")
        elif value < 0:
            return red(f"{value}") if positive_is_good else green(f"{value}")
        return "+0"
    
    def format_name(self, name: str, max_length: int = 25) -> str:
        """Format entity name to fit in display."""
        if not name or name == "Unknown":
            return "Unknown"
        
        if len(name) > max_length:
            return name[:max_length-3] + "..."
        return name
    
    def display_footer(self):
        """Display standardized footer."""
        return f"{bold_yellow('Press Ctrl+C to quit')}"