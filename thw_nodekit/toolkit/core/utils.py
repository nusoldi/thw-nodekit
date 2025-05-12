"""
Utility functions for common operations across the toolkit.
"""

import datetime
from typing import Union, Optional, Tuple
import pytz  # Make sure this is in your requirements.txt


def format_time_remaining(time_remaining: Union[str, int, float, datetime.timedelta]) -> str:
    """
    Format time remaining in a human-readable format.
    
    Args:
        time_remaining: Time value as seconds (int/float), string, or timedelta
        
    Returns:
        Formatted string like "0 days, 2 hours, 30 minutes, 23 seconds"
    """
    # Convert to timedelta if it's seconds as a number or string
    if isinstance(time_remaining, (int, float)):
        td = datetime.timedelta(seconds=time_remaining)
    elif isinstance(time_remaining, str) and time_remaining.isdigit():
        td = datetime.timedelta(seconds=int(time_remaining))
    elif isinstance(time_remaining, datetime.timedelta):
        td = time_remaining
    else:
        # If it's already a formatted string or unknown format, return as is
        return str(time_remaining)
    
    # Calculate components
    total_seconds = int(td.total_seconds())
    days, remainder = divmod(total_seconds, 86400)  # 86400 seconds in a day
    hours, remainder = divmod(remainder, 3600)      # 3600 seconds in an hour
    minutes, seconds = divmod(remainder, 60)        # 60 seconds in a minute
    
    # Format with pluralization
    day_text = f"{days} day{'s' if days != 1 else ''}"
    hour_text = f"{hours} hour{'s' if hours != 1 else ''}"
    minute_text = f"{minutes} min"
    second_text = f"{seconds} sec"

    # Combine both formats
    return f"{day_text}, {hour_text}, {minute_text}, {second_text}"


def format_timestamp(timestamp: Union[int, float, datetime.datetime], 
                    format_type: str = "iso", 
                    timezone: Optional[str] = None) -> str:
    """
    Format a timestamp in the specified format.
    
    Args:
        timestamp: Unix timestamp or datetime object
        format_type: Format type ("iso", "human", "both")
        timezone: Optional timezone name (default is UTC)
        
    Returns:
        Formatted timestamp string
    """
    # Convert to datetime if it's a timestamp
    if isinstance(timestamp, (int, float)):
        dt = datetime.datetime.fromtimestamp(timestamp, tz=datetime.timezone.utc)
    elif isinstance(timestamp, datetime.datetime):
        # Ensure the datetime has timezone info
        if timestamp.tzinfo is None:
            dt = timestamp.replace(tzinfo=datetime.timezone.utc)
        else:
            dt = timestamp
    else:
        # Invalid input
        return str(timestamp)
    
    # Convert to the specified timezone if provided
    if timezone:
        try:
            target_tz = pytz.timezone(timezone)
            dt = dt.astimezone(target_tz)
        except pytz.exceptions.UnknownTimeZoneError:
            # If timezone is invalid, keep as is
            pass
    
    # Format based on type
    if format_type == "iso":
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    elif format_type == "human":
        # Format like "Sun Apr 6, 11:57 PM"
        return dt.strftime("%a %b %-d, %I:%M %p").replace(" 0", " ")
    elif format_type == "both":
        iso_format = dt.strftime("%Y-%m-%d %H:%M:%S")
        human_format = dt.strftime("%a %b %-d, %I:%M %p").replace(" 0", " ")
        return f"{iso_format} | {human_format}"
    else:
        return dt.isoformat()


def convert_timezone(dt: datetime.datetime, 
                    target_timezone: str) -> datetime.datetime:
    """
    Convert a datetime object to a different timezone.
    
    Args:
        dt: Datetime object to convert
        target_timezone: Target timezone name
        
    Returns:
        Datetime object in the target timezone
    """
    # Ensure the datetime has timezone info
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    
    # Convert to the target timezone
    try:
        target_tz = pytz.timezone(target_timezone)
        return dt.astimezone(target_tz)
    except pytz.exceptions.UnknownTimeZoneError:
        # If timezone is invalid, return original
        return dt


def ensure_utc(dt: Union[datetime.datetime, int, float]) -> datetime.datetime:
    """
    Ensure a datetime object is in UTC.
    
    Args:
        dt: Datetime object or timestamp
        
    Returns:
        Datetime object in UTC
    """
    if isinstance(dt, (int, float)):
        return datetime.datetime.fromtimestamp(dt, tz=datetime.timezone.utc)
    elif isinstance(dt, datetime.datetime):
        if dt.tzinfo is None:
            return dt.replace(tzinfo=datetime.timezone.utc)
        return dt.astimezone(datetime.timezone.utc)
    else:
        raise TypeError("Input must be a datetime object or timestamp")


def get_current_time(timezone: Optional[str] = None) -> datetime.datetime:
    """
    Get the current time in the specified timezone.
    
    Args:
        timezone: Optional timezone name (default is UTC)
        
    Returns:
        Current datetime in the specified timezone
    """
    current_time = datetime.datetime.now(datetime.timezone.utc)
    
    if timezone:
        try:
            target_tz = pytz.timezone(timezone)
            return current_time.astimezone(target_tz)
        except pytz.exceptions.UnknownTimeZoneError:
            pass
    
    return current_time

def colorize(text, color_code):
    """Add color to terminal output.

    Args:
        text (str): The text to be colorized.
        color_code (str): The ANSI color code as a string (e.g., "31" for red, "32" for green).
    """
    return f"\033[{color_code}m{text}\033[0m"

def green(text):
    """Format text as green."""
    if text is None:
        text = ""
    return f"\033[92m{text}\033[0m"

def yellow(text):
    """Format text as yellow."""
    if text is None:
        text = ""
    return f"\033[93m{text}\033[0m"

def red(text):
    """Format text as red."""
    if text is None:
        text = ""
    return f"\033[91m{text}\033[0m"

def blue(text):
    """Format text as blue."""
    if text is None:
        text = ""
    return f"\033[94m{text}\033[0m"

def bold_green(text):
    """Format text as bold green."""
    if text is None:
        text = ""
    return f"\033[1;92m{text}\033[0m"

def bold_yellow(text):
    """Format text as bold yellow."""
    if text is None:
        text = ""
    return f"\033[1;93m{text}\033[0m"

def bright_cyan(text):
    """Format text as bright cyan."""
    if text is None:
        text = ""
    return f"\033[96m{text}\033[0m"