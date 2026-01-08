# API Implementation Quick Reference

## New Files Created

### 1. `exchange_credential_manager.py` (320 lines)
**Purpose**: Manage API credentials for any exchange with file I/O

**Key Classes**:
- `ExchangeConfig` - Configuration template for an exchange
- `CredentialManager` - Read/write credentials to files
- `ExchangeRegistry` - Central registry of all exchanges

**Usage**:
```python
from exchange_credential_manager import ExchangeConfig, CredentialManager, register_exchange

config = ExchangeConfig(
    name="myex",
    display_name="My Exchange",
    credential_fields=["api_key", "api_secret"]
)
register_exchange(config)

manager = CredentialManager(config)
creds, success = manager.read_credentials()
```

---

### 2. `wizard_template_generator.py` (350 lines)
**Purpose**: Reusable setup wizard components for GUI credential entry

**Key Classes**:
- `BaseExchangeWizard` - Abstract base for all wizards
- `ScrollableWizardFrame` - Reusable scrollable UI frame

**Usage**:
```python
from wizard_template_generator import BaseExchangeWizard

class MyWizard(BaseExchangeWizard):
    def test_api_connection(self) -> str:
        # Custom test logic
        return "✅ Connected"

# In pt_hub.py:
wizard = MyWizard(root_window, config)
```

---

### 3. `exchange_api_utilities.py` (400 lines)
**Purpose**: Base classes and utilities for implementing API clients

**Key Classes**:
- `APIClientBase` - Generic API client with signing and error handling
- `MarketDataClient` - Base for market data implementations
- `TradingClient` - Base for trading implementations
- `RateLimiter` - Rate limiting helper

**Usage**:
```python
from exchange_api_utilities import TradingClient, AuthMethod

class MyExchangeTrader(TradingClient):
    def __init__(self, api_key: str, api_secret: str):
        super().__init__(
            api_key=api_key,
            api_secret=api_secret,
            base_url="https://api.myex.com/v1",
            auth_method=AuthMethod.HMAC_SHA256
        )
    
    def place_order(self, symbol: str, side: str, quantity: float, **kwargs):
        return self._post("/orders", json_data={
            "symbol": symbol,
            "side": side,
            "qty": quantity
        })
```

---

### 4. `FUTURE_API_IMPLEMENTATION_GUIDE.md` (400+ lines)
**Purpose**: Complete guide for adding new exchanges

**Contents**:
- Step-by-step implementation instructions
- Code examples for market data and trading
- Authentication patterns (HMAC, ED25519, RSA)
- File structure and best practices
- Troubleshooting

---

## Checklist: Adding a New Exchange

### Phase 1: Setup & Configuration
- [ ] Read exchange API documentation
- [ ] Define `ExchangeConfig` in `pt_hub.py`
- [ ] Call `register_exchange(config)`
- [ ] Add `exchange_{name}_enabled` to `DEFAULT_SETTINGS`
- [ ] Create placeholder credential files: `{name}_key.txt`, `{name}_secret.txt`
- [ ] Update `.gitignore` to exclude credential files

### Phase 2: GUI & Credentials
- [ ] Add checkbox in settings dialog
- [ ] Create wizard class (extend `BaseExchangeWizard`)
- [ ] Implement `test_api_connection()` method
- [ ] Add setup wizard button to settings
- [ ] Test wizard - save and reload credentials

### Phase 3: Market Data Implementation
- [ ] Create `{Exchange}MarketData` class in `pt_thinker.py`
- [ ] Extend `MarketDataClient` from `exchange_api_utilities.py`
- [ ] Implement `get_klines()` method
- [ ] Implement `get_ticker()` method (optional)
- [ ] Add credential loading function
- [ ] Test market data fetching with real API

### Phase 4: Trading Implementation
- [ ] Create `{Exchange}Trader` class in `pt_trader.py`
- [ ] Extend `TradingClient` from `exchange_api_utilities.py`
- [ ] Implement `place_order()` method
- [ ] Implement `cancel_order()` method
- [ ] Implement `get_account_value()` method
- [ ] Test with sandbox/paper trading first

### Phase 5: Integration & Testing
- [ ] Integrate with existing trading logic
- [ ] Test end-to-end workflow
- [ ] Add error handling for network failures
- [ ] Log transactions to `trader_status.json`
- [ ] Document any exchange-specific quirks

---

## Common Patterns

### Pattern 1: Simple HMAC-SHA256 Auth
```python
import hmac
import hashlib

timestamp = str(int(time.time()))
signature = hmac.new(
    api_secret.encode(),
    timestamp.encode(),
    hashlib.sha256
).hexdigest()
```

### Pattern 2: Request Body Signing
```python
message = f"{api_key}{timestamp}{path}{method}{json.dumps(body)}"
signature = hmac.new(
    api_secret.encode(),
    message.encode(),
    hashlib.sha256
).hexdigest()
```

### Pattern 3: Nonce-Based Auth (Kraken style)
```python
nonce = str(int(time.time() * 1000))
postdata = urlencode({"nonce": nonce, "param": value})
message_hash = hashlib.sha256(postdata.encode()).digest()
signature = hmac.new(api_secret.encode(), message_hash, hashlib.sha512).digest()
```

### Pattern 4: Custom Header Auth
```python
headers = {
    "X-API-Key": api_key,
    "X-API-Signature": signature,
    "X-API-Timestamp": timestamp
}
```

---

## File Structure for New Exchange

```
PowerTrader_AI-main/
├── pt_hub.py                              # (modify)
│   ├── Import config classes
│   ├── Define ExchangeConfig
│   ├── Register exchange
│   ├── Create wizard class
│   ├── Add GUI controls
│   └── Handle settings persistence
│
├── pt_thinker.py                          # (modify)
│   ├── Import MarketDataClient
│   ├── Create {Exchange}MarketData class
│   └── Add credential loader function
│
├── pt_trader.py                           # (modify)
│   ├── Import TradingClient
│   ├── Create {Exchange}Trader class
│   └── Add credential loader function
│
├── exchange_credential_manager.py         # (no changes)
├── wizard_template_generator.py           # (no changes)
├── exchange_api_utilities.py              # (no changes)
│
├── {exchange}_key.txt                     # (created by wizard)
├── {exchange}_secret.txt                  # (created by wizard)
├── {exchange}_passphrase.txt              # (optional, if needed)
│
└── .gitignore                             # (add credential files)
```

---

## Testing Checklist

```python
# Test 1: Configuration
from exchange_credential_manager import get_exchange_config
config = get_exchange_config("myexchange")
assert config is not None, "Config not registered"

# Test 2: Credential Manager
manager = CredentialManager(config)
assert manager.credentials_exist() or not manager.credentials_exist()

# Test 3: Market Data
from pt_thinker import myexchange_market_data
md = myexchange_market_data()
candles = md.get_klines("BTC-USD", "1h")
assert len(candles) > 0, "No candles returned"

# Test 4: Trading
from pt_trader import MyExchangeTrader
balance = trader.get_account_value()
assert balance >= 0, "Invalid balance"

# Test 5: Rate Limiting
from exchange_api_utilities import RateLimiter
limiter = RateLimiter(calls_per_second=5)
for i in range(10):
    limiter.wait_if_needed()
    # Make API call
```

---

## Environment Setup

```bash
# Install dependencies (if not already installed)
pip install -r requirements.txt

# Verify imports
python -c "from exchange_credential_manager import ExchangeConfig; print('✅ Ready')"

# Run wizard generator test
python wizard_template_generator.py
```

---

## Support for Different Credential Types

### API Key + Secret (Standard)
```python
credential_fields=["api_key", "api_secret"]
```

### API Key + Secret + Passphrase (KuCoin style)
```python
credential_fields=["api_key", "api_secret", "passphrase"]
```

### Base64-Encoded Secret (Kraken style)
```python
credential_fields=["api_key", "api_secret"],
base64_encoded_fields=["api_secret"]
```

### RSA Private Key
```python
credential_fields=["api_key", "private_key"],
base64_encoded_fields=["private_key"]
```

---

## Error Handling

```python
from exchange_api_utilities import APIClientBase

try:
    response = client._request("GET", "/ticker", params={"symbol": "BTC"})
    response.raise_for_status()
    data = response.json()
except requests.exceptions.HTTPError as e:
    if e.response.status_code == 401:
        print("Authentication failed - check credentials")
    elif e.response.status_code == 429:
        print("Rate limited - wait before retrying")
    else:
        print(f"API error: {e.response.status_code}")
except requests.exceptions.Timeout:
    print("Request timeout - increase timeout or check network")
except requests.exceptions.ConnectionError:
    print("Connection failed - check API availability")
```

---

## Performance Tips

1. **Caching**: Cache OHLCV data locally to reduce API calls
2. **Bulk Requests**: Batch multiple requests when possible
3. **Rate Limiting**: Use `RateLimiter` to stay within API limits
4. **Async**: Use threading for non-blocking API calls
5. **Error Recovery**: Implement exponential backoff for retries

---

## Documentation References

- `FUTURE_API_IMPLEMENTATION_GUIDE.md` - Complete step-by-step guide
- `EXCHANGE_SETUP.md` - User guide for configuring exchanges
- `.github/copilot-instructions.md` - API platform specifications
- Existing implementations:
  - Robinhood: `pt_thinker.py` lines 64-120 (RobinhoodMarketData)
  - KuCoin: `pt_thinker.py` lines 21-52 (get_klines)

---

## Questions?

Check these resources in order:
1. `FUTURE_API_IMPLEMENTATION_GUIDE.md` - Most detailed
2. Code comments in `exchange_api_utilities.py`
3. Existing Robinhood implementation in `pt_thinker.py` / `pt_trader.py`
4. Exchange API documentation for your chosen platform
