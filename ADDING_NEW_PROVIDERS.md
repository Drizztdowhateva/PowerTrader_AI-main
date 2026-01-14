# How to Add a New Exchange API Provider

This guide explains how to add support for a new cryptocurrency exchange to PowerTrader AI.

## Overview

PowerTrader AI uses an abstraction layer in `api_providers.py` that separates:
1. **Market Data Providers** - Fetch historical candles and current prices
2. **Trading Providers** - Execute orders and manage account info

## Adding a New Market Data Provider

### Step 1: Create Your Provider Class

Edit `api_providers.py` and add a new class that inherits from `MarketDataProvider`:

```python
class YourExchangeMarketData(MarketDataProvider):
    """Your exchange market data provider."""
    
    def __init__(self, **kwargs):
        self.base_url = "https://api.yourexchange.com"
        # Add any initialization needed
    
    def normalize_symbol(self, symbol: str) -> str:
        """Convert symbol to your exchange's format."""
        # Example: BTC-USDT -> BTCUSDT or BTC_USDT
        symbol = symbol.upper().strip()
        # Your conversion logic here
        return symbol
    
    def _map_timeframe(self, tf: str) -> str:
        """Map standard timeframe to exchange format."""
        # Map from PowerTrader format to your exchange's format
        tf_map = {
            '1min': '1m',
            '5min': '5m',
            '15min': '15m',
            '30min': '30m',
            '1hour': '1h',
            '4hour': '4h',
            '1day': '1d',
            '1week': '1w'
        }
        return tf_map.get(tf, '1h')
    
    def get_klines(self, symbol: str, timeframe: str, limit: int = 1500) -> List[List]:
        """Get candlestick data from your exchange."""
        symbol = self.normalize_symbol(symbol)
        interval = self._map_timeframe(timeframe)
        
        try:
            url = f"{self.base_url}/api/v1/candles"  # Your endpoint
            params = {
                'symbol': symbol,
                'interval': interval,
                'limit': min(limit, 1000)  # Respect exchange limits
            }
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            
            # Convert to standard format:
            # [timestamp, open, close, high, low, volume]
            result = []
            for candle in data:
                result.append([
                    str(candle['timestamp']),
                    str(candle['open']),
                    str(candle['close']),
                    str(candle['high']),
                    str(candle['low']),
                    str(candle['volume'])
                ])
            return result
        except Exception:
            return []
    
    def get_current_price(self, symbol: str) -> Dict[str, float]:
        """Get current bid/ask prices."""
        symbol = self.normalize_symbol(symbol)
        try:
            url = f"{self.base_url}/api/v1/ticker"  # Your endpoint
            params = {'symbol': symbol}
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            
            return {
                'bid': float(data['bidPrice']),
                'ask': float(data['askPrice'])
            }
        except Exception:
            pass
        return {'bid': 0.0, 'ask': 0.0}
```

### Step 2: Add to Factory Function

In `api_providers.py`, update the `create_market_data_provider` function:

```python
def create_market_data_provider(provider_name: str, **kwargs) -> MarketDataProvider:
    provider_name = provider_name.lower().strip()
    
    if provider_name == 'kucoin':
        return KuCoinMarketData()
    elif provider_name == 'binance':
        return BinanceMarketData(use_us=kwargs.get('use_us', False))
    elif provider_name == 'yourexchange':  # Add your exchange here
        return YourExchangeMarketData(**kwargs)
    # ... existing code ...
```

### Step 3: Test Your Provider

Create a test script or add to `test_api_providers.py`:

```python
from api_providers import create_market_data_provider

# Test your provider
provider = create_market_data_provider('yourexchange')

# Test symbol conversion
symbol = provider.normalize_symbol('BTC-USDT')
print(f"Normalized symbol: {symbol}")

# Test price fetching
price = provider.get_current_price('BTC-USDT')
print(f"Current price: {price}")

# Test klines
klines = provider.get_klines('BTC-USDT', '1hour', limit=10)
print(f"Fetched {len(klines)} candles")
```

## Adding a New Trading Provider

### Step 1: Create Your Provider Class

```python
class YourExchangeTrading(TradingProvider):
    """Your exchange trading provider."""
    
    def __init__(self, api_key: str, api_secret: str, **kwargs):
        self.api_key = api_key.strip()
        self.api_secret = api_secret.strip()
        self.base_url = "https://api.yourexchange.com"
    
    def normalize_symbol(self, symbol: str) -> str:
        """Convert to exchange format."""
        symbol = symbol.upper().strip().replace('-', '')
        if not symbol.endswith('USDT'):
            symbol = f"{symbol}USDT"
        return symbol
    
    def _sign_request(self, params: dict) -> str:
        """Create signature for authenticated requests."""
        # Implement your exchange's signature method
        import hmac
        import hashlib
        
        query_string = '&'.join([f"{k}={v}" for k, v in sorted(params.items())])
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature
    
    def _make_request(self, method: str, endpoint: str, params: dict = None) -> dict:
        """Make authenticated request."""
        params = params or {}
        headers = {'X-API-KEY': self.api_key}
        
        # Add timestamp
        params['timestamp'] = int(time.time() * 1000)
        
        # Sign the request
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
        """Place a market buy order."""
        symbol = self.normalize_symbol(symbol)
        
        params = {
            'symbol': symbol,
            'side': 'BUY',
            'type': 'MARKET',
            'quoteOrderQty': f"{amount_usd:.2f}"
        }
        
        return self._make_request('POST', '/api/v1/order', params)
    
    def place_sell_order(self, symbol: str, quantity: float, **kwargs) -> Dict[str, Any]:
        """Place a market sell order."""
        symbol = self.normalize_symbol(symbol)
        
        params = {
            'symbol': symbol,
            'side': 'SELL',
            'type': 'MARKET',
            'quantity': f"{quantity:.8f}"
        }
        
        return self._make_request('POST', '/api/v1/order', params)
    
    def get_account_info(self) -> Dict[str, Any]:
        """Get account information."""
        return self._make_request('GET', '/api/v1/account')
    
    def get_orders(self, symbol: str) -> List[Dict[str, Any]]:
        """Get order history."""
        symbol = self.normalize_symbol(symbol)
        params = {'symbol': symbol}
        response = self._make_request('GET', '/api/v1/orders', params)
        return response.get('orders', [])
```

### Step 2: Add to Factory Function

Update `create_trading_provider`:

```python
def create_trading_provider(provider_name: str, **kwargs) -> TradingProvider:
    provider_name = provider_name.lower().strip()
    
    if provider_name == 'robinhood':
        return RobinhoodTrading(
            api_key=kwargs['api_key'],
            base64_private_key=kwargs['private_key']
        )
    elif provider_name == 'yourexchange':  # Add here
        return YourExchangeTrading(
            api_key=kwargs['api_key'],
            api_secret=kwargs['api_secret']
        )
    # ... existing code ...
```

### Step 3: Add Environment Variable Support

In `pt_trader.py`, add support for your exchange credentials:

```python
def _get_trading_provider_from_settings() -> Optional['TradingProvider']:
    # ... existing code ...
    
    elif provider_name == 'yourexchange':
        api_key = os.environ.get("YOUREXCHANGE_API_KEY", "").strip()
        api_secret = os.environ.get("YOUREXCHANGE_API_SECRET", "").strip()
        if not api_key or not api_secret:
            print("[TRADER] Warning: yourexchange selected but credentials not found")
            # Fallback logic
        
        return create_trading_provider(
            "yourexchange",
            api_key=api_key,
            api_secret=api_secret
        )
```

## Important Notes

### Data Format Standardization

PowerTrader AI expects klines in this format (matching KuCoin's native format):
```python
[
    timestamp (str),   # Unix timestamp in seconds
    open (str),        # Opening price
    close (str),       # Closing price (NOTE: close before high/low)
    high (str),        # Highest price
    low (str),         # Lowest price
    volume (str)       # Trading volume
]
```

**Important**: The order is [timestamp, open, close, high, low, volume], which matches KuCoin's format.
Make sure your provider converts the exchange's format to this standard.

### Symbol Format

Different exchanges use different symbol formats:
- **KuCoin**: `BTC-USDT`
- **Binance**: `BTCUSDT`
- **Coinbase**: `BTC-USD`

Your `normalize_symbol()` method should convert between formats.

### Error Handling

Always wrap API calls in try/except blocks and return safe defaults:
- `get_klines()` → return `[]` on error
- `get_current_price()` → return `{'bid': 0.0, 'ask': 0.0}` on error
- Trading methods → raise exceptions (caller will handle)

### Rate Limits

Be aware of your exchange's rate limits and implement appropriate delays or caching if needed.

### Testing

Before using a new provider with real money:
1. Test with paper trading / testnet if available
2. Verify symbol normalization works for all your coins
3. Test with small amounts first
4. Monitor for API changes from the exchange

## Documentation

After adding a provider, update:
1. `API_PROVIDERS_GUIDE.md` - Add setup instructions
2. `README.md` - Add to supported providers list
3. `gui_settings.example.json` - Add example config
4. Create a pull request with your addition!

## Getting Help

If you need help adding a provider:
1. Check the existing provider implementations as examples
2. Read the exchange's API documentation
3. Open an issue on GitHub with questions
4. Join the community discussions

## Common Issues

### "Module not found" errors
Some exchanges have official Python clients. Add them to `requirements.txt` as optional dependencies:
```
# Optional: YourExchange client
# yourexchange-python
```

### Authentication failures
- Verify API key permissions on the exchange
- Check signature generation matches exchange docs
- Ensure timestamp format is correct
- Test with exchange's official examples first

### Symbol not found errors
- Check your `normalize_symbol()` logic
- Verify the coin is available on the exchange
- Look at the exchange's symbol list endpoint

## Example: Full Implementation

See `api_providers.py` for complete examples:
- **KuCoinMarketData** - Simple REST API
- **BinanceMarketData** - With symbol conversion
- **RobinhoodTrading** - With custom signing
- **BinanceTrading** - With HMAC-SHA256 signing

Each implementation includes error handling, symbol normalization, and proper data format conversion.
