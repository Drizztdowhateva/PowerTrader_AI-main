"""
Exchange API Utilities

Common helper functions and classes for implementing exchange APIs.
Reduces boilerplate code when adding new platforms.
"""

import hmac
import hashlib
import time
import json
import threading
from typing import Dict, Tuple, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
import requests


class AuthMethod(Enum):
    """Supported authentication methods"""
    HMAC_SHA256 = "hmac-sha256"
    HMAC_SHA512 = "hmac-sha512"
    ED25519 = "ed25519"
    RSA = "rsa"
    BEARER_TOKEN = "bearer"
    API_KEY = "api_key"


class APIClientBase:
    """Base class for exchange API clients
    
    Provides common functionality like request signing, error handling,
    rate limiting, and retry logic.
    
    Subclass this for each exchange instead of building from scratch.
    """
    
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        base_url: str,
        auth_method: AuthMethod = AuthMethod.HMAC_SHA256,
        timeout: int = 10
    ):
        """Initialize API client
        
        Args:
            api_key: API key credential
            api_secret: API secret credential
            base_url: Base URL for API endpoints (e.g., "https://api.exchange.com/v1")
            auth_method: Which authentication method to use
            timeout: Request timeout in seconds
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = base_url
        self.auth_method = auth_method
        self.timeout = timeout
        
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "PowerTrader/1.0"
        })
        
        self.rate_limit_remaining = None
        self.rate_limit_reset = None
    
    def _sign_hmac_sha256(self, message: str) -> str:
        """Sign message with HMAC-SHA256
        
        Args:
            message: Message to sign
            
        Returns:
            Hex-encoded signature
        """
        return hmac.new(
            self.api_secret.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
    
    def _sign_hmac_sha512(self, message: str) -> str:
        """Sign message with HMAC-SHA512
        
        Args:
            message: Message to sign
            
        Returns:
            Hex-encoded signature
        """
        return hmac.new(
            self.api_secret.encode(),
            message.encode(),
            hashlib.sha512
        ).hexdigest()
    
    def _sign_ed25519(self, message: str) -> str:
        """Sign message with ED25519 (Robinhood style)
        
        Args:
            message: Message to sign
            
        Returns:
            Hex-encoded signature
        
        Note: Override this in subclass if you have ED25519 implementation
        """
        raise NotImplementedError("Override in subclass for ED25519 signing")
    
    def _build_headers(
        self,
        timestamp: str,
        signature: str,
        method: str,
        path: str
    ) -> Dict[str, str]:
        """Build request headers with authentication
        
        Override in subclass to customize header format
        
        Args:
            timestamp: Request timestamp
            signature: Request signature
            method: HTTP method
            path: API path
            
        Returns:
            Dict of headers
        """
        headers = {
            "X-API-Key": self.api_key,
            "X-API-Signature": signature,
            "X-API-Timestamp": timestamp
        }
        return headers
    
    def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict] = None,
        json_data: Optional[Dict] = None,
        authenticated: bool = True
    ) -> requests.Response:
        """Make HTTP request with automatic signing and error handling
        
        Args:
            method: HTTP method (GET, POST, DELETE, etc.)
            path: API path (relative, without base URL)
            params: URL query parameters
            json_data: JSON request body
            authenticated: Whether to add authentication headers
            
        Returns:
            Response object
            
        Raises:
            requests.RequestException on network errors
        """
        url = f"{self.base_url}{path}"
        
        headers = {}
        
        if authenticated:
            timestamp = str(int(time.time()))
            body = json.dumps(json_data) if json_data else ""
            
            # Build message for signing
            message = f"{self.api_key}{timestamp}{path}{method}{body}"
            
            if self.auth_method == AuthMethod.HMAC_SHA256:
                signature = self._sign_hmac_sha256(message)
            elif self.auth_method == AuthMethod.HMAC_SHA512:
                signature = self._sign_hmac_sha512(message)
            elif self.auth_method == AuthMethod.ED25519:
                signature = self._sign_ed25519(message)
            else:
                signature = ""
            
            headers = self._build_headers(timestamp, signature, method, path)
        
        try:
            response = self.session.request(
                method,
                url,
                params=params,
                json=json_data,
                headers=headers,
                timeout=self.timeout
            )
            
            # Track rate limits from response headers
            if "X-RateLimit-Remaining" in response.headers:
                self.rate_limit_remaining = int(response.headers["X-RateLimit-Remaining"])
            
            if "X-RateLimit-Reset" in response.headers:
                self.rate_limit_reset = int(response.headers["X-RateLimit-Reset"])
            
            return response
        
        except requests.Timeout:
            raise requests.RequestException(f"Request timeout after {self.timeout}s")
        except requests.ConnectionError as e:
            raise requests.RequestException(f"Connection failed: {e}")
    
    def _get(self, path: str, params: Optional[Dict] = None, **kwargs) -> Dict:
        """Make authenticated GET request
        
        Args:
            path: API path
            params: Query parameters
            **kwargs: Additional arguments for _request()
            
        Returns:
            JSON response as dict
        """
        response = self._request("GET", path, params=params, **kwargs)
        response.raise_for_status()
        return response.json()
    
    def _post(self, path: str, json_data: Optional[Dict] = None, **kwargs) -> Dict:
        """Make authenticated POST request
        
        Args:
            path: API path
            json_data: Request body
            **kwargs: Additional arguments for _request()
            
        Returns:
            JSON response as dict
        """
        response = self._request("POST", path, json_data=json_data, **kwargs)
        response.raise_for_status()
        return response.json()
    
    def _delete(self, path: str, **kwargs) -> Dict:
        """Make authenticated DELETE request
        
        Args:
            path: API path
            **kwargs: Additional arguments for _request()
            
        Returns:
            JSON response as dict (if any)
        """
        response = self._request("DELETE", path, **kwargs)
        response.raise_for_status()
        
        if response.text:
            return response.json()
        return {}
    
    def close(self):
        """Close the session"""
        self.session.close()


class MarketDataClient(APIClientBase):
    """Base class for market data fetching
    
    Extend this class for exchange-specific market data implementations
    """
    
    def get_klines(
        self,
        symbol: str,
        interval: str,
        limit: int = 1000,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None
    ) -> List[Tuple]:
        """Fetch OHLCV candles
        
        Override in subclass for exchange-specific implementation
        
        Args:
            symbol: Trading pair (e.g., "BTC-USD", "BTC/USDT")
            interval: Timeframe (e.g., "1m", "5m", "1h", "1d")
            limit: Max candles to return
            start_time: Optional start timestamp (ms)
            end_time: Optional end timestamp (ms)
            
        Returns:
            List of (timestamp, open, high, low, close, volume) tuples
        """
        raise NotImplementedError("Override in exchange-specific subclass")
    
    def get_ticker(self, symbol: str) -> Dict[str, float]:
        """Get current ticker data
        
        Args:
            symbol: Trading pair
            
        Returns:
            Dict with bid, ask, last, volume, etc.
        """
        raise NotImplementedError("Override in exchange-specific subclass")
    
    def get_depth(self, symbol: str, limit: int = 20) -> Dict[str, List]:
        """Get order book
        
        Args:
            symbol: Trading pair
            limit: Number of levels per side
            
        Returns:
            Dict with 'bids' and 'asks' lists
        """
        raise NotImplementedError("Override in exchange-specific subclass")


class TradingClient(APIClientBase):
    """Base class for trading functionality
    
    Extend this class for exchange-specific trading implementations
    """
    
    def place_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        order_type: str = "market",
        price: Optional[float] = None,
        stop_price: Optional[float] = None,
        take_profit: Optional[float] = None,
        time_in_force: str = "GTC"
    ) -> Dict[str, Any]:
        """Place an order
        
        Override in subclass for exchange-specific implementation
        
        Args:
            symbol: Trading pair
            side: "buy" or "sell"
            quantity: Amount to trade
            order_type: "market", "limit", "stop_loss", "take_profit", etc.
            price: Limit price (required for limit orders)
            stop_price: Stop price (for stop orders)
            take_profit: Take profit price
            time_in_force: "GTC" (good til cancel), "IOC" (immediate or cancel), etc.
            
        Returns:
            Order details dict with order_id, status, etc.
        """
        raise NotImplementedError("Override in exchange-specific subclass")
    
    def cancel_order(self, symbol: str, order_id: str) -> bool:
        """Cancel an order
        
        Args:
            symbol: Trading pair
            order_id: Order ID to cancel
            
        Returns:
            True if successful
        """
        raise NotImplementedError("Override in exchange-specific subclass")
    
    def get_order(self, symbol: str, order_id: str) -> Dict[str, Any]:
        """Get order status
        
        Args:
            symbol: Trading pair
            order_id: Order ID
            
        Returns:
            Order details dict
        """
        raise NotImplementedError("Override in exchange-specific subclass")
    
    def get_open_orders(self, symbol: Optional[str] = None) -> List[Dict]:
        """Get all open orders
        
        Args:
            symbol: Optional - filter by trading pair
            
        Returns:
            List of open order dicts
        """
        raise NotImplementedError("Override in exchange-specific subclass")
    
    def get_account_balance(self) -> Dict[str, float]:
        """Get account balance for all coins
        
        Returns:
            Dict mapping coin symbols to balances
        """
        raise NotImplementedError("Override in exchange-specific subclass")
    
    def get_account_value(self, reference_currency: str = "USD") -> float:
        """Get total account value in reference currency
        
        Args:
            reference_currency: Currency to value account in
            
        Returns:
            Total account value
        """
        raise NotImplementedError("Override in exchange-specific subclass")


@dataclass
class RateLimitInfo:
    """Rate limit information from API"""
    limit: int
    remaining: int
    reset_time: int
    reset_seconds: float


class RateLimiter:
    """Simple rate limiter for API calls"""
    
    def __init__(self, calls_per_second: float = 10):
        """Initialize rate limiter
        
        Args:
            calls_per_second: Max API calls allowed per second
        """
        self.calls_per_second = calls_per_second
        self.min_interval = 1.0 / calls_per_second
        self.last_call = 0
        self.lock = threading.Lock()
    
    def wait_if_needed(self):
        """Wait before making next call if needed"""
        with self.lock:
            elapsed = time.time() - self.last_call
            if elapsed < self.min_interval:
                time.sleep(self.min_interval - elapsed)
            self.last_call = time.time()


# Example: Minimal exchange implementation using these utilities

class ExampleExchange(TradingClient):
    """Example implementation for 'ExampleExchange' platform"""
    
    def __init__(self, api_key: str, api_secret: str):
        super().__init__(
            api_key=api_key,
            api_secret=api_secret,
            base_url="https://api.example.com/v1",
            auth_method=AuthMethod.HMAC_SHA256
        )
        self.rate_limiter = RateLimiter(calls_per_second=10)
    
    def get_ticker(self, symbol: str) -> Dict[str, float]:
        """Get current price"""
        self.rate_limiter.wait_if_needed()
        
        data = self._get(
            "/ticker",
            params={"symbol": symbol},
            authenticated=False
        )
        
        return {
            "bid": float(data.get("bid", 0)),
            "ask": float(data.get("ask", 0)),
            "last": float(data.get("last", 0)),
            "volume": float(data.get("volume", 0))
        }
    
    def place_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        order_type: str = "market",
        price: Optional[float] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Place an order"""
        self.rate_limiter.wait_if_needed()
        
        payload = {
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "order_type": order_type
        }
        
        if price:
            payload["price"] = price
        
        response = self._post("/orders", json_data=payload)
        
        return {
            "order_id": response.get("id"),
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "status": response.get("status"),
            "filled": response.get("filled", 0)
        }
    
    def get_account_value(self, reference_currency: str = "USD") -> float:
        """Get total account value"""
        self.rate_limiter.wait_if_needed()
        
        data = self._get("/account")
        return float(data.get("total_value", 0))


if __name__ == "__main__":
    # Test the utilities
    print("Exchange API Utilities - Ready for import")
    print("Available classes:")
    print("  - APIClientBase: Generic API client")
    print("  - MarketDataClient: For market data APIs")
    print("  - TradingClient: For trading APIs")
    print("  - RateLimiter: API rate limiting")
    print("  - ExampleExchange: Minimal working example")
