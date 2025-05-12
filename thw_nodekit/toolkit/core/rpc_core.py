"""
Core Solana JSON-RPC client handling connection and communication.
"""

import time
import json
import requests
from typing import Any, Dict, List, Optional, Union
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class RPC_Core:
    """
    Core JSON-RPC client for Solana blockchain communication.
    
    Handles low-level communication, connection management, and failover
    without concern for specific Solana methods or business logic.
    """
    
    def __init__(self, urls: List[str], timeout: int = 30, max_retries: int = 3):
        """
        Initialize RPC client with multiple endpoint URLs.
        
        Args:
            urls: List of RPC endpoint URLs to use (with failover)
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts per URL
        """
        if not urls:
            raise ValueError("At least one RPC URL must be provided")
            
        self.urls = urls
        self.timeout = timeout
        self.max_retries = max_retries
        self.current_url_index = 0
        
        # Configure session with connection pooling for performance
        self.session = self._configure_session()
        
    def _configure_session(self) -> requests.Session:
        """Configure HTTP session with connection pooling and retries."""
        session = requests.Session()
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=0,  # We handle retries manually with URL rotation
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["POST"]
        )
        
        # Configure connection pooling
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=10,
            pool_maxsize=100
        )
        
        # Mount adapter for both http and https
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        return session
        
    @property
    def current_url(self) -> str:
        """Get current active RPC URL."""
        return self.urls[self.current_url_index]
        
    def _next_url(self) -> None:
        """Rotate to next available RPC URL."""
        self.current_url_index = (self.current_url_index + 1) % len(self.urls)
        
    def call(self, method: str, params: Optional[List[Any]] = None) -> Any:
        """
        Make JSON-RPC call to Solana blockchain.
        
        Args:
            method: RPC method name
            params: Method parameters (optional)
            
        Returns:
            Parsed response result
            
        Raises:
            RuntimeError: If all endpoints fail
        """
        params = params or []
        attempts = 0
        last_error = None
        
        # Try each URL up to max_retries times
        while attempts < self.max_retries * len(self.urls):
            try:
                payload = {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": method,
                    "params": params
                }
                
                response = self.session.post(
                    self.current_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=self.timeout
                )
                response.raise_for_status()
                result = response.json()
                
                if "error" in result:
                    error = result["error"]
                    raise RuntimeError(f"RPC error: {error.get('message')}")
                    
                return result.get("result")
                
            except Exception as e:
                last_error = e
                print(f"RPC error with {self.current_url}: {e}")
                
                # Try next URL
                self._next_url()
                attempts += 1
                time.sleep(0.5)
                
        # All attempts failed
        raise RuntimeError(f"All RPC endpoints failed after {self.max_retries} attempts each: {str(last_error)}")
        
    def batch_call(self, requests: List[Dict[str, Any]]) -> List[Any]:
        """
        Make multiple RPC calls in a single batch request.
        
        Args:
            requests: List of {method, params} dictionaries
            
        Returns:
            List of results in same order as requests
        """
        payload = []
        for i, req in enumerate(requests):
            payload.append({
                "jsonrpc": "2.0",
                "id": i + 1,
                "method": req.get("method"),
                "params": req.get("params", [])
            })
        
        attempts = 0
        last_error = None
        
        # Try each URL up to max_retries times
        while attempts < self.max_retries * len(self.urls):
            try:
                response = self.session.post(
                    self.current_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=self.timeout
                )
                
                response.raise_for_status()
                responses = response.json()
                
                # For batch requests, response is a list
                if not isinstance(responses, list):
                    raise ValueError("Expected batch response to be a list")
                
                # Extract results in proper order
                results = []
                responses_by_id = {r.get("id"): r for r in responses}
                
                for i in range(1, len(requests) + 1):
                    if i in responses_by_id:
                        resp = responses_by_id[i]
                        if "error" in resp:
                            error = resp["error"]
                            results.append({
                                "success": False,
                                "error": f"RPC Error {error.get('code')}: {error.get('message')}"
                            })
                        else:
                            results.append({
                                "success": True,
                                "result": resp.get("result")
                            })
                    else:
                        results.append({
                            "success": False,
                            "error": "Missing response"
                        })
                
                return results
                
            except Exception as e:
                last_error = e
                print(f"Batch RPC error with {self.current_url}: {str(e)}")
                
                # Try next URL
                self._next_url()
                attempts += 1
                
                # Add small delay between retries
                time.sleep(0.5)
        
        # All endpoints failed
        raise RuntimeError(f"All RPC endpoints failed after {attempts} attempts: {str(last_error)}")