"""
API Provider Abstraction Layer for PowerTrader AI

This module provides a unified interface for different cryptocurrency exchange APIs,
making it easy to add support for new platforms.

Currently supported providers:
- Market Data: KuCoin, Binance, Coinbase, CoinGecko (fallback)
- Trading: Robinhood, Binance, Coinbase
"""

import os
import time
import base64
import hmac
import hashlib
import json
import requests
from typing import Dict, List, Optional, Tuple, Any
from abc import ABC, abstractmethod
from datetime import datetime
from nacl.signing import SigningKey


# ============================================================================
# Base Classes for API Abstraction
# ============================================================================

class MarketDataProvider(ABC):
    """Base class for market data providers."""
    
    @abstractmethod
    def get_klines(self, symbol: str, timeframe: str, limit: int = 1500) -> List[List]:
        """
        Get candlestick/kline data.
        
        Args:
            symbol: Trading pair symbol (e.g., 'BTC-USDT', 'BTC-USD')
            timeframe: Timeframe string (e.g., '1hour', '1day', '1week')
            limit: Maximum number of candles to return
            
        Returns:
            List of candles, each candle is a list: [timestamp, open, close, high, low, volume]
            Note: This order matches KuCoin's format for consistency
        """
        pass
    
    @abstractmethod
    def get_current_price(self, symbol: str) -> Dict[str, float]:
        """
        Get current price for a symbol.
        
        Args:
            symbol: Trading pair symbol
            
        Returns:
            Dict with 'bid' and 'ask' prices
        """
        pass
    
    @abstractmethod
    def normalize_symbol(self, symbol: str) -> str:
        """Convert symbol to provider-specific format."""
        pass


class TradingProvider(ABC):
    """Base class for trading execution providers."""
    
    @abstractmethod
    def place_buy_order(self, symbol: str, amount_usd: float, **kwargs) -> Dict[str, Any]:
        """Place a market buy order."""
        pass
    
    @abstractmethod
    def place_sell_order(self, symbol: str, quantity: float, **kwargs) -> Dict[str, Any]:
        """Place a market sell order."""
        pass
    
    @abstractmethod
    def get_account_info(self) -> Dict[str, Any]:
        """Get account balance and holdings information."""
        pass
    
    @abstractmethod
    def get_orders(self, symbol: str) -> List[Dict[str, Any]]:
        """Get order history for a symbol."""
        pass
    
    @abstractmethod
    def normalize_symbol(self, symbol: str) -> str:
        """Convert symbol to provider-specific format."""
        pass


# ============================================================================
# Market Data Providers
# ============================================================================

class KuCoinMarketData(MarketDataProvider):
    """KuCoin market data provider (existing implementation)."""
    
    def __init__(self):
        self.base_url = "https://api.kucoin.com"
        self.market_client = None
        try:
            from kucoin.client import Market
            self.market_client = Market(url=self.base_url)
        except ImportError:
            pass
    
    def normalize_symbol(self, symbol: str) -> str:
        """Convert symbol to KuCoin format (BTC-USDT)."""
        symbol = symbol.upper().strip()
        if '-' not in symbol:
            return f"{symbol}-USDT"
        return symbol
    
    def _map_timeframe(self, tf: str) -> str:
        """Map standard timeframe to KuCoin format."""
        tf_map = {
            '1min': '1min', '3min': '3min', '5min': '5min', '15min': '15min',
            '30min': '30min', '1hour': '1hour', '2hour': '2hour', '4hour': '4hour',
            '6hour': '6hour', '8hour': '8hour', '12hour': '12hour',
            '1day': '1day', '1week': '1week'
        }
        return tf_map.get(tf, tf)
    
    def get_klines(self, symbol: str, timeframe: str, limit: int = 1500) -> List[List]:
        """Get klines from KuCoin."""
        symbol = self.normalize_symbol(symbol)
        tf = self._map_timeframe(timeframe)
        
        # Try with kucoin-python client first
        if self.market_client:
            try:
                return self.market_client.get_kline(symbol, tf)
            except Exception:
                pass
        
        # Fallback to REST API
        try:
            url = f"{self.base_url}/api/v1/market/candles"
            params = {'type': tf, 'symbol': symbol}
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            return data.get('data', []) if isinstance(data, dict) else data
        except Exception:
            return []
    
    def get_current_price(self, symbol: str) -> Dict[str, float]:
        """Get current price from KuCoin."""
        symbol = self.normalize_symbol(symbol)
        try:
            url = f"{self.base_url}/api/v1/market/orderbook/level1"
            params = {'symbol': symbol}
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            if data.get('code') == '200000' and 'data' in data:
                price_data = data['data']
                return {
                    'bid': float(price_data.get('bestBid', 0)),
                    'ask': float(price_data.get('bestAsk', 0))
                }
        except Exception:
            pass
        return {'bid': 0.0, 'ask': 0.0}


class BinanceMarketData(MarketDataProvider):
    """Binance market data provider."""
    
    def __init__(self, use_us: bool = False):
        self.base_url = "https://api.binance.us" if use_us else "https://api.binance.com"
    
    def normalize_symbol(self, symbol: str) -> str:
        """Convert symbol to Binance format (BTCUSDT - no separator)."""
        symbol = symbol.upper().strip().replace('-', '').replace('_', '')
        if not symbol.endswith('USDT'):
            symbol = f"{symbol}USDT"
        return symbol
    
    def _map_timeframe(self, tf: str) -> str:
        """Map standard timeframe to Binance format."""
        tf_map = {
            '1min': '1m', '3min': '3m', '5min': '5m', '15min': '15m', '30min': '30m',
            '1hour': '1h', '2hour': '2h', '4hour': '4h', '6hour': '6h', '8hour': '8h', '12hour': '12h',
            '1day': '1d', '3day': '3d', '1week': '1w', '1month': '1M'
        }
        return tf_map.get(tf, '1h')
    
    def get_klines(self, symbol: str, timeframe: str, limit: int = 1500) -> List[List]:
        """Get klines from Binance."""
        symbol = self.normalize_symbol(symbol)
        interval = self._map_timeframe(timeframe)
        
        try:
            url = f"{self.base_url}/api/v3/klines"
            params = {
                'symbol': symbol,
                'interval': interval,
                'limit': min(limit, 1000)  # Binance max is 1000
            }
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            
            # Convert Binance format to standard format
            # Binance: [timestamp, open, high, low, close, volume, ...]
            # Standard: [timestamp, open, close, high, low, volume]
            result = []
            for candle in data:
                result.append([
                    str(int(candle[0]) // 1000),  # Convert ms to seconds
                    candle[1],  # open
                    candle[4],  # close
                    candle[2],  # high
                    candle[3],  # low
                    candle[5]   # volume
                ])
            return result
        except Exception:
            return []
    
    def get_current_price(self, symbol: str) -> Dict[str, float]:
        """Get current price from Binance."""
        symbol = self.normalize_symbol(symbol)
        try:
            url = f"{self.base_url}/api/v3/ticker/bookTicker"
            params = {'symbol': symbol}
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            return {
                'bid': float(data.get('bidPrice', 0)),
                'ask': float(data.get('askPrice', 0))
            }
        except Exception:
            pass
        return {'bid': 0.0, 'ask': 0.0}


class CoinbaseMarketData(MarketDataProvider):
    """Coinbase (Advanced Trade API) market data provider."""
    
    def __init__(self):
        self.base_url = "https://api.coinbase.com"
    
    def normalize_symbol(self, symbol: str) -> str:
        """Convert symbol to Coinbase format (BTC-USD)."""
        symbol = symbol.upper().strip()
        if '-' not in symbol:
            return f"{symbol}-USD"
        return symbol
    
    def _map_timeframe(self, tf: str) -> int:
        """Map standard timeframe to Coinbase granularity (seconds)."""
        tf_map = {
            '1min': 60, '5min': 300, '15min': 900, '30min': 1800,
            '1hour': 3600, '2hour': 7200, '6hour': 21600,
            '1day': 86400, '1week': 604800
        }
        return tf_map.get(tf, 3600)
    
    def get_klines(self, symbol: str, timeframe: str, limit: int = 1500) -> List[List]:
        """Get klines from Coinbase."""
        symbol = self.normalize_symbol(symbol)
        granularity = self._map_timeframe(timeframe)
        
        try:
            # Coinbase returns max 300 candles per request
            url = f"{self.base_url}/api/v3/brokerage/products/{symbol}/candles"
            params = {
                'granularity': str(granularity),
                'limit': min(limit, 300)
            }
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            
            # Convert Coinbase format to standard format
            # Coinbase: {candles: [{start, low, high, open, close, volume}, ...]}
            # Standard: [timestamp, open, close, high, low, volume]
            result = []
            candles = data.get('candles', [])
            for candle in candles:
                result.append([
                    candle.get('start', '0'),
                    candle.get('open', '0'),
                    candle.get('close', '0'),
                    candle.get('high', '0'),
                    candle.get('low', '0'),
                    candle.get('volume', '0')
                ])
            return result
        except Exception:
            return []
    
    def get_current_price(self, symbol: str) -> Dict[str, float]:
        """Get current price from Coinbase."""
        symbol = self.normalize_symbol(symbol)
        try:
            url = f"{self.base_url}/api/v3/brokerage/products/{symbol}/ticker"
            resp = requests.get(url, params={}, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            price = float(data.get('price', 0))
            return {
                'bid': price * 0.9995,  # Approximate bid/ask spread
                'ask': price * 1.0005
            }
        except Exception:
            pass
        return {'bid': 0.0, 'ask': 0.0}


class CoinGeckoMarketData(MarketDataProvider):
    """CoinGecko market data provider (fallback/free tier)."""
    
    def __init__(self):
        self.base_url = "https://api.coingecko.com/api/v3"
        self._coin_id_cache = {}
    
    def normalize_symbol(self, symbol: str) -> str:
        """Convert symbol to CoinGecko coin ID."""
        symbol = symbol.upper().strip().replace('-USD', '').replace('-USDT', '')
        
        # Common mappings
        coin_map = {
            'BTC': 'bitcoin', 'ETH': 'ethereum', 'XRP': 'ripple',
            'BNB': 'binancecoin', 'DOGE': 'dogecoin', 'ADA': 'cardano',
            'SOL': 'solana', 'MATIC': 'matic-network', 'DOT': 'polkadot',
            'AVAX': 'avalanche-2', 'LINK': 'chainlink'
        }
        return coin_map.get(symbol, symbol.lower())
    
    def _map_timeframe(self, tf: str) -> int:
        """Map timeframe to CoinGecko days parameter."""
        tf_map = {
            '1min': 1, '5min': 1, '15min': 1, '30min': 1, '1hour': 1,
            '4hour': 7, '1day': 30, '1week': 90
        }
        return tf_map.get(tf, 7)
    
    def get_klines(self, symbol: str, timeframe: str, limit: int = 1500) -> List[List]:
        """Get price history from CoinGecko (limited granularity)."""
        coin_id = self.normalize_symbol(symbol)
        days = self._map_timeframe(timeframe)
        
        try:
            url = f"{self.base_url}/coins/{coin_id}/market_chart"
            params = {
                'vs_currency': 'usd',
                'days': days,
                'interval': 'hourly' if days <= 7 else 'daily'
            }
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            
            # CoinGecko only provides [timestamp, price] pairs
            # We'll approximate OHLC data
            prices = data.get('prices', [])
            result = []
            for i, price_point in enumerate(prices):
                timestamp = str(int(price_point[0]) // 1000)
                price = price_point[1]
                # Approximate OHLC with same price (not ideal but works for signals)
                result.append([timestamp, str(price), str(price), str(price), str(price), '0'])
            
            return result
        except Exception:
            return []
    
    def get_current_price(self, symbol: str) -> Dict[str, float]:
        """Get current price from CoinGecko."""
        coin_id = self.normalize_symbol(symbol)
        try:
            url = f"{self.base_url}/simple/price"
            params = {
                'ids': coin_id,
                'vs_currencies': 'usd'
            }
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            price = float(data.get(coin_id, {}).get('usd', 0))
            return {
                'bid': price * 0.999,
                'ask': price * 1.001
            }
        except Exception:
            pass
        return {'bid': 0.0, 'ask': 0.0}


# ============================================================================
# Trading Providers
# ============================================================================

class RobinhoodTrading(TradingProvider):
    """Robinhood trading provider (existing implementation)."""
    
    def __init__(self, api_key: str, base64_private_key: str):
        self.api_key = api_key.strip()
        self.base_url = "https://trading.robinhood.com"
        
        # Decode private key
        private_key_seed = base64.b64decode(base64_private_key.strip())
        self.private_key = SigningKey(private_key_seed)
    
    def normalize_symbol(self, symbol: str) -> str:
        """Convert symbol to Robinhood format (BTC-USD)."""
        symbol = symbol.upper().strip()
        if '-' not in symbol:
            return f"{symbol}-USD"
        return symbol
    
    def _get_current_timestamp(self) -> int:
        return int(time.time())
    
    def _get_authorization_header(self, method: str, path: str, body: str, timestamp: int) -> dict:
        message_to_sign = f"{self.api_key}{timestamp}{path}{method.upper()}{body or ''}"
        signed = self.private_key.sign(message_to_sign.encode("utf-8"))
        signature_b64 = base64.b64encode(signed.signature).decode("utf-8")
        
        return {
            "x-api-key": self.api_key,
            "x-timestamp": str(timestamp),
            "x-signature": signature_b64,
            "Content-Type": "application/json",
        }
    
    def make_api_request(self, method: str, path: str, body: str = "") -> dict:
        url = f"{self.base_url}{path}"
        ts = self._get_current_timestamp()
        headers = self._get_authorization_header(method, path, body, ts)
        
        resp = requests.request(
            method=method.upper(),
            url=url,
            headers=headers,
            data=body or None,
            timeout=10
        )
        
        if resp.status_code >= 400:
            raise RuntimeError(f"Robinhood HTTP {resp.status_code}: {resp.text}")
        return resp.json()
    
    def place_buy_order(self, symbol: str, amount_usd: float, **kwargs) -> Dict[str, Any]:
        """Place a market buy order on Robinhood."""
        symbol = self.normalize_symbol(symbol)
        path = "/api/v1/crypto/trading/orders/"
        
        order_config = {
            "client_order_id": kwargs.get('client_order_id', str(int(time.time() * 1000))),
            "side": "buy",
            "type": "market",
            "symbol": symbol,
            "market_order_config": {
                "asset_quantity": str(amount_usd)
            }
        }
        
        response = self.make_api_request("POST", path, json.dumps(order_config))
        return response
    
    def place_sell_order(self, symbol: str, quantity: float, **kwargs) -> Dict[str, Any]:
        """Place a market sell order on Robinhood."""
        symbol = self.normalize_symbol(symbol)
        path = "/api/v1/crypto/trading/orders/"
        
        order_config = {
            "client_order_id": kwargs.get('client_order_id', str(int(time.time() * 1000))),
            "side": "sell",
            "type": "market",
            "symbol": symbol,
            "market_order_config": {
                "asset_quantity": str(quantity)
            }
        }
        
        response = self.make_api_request("POST", path, json.dumps(order_config))
        return response
    
    def get_account_info(self) -> Dict[str, Any]:
        """Get Robinhood account information."""
        path = "/api/v1/crypto/trading/accounts/"
        return self.make_api_request("GET", path)
    
    def get_orders(self, symbol: str) -> List[Dict[str, Any]]:
        """Get order history for a symbol."""
        symbol = self.normalize_symbol(symbol)
        path = f"/api/v1/crypto/trading/orders/?symbol={symbol}"
        response = self.make_api_request("GET", path)
        return response.get("results", [])


class BinanceTrading(TradingProvider):
    """Binance trading provider (spot trading)."""
    
    def __init__(self, api_key: str, api_secret: str, use_us: bool = False):
        self.api_key = api_key.strip()
        self.api_secret = api_secret.strip()
        self.base_url = "https://api.binance.us" if use_us else "https://api.binance.com"
    
    def normalize_symbol(self, symbol: str) -> str:
        """Convert symbol to Binance format (BTCUSDT)."""
        symbol = symbol.upper().strip().replace('-', '').replace('_', '')
        if not symbol.endswith('USDT'):
            symbol = f"{symbol}USDT"
        return symbol
    
    def _get_timestamp(self) -> int:
        return int(time.time() * 1000)
    
    def _sign_request(self, params: dict) -> str:
        """Create signature for Binance API request."""
        query_string = '&'.join([f"{k}={v}" for k, v in sorted(params.items())])
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature
    
    def _make_request(self, method: str, endpoint: str, params: dict = None, signed: bool = True) -> dict:
        """Make authenticated request to Binance API."""
        params = params or {}
        headers = {'X-MBX-APIKEY': self.api_key}
        
        if signed:
            params['timestamp'] = self._get_timestamp()
            params['signature'] = self._sign_request(params)
        
        url = f"{self.base_url}{endpoint}"
        
        if method.upper() == 'GET':
            resp = requests.get(url, params=params, headers=headers, timeout=10)
        elif method.upper() == 'POST':
            resp = requests.post(url, params=params, headers=headers, timeout=10)
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        resp.raise_for_status()
        return resp.json()
    
    def place_buy_order(self, symbol: str, amount_usd: float, **kwargs) -> Dict[str, Any]:
        """Place a market buy order on Binance."""
        symbol = self.normalize_symbol(symbol)
        
        # Binance requires quantity, so we use quoteOrderQty for USDT amount
        params = {
            'symbol': symbol,
            'side': 'BUY',
            'type': 'MARKET',
            'quoteOrderQty': f"{amount_usd:.2f}"
        }
        
        return self._make_request('POST', '/api/v3/order', params)
    
    def place_sell_order(self, symbol: str, quantity: float, **kwargs) -> Dict[str, Any]:
        """Place a market sell order on Binance."""
        symbol = self.normalize_symbol(symbol)
        
        params = {
            'symbol': symbol,
            'side': 'SELL',
            'type': 'MARKET',
            'quantity': f"{quantity:.8f}"
        }
        
        return self._make_request('POST', '/api/v3/order', params)
    
    def get_account_info(self) -> Dict[str, Any]:
        """Get Binance account information."""
        return self._make_request('GET', '/api/v3/account')
    
    def get_orders(self, symbol: str) -> List[Dict[str, Any]]:
        """Get order history for a symbol."""
        symbol = self.normalize_symbol(symbol)
        params = {'symbol': symbol}
        return self._make_request('GET', '/api/v3/allOrders', params)


class CoinbaseTrading(TradingProvider):
    """Coinbase Advanced Trade API trading provider."""
    
    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key.strip()
        self.api_secret = api_secret.strip()
        self.base_url = "https://api.coinbase.com"
    
    def normalize_symbol(self, symbol: str) -> str:
        """Convert symbol to Coinbase format (BTC-USD)."""
        symbol = symbol.upper().strip()
        if '-' not in symbol:
            return f"{symbol}-USD"
        return symbol
    
    def _get_timestamp(self) -> str:
        return str(int(time.time()))
    
    def _sign_request(self, timestamp: str, method: str, path: str, body: str = "") -> str:
        """Create signature for Coinbase API request."""
        message = f"{timestamp}{method.upper()}{path}{body}"
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature
    
    def _make_request(self, method: str, path: str, body: dict = None) -> dict:
        """Make authenticated request to Coinbase API."""
        timestamp = self._get_timestamp()
        body_str = json.dumps(body) if body else ""
        
        headers = {
            'CB-ACCESS-KEY': self.api_key,
            'CB-ACCESS-SIGN': self._sign_request(timestamp, method, path, body_str),
            'CB-ACCESS-TIMESTAMP': timestamp,
            'Content-Type': 'application/json'
        }
        
        url = f"{self.base_url}{path}"
        
        if method.upper() == 'GET':
            resp = requests.get(url, headers=headers, timeout=10)
        elif method.upper() == 'POST':
            resp = requests.post(url, json=body, headers=headers, timeout=10)
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        resp.raise_for_status()
        return resp.json()
    
    def place_buy_order(self, symbol: str, amount_usd: float, **kwargs) -> Dict[str, Any]:
        """Place a market buy order on Coinbase."""
        symbol = self.normalize_symbol(symbol)
        
        order = {
            'product_id': symbol,
            'side': 'BUY',
            'order_configuration': {
                'market_market_ioc': {
                    'quote_size': str(amount_usd)
                }
            }
        }
        
        return self._make_request('POST', '/api/v3/brokerage/orders', order)
    
    def place_sell_order(self, symbol: str, quantity: float, **kwargs) -> Dict[str, Any]:
        """Place a market sell order on Coinbase."""
        symbol = self.normalize_symbol(symbol)
        
        order = {
            'product_id': symbol,
            'side': 'SELL',
            'order_configuration': {
                'market_market_ioc': {
                    'base_size': str(quantity)
                }
            }
        }
        
        return self._make_request('POST', '/api/v3/brokerage/orders', order)
    
    def get_account_info(self) -> Dict[str, Any]:
        """Get Coinbase account information."""
        return self._make_request('GET', '/api/v3/brokerage/accounts')
    
    def get_orders(self, symbol: str) -> List[Dict[str, Any]]:
        """Get order history for a symbol."""
        symbol = self.normalize_symbol(symbol)
        response = self._make_request('GET', f'/api/v3/brokerage/orders/historical/batch?product_id={symbol}')
        return response.get('orders', [])


# ============================================================================
# Provider Factory Functions
# ============================================================================

def create_market_data_provider(provider_name: str, **kwargs) -> MarketDataProvider:
    """
    Factory function to create a market data provider.
    
    Args:
        provider_name: Name of the provider ('kucoin', 'binance', 'coinbase', 'coingecko')
        **kwargs: Provider-specific configuration
        
    Returns:
        MarketDataProvider instance
    """
    provider_name = provider_name.lower().strip()
    
    if provider_name == 'kucoin':
        return KuCoinMarketData()
    elif provider_name == 'binance':
        return BinanceMarketData(use_us=kwargs.get('use_us', False))
    elif provider_name == 'binance_us':
        return BinanceMarketData(use_us=True)
    elif provider_name == 'coinbase':
        return CoinbaseMarketData()
    elif provider_name == 'coingecko':
        return CoinGeckoMarketData()
    else:
        raise ValueError(f"Unknown market data provider: {provider_name}")


def create_trading_provider(provider_name: str, **kwargs) -> TradingProvider:
    """
    Factory function to create a trading provider.
    
    Args:
        provider_name: Name of the provider ('robinhood', 'binance', 'coinbase')
        **kwargs: Provider-specific credentials and configuration
        
    Returns:
        TradingProvider instance
    """
    provider_name = provider_name.lower().strip()
    
    if provider_name == 'robinhood':
        return RobinhoodTrading(
            api_key=kwargs['api_key'],
            base64_private_key=kwargs['private_key']
        )
    elif provider_name == 'binance':
        return BinanceTrading(
            api_key=kwargs['api_key'],
            api_secret=kwargs['api_secret'],
            use_us=kwargs.get('use_us', False)
        )
    elif provider_name == 'binance_us':
        return BinanceTrading(
            api_key=kwargs['api_key'],
            api_secret=kwargs['api_secret'],
            use_us=True
        )
    elif provider_name == 'coinbase':
        return CoinbaseTrading(
            api_key=kwargs['api_key'],
            api_secret=kwargs['api_secret']
        )
    else:
        raise ValueError(f"Unknown trading provider: {provider_name}")
