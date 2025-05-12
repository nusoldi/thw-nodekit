"""
Utilities for working with IP addresses, geolocation, and IP metadata.
"""

import ipinfo
from typing import Dict, Any, Optional
from functools import lru_cache
from thw_nodekit.config import get_config

def get_ip_info(ip_address: str, token: Optional[str] = None, cache: bool = True) -> Dict[str, Any]:
    """
    Retrieve information about an IP address using the ipinfo.io API.
    
    Args:
        ip_address: The IP address to look up
        token: Optional API token for ipinfo.io (for higher rate limits)
        cache: Whether to cache results to reduce API calls
        
    Returns:
        Dictionary containing information about the IP address including:
        - ip: IP address
        - hostname: Hostname (if available)
        - city: City location
        - region: Region/state
        - country: Country code
        - country_name: Full country name
        - loc: Latitude,longitude
        - org: Organization/ISP
        - asn: AS number
        - org_name: Organization name without ASN
        - va_format: VA-style format string
        
    Raises:
        RuntimeError: If the API request fails
    """
    if token is None:
        config = get_config()
        token = config.get("toolkit.ipinfo_token")
        
    if cache:
        return _get_ip_info_cached(ip_address, token)
    else:
        return _get_ip_info_uncached(ip_address, token)

@lru_cache(maxsize=1024)
def _get_ip_info_cached(ip_address: str, token: Optional[str] = None) -> Dict[str, Any]:
    """Cached version of the IP info retrieval function"""
    return _get_ip_info_uncached(ip_address, token)

def _get_ip_info_uncached(ip_address: str, token: Optional[str] = None) -> Dict[str, Any]:
    """Uncached implementation of IP info retrieval"""
    try:
        # Create a handler with the token
        handler = ipinfo.getHandler(token)
        
        # Get the details for the IP
        details = handler.getDetails(ip_address)
        ip_data = details.all
        
        # Enhance the data with additional processed fields
        result = dict(ip_data)
        
        # Process organization info to extract ASN
        org_info = ip_data.get('org', '')
        if org_info and ' ' in org_info and org_info.startswith('AS'):
            asn, org = org_info.split(' ', 1)
            result['asn'] = asn
            result['org_name'] = org
        else:
            result['asn'] = 'AS0'
            result['org_name'] = org_info
        
        # Create VA-style format string
        country = ip_data.get('country', 'Unknown')
        city = ip_data.get('city', 'Unknown')
        asn_num = result['asn'][2:] if result['asn'].startswith('AS') else result['asn']
        result['va_format'] = f"{asn_num}-{country}-{city}"
        
        return result
    except Exception as e:
        raise RuntimeError(f"Failed to retrieve IP information: {str(e)}")