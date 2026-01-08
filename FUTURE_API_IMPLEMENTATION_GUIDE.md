# Future API Implementation Guide

This guide explains how to use the generalized credential management and wizard template system to add new exchange APIs to PowerTrader.

## Quick Start: Adding a New Exchange

### Step 1: Define the Exchange Configuration

In `pt_hub.py`, define an `ExchangeConfig` at the top of the file (after imports):

```python
from exchange_credential_manager import ExchangeConfig, register_exchange

# Define your exchange
my_exchange_config = ExchangeConfig(
    name="myexchange",                    # Lowercase identifier
    display_name="My Exchange",           # User-friendly name
    credential_fields=["api_key", "api_secret"],  # Required credentials
    api_endpoints={
        "market_data": "https://api.myexchange.com/v1/market/candles",
        "trading": "https://api.myexchange.com/v1/orders"
    },
    auth_method="hmac-sha256",           # How authentication works
    setup_instructions={
        "api_key": "Get from https://myexchange.com/api/settings",
        "api_secret": "Shown only once - keep it safe!"
    },
    supports_market_data=True,
    supports_trading=True,
    supports_futures=False
)

# Register it
register_exchange(my_exchange_config)
```

### Step 2: Create the Setup Wizard

Use the `BaseExchangeWizard` class for a basic wizard, or subclass it for custom behavior:

```python
from wizard_template_generator import BaseExchangeWizard

class MyExchangeWizard(BaseExchangeWizard):
    """Custom wizard for My Exchange with connection test"""
    
    def test_api_connection(self) -> str:
        """Override to test actual API connectivity"""
        try:
            creds, success = self.manager.read_credentials()
            if not success:
                return "❌ Credentials not set"
            
            api_key = creds.get("api_key", "")
            
            # Test public endpoint (no auth needed)
            import requests
            response = requests.get(
                "https://api.myexchange.com/v1/ping",
                timeout=5
            )
            
            if response.status_code == 200:
                return "✅ Connection successful"
            else:
                return f"❌ API returned {response.status_code}"
        
        except Exception as e:
            return f"❌ Connection failed: {str(e)}"

# In your settings dialog, add the wizard:
def _open_myexchange_api_wizard():
    MyExchangeWizard(win, my_exchange_config)

# Add button to settings dialog:
myex_btn = tk.Button(
    button_frame,
    text="My Exchange API Setup",
    command=_open_myexchange_api_wizard,
    bg=DARK_ACCENT,
    fg="#000000"
)
myex_btn.pack(pady=5, fill="x")
```

### Step 3: Add Settings Toggle

In `DEFAULT_SETTINGS`, add your exchange enable flag:

```python
DEFAULT_SETTINGS = {
    # ... existing settings ...
    "exchange_myexchange_enabled": False,  # Add this
}
```

In the settings dialog UI section:

```python
# Add checkbox for your exchange
myex_var = tk.BooleanVar(
    value=settings.get("exchange_myexchange_enabled", False)
)
myex_checkbox = tk.Checkbox(
    settings_frame,
    text="My Exchange Trading",
    variable=myex_var
)
myex_checkbox.pack(anchor="w", pady=2)

# When saving settings, add:
settings["exchange_myexchange_enabled"] = myex_var.get()
```

### Step 4: Implement Market Data and Trading Classes

In `pt_thinker.py` and `pt_trader.py`, implement classes following the existing `RobinhoodMarketData` and `CryptoAPITrading` patterns:

**pt_thinker.py** (Market Data):
```python
class MyExchangeMarketData:
    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = "https://api.myexchange.com/v1"
    
    def get_klines(self, symbol: str, interval: str) -> List[Tuple]:
        """Fetch OHLCV candles
        
        Args:
            symbol: e.g., "BTC-USD"
            interval: e.g., "1h", "1d"
        
        Returns:
            List of (timestamp, open, high, low, close, volume)
        """
        import requests
        import hmac
        import hashlib
        import time
        
        params = {
            "symbol": symbol,
            "interval": interval,
            "limit": 1000
        }
        
        # Add authentication if needed
        timestamp = str(int(time.time()))
        signature = hmac.new(
            self.api_secret.encode(),
            timestamp.encode(),
            hashlib.sha256
        ).hexdigest()
        
        headers = {
            "API-Key": self.api_key,
            "API-Signature": signature,
            "API-Timestamp": timestamp
        }
        
        response = requests.get(
            f"{self.base_url}/klines",
            params=params,
            headers=headers
        )
        
        if response.status_code == 200:
            data = response.json()
            # Parse and return OHLCV data
            return data.get("klines", [])
        
        return []
    
    def get_current_price(self, symbol: str) -> float:
        """Get current market price"""
        import requests
        
        response = requests.get(
            f"{self.base_url}/ticker",
            params={"symbol": symbol}
        )
        
        if response.status_code == 200:
            data = response.json()
            return float(data.get("last", 0))
        
        return 0.0

def myexchange_market_data() -> MyExchangeMarketData:
    """Get market data client for My Exchange"""
    from exchange_credential_manager import get_exchange_config, CredentialManager
    
    config = get_exchange_config("myexchange")
    if not config:
        raise ValueError("My Exchange not configured")
    
    manager = CredentialManager(config)
    creds, success = manager.read_credentials()
    
    if not success:
        raise ValueError("My Exchange credentials not set")
    
    return MyExchangeMarketData(
        api_key=creds.get("api_key", ""),
        api_secret=creds.get("api_secret", "")
    )
```

**pt_trader.py** (Trading):
```python
class MyExchangeTrading:
    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = "https://api.myexchange.com/v1"
    
    def place_order(self, symbol: str, side: str, quantity: float, price: float = None) -> Dict:
        """Place a buy/sell order
        
        Args:
            symbol: e.g., "BTC-USD"
            side: "buy" or "sell"
            quantity: Amount to buy/sell
            price: Optional limit price (market if not provided)
        
        Returns:
            Order details dict
        """
        import requests
        import hmac
        import hashlib
        import time
        import json
        
        order_data = {
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "order_type": "limit" if price else "market"
        }
        
        if price:
            order_data["price"] = price
        
        timestamp = str(int(time.time()))
        body = json.dumps(order_data)
        
        signature = hmac.new(
            self.api_secret.encode(),
            body.encode(),
            hashlib.sha256
        ).hexdigest()
        
        headers = {
            "API-Key": self.api_key,
            "API-Signature": signature,
            "API-Timestamp": timestamp,
            "Content-Type": "application/json"
        }
        
        response = requests.post(
            f"{self.base_url}/orders",
            json=order_data,
            headers=headers
        )
        
        if response.status_code in (200, 201):
            return response.json()
        
        raise Exception(f"Order failed: {response.text}")
    
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an existing order"""
        import requests
        
        response = requests.delete(
            f"{self.base_url}/orders/{order_id}",
            headers={"API-Key": self.api_key}
        )
        
        return response.status_code == 200
    
    def get_account_value(self) -> float:
        """Get total account balance in USD"""
        import requests
        
        response = requests.get(
            f"{self.base_url}/account",
            headers={"API-Key": self.api_key}
        )
        
        if response.status_code == 200:
            data = response.json()
            return float(data.get("total_value", 0))
        
        return 0.0
```

## File Structure

When adding a new exchange, you'll create/modify:

```
PowerTrader_AI-main/
├── pt_hub.py                              # Add config, wizard, UI
├── pt_thinker.py                          # Add market data class
├── pt_trader.py                           # Add trading class
├── exchange_credential_manager.py         # (Already exists - no changes)
├── wizard_template_generator.py           # (Already exists - no changes)
├── myexchange_key.txt                     # (Created by wizard)
├── myexchange_secret.txt                  # (Created by wizard)
└── .gitignore                             # (Update with credentials)
```

## Advanced: Custom Wizard with Extra Features

If you need a custom wizard with additional fields or validation:

```python
from wizard_template_generator import BaseExchangeWizard

class AdvancedExchangeWizard(BaseExchangeWizard):
    """Advanced wizard with custom UI and validation"""
    
    def _build_ui(self):
        # Call parent build
        super()._build_ui()
        
        # Add custom elements
        content_frame = self.scroll_frame.get_content_frame()
        
        info_label = tk.Label(
            content_frame,
            text="⚠️ Additional Setup Required",
            bg=self.dark_bg,
            fg="#FFD700",
            font=("Helvetica", 11, "bold")
        )
        info_label.pack(pady=10)
    
    def test_api_connection(self) -> str:
        """Custom connection test"""
        creds, success = self.manager.read_credentials()
        
        if not success:
            return "❌ All credentials required"
        
        # Your custom test logic here
        return "✅ All checks passed"
```

## Configuration Reference

### ExchangeConfig Fields

```python
ExchangeConfig(
    name: str                           # "binance", "kraken", etc.
    display_name: str                   # "Binance", "Kraken", etc.
    credential_fields: List[str]        # ["api_key", "api_secret", "passphrase"]
    
    api_endpoints: Dict[str, str]       # Optional - for reference
    auth_method: str                    # "hmac-sha256", "ed25519", "rsa", etc.
    file_extension: str                 # Default: "txt"
    base_dir: str                       # Default: "."
    base64_encoded_fields: List[str]    # Fields that are base64-encoded
    setup_instructions: Dict[str, str]  # Help text per field
    
    supports_market_data: bool          # True if fetches prices
    supports_trading: bool              # True if executes orders
    supports_margin_trading: bool       # True if margin available
    supports_futures: bool              # True if futures available
)
```

## Credential Management

The `CredentialManager` class handles all file I/O:

```python
from exchange_credential_manager import CredentialManager

manager = CredentialManager(config)

# Read credentials
credentials, success = manager.read_credentials()
if success:
    api_key = credentials["api_key"]

# Write credentials
success, message = manager.write_credentials({
    "api_key": "...",
    "api_secret": "..."
})

# Check if credentials exist
if manager.credentials_exist():
    print("Ready to trade!")

# Get file paths (for debugging)
paths = manager.get_file_paths()
```

## Testing Your Implementation

Before integrating with the trading system:

```python
# Test market data fetching
from pt_thinker import myexchange_market_data

md = myexchange_market_data()
candles = md.get_klines("BTC-USD", "1h")
print(f"Got {len(candles)} candles")

# Test trading (be careful with real money!)
from pt_trader import MyExchangeTrading
from exchange_credential_manager import CredentialManager

manager = CredentialManager(config)
creds, _ = manager.read_credentials()

trader = MyExchangeTrading(creds["api_key"], creds["api_secret"])
balance = trader.get_account_value()
print(f"Account value: ${balance}")
```

## Common Authentication Patterns

### HMAC-SHA256 (Binance, Bybit, etc.)

```python
import hmac
import hashlib
import time

timestamp = str(int(time.time() * 1000))  # milliseconds
message = f"{timestamp}{api_key}{rest_of_body}"
signature = hmac.new(
    api_secret.encode(),
    message.encode(),
    hashlib.sha256
).hexdigest()
```

### ED25519 (Robinhood)

```python
import nacl.signing
import nacl.encoding
import time
import json
import hmac
import hashlib

key = nacl.signing.SigningKey(
    secret_key_bytes,
    encoder=nacl.encoding.RawEncoder
)

timestamp = str(int(time.time()))
signature = key.sign(f"{api_key}{timestamp}{path}{method}{body}".encode()).signature.hex()
```

### API-Sign Header (Kraken)

```python
import hashlib
import hmac
import time
from urllib.parse import urlencode

nonce = str(int(time.time() * 1000))
postdata = urlencode({"nonce": nonce, ...})

message = postdata.encode()
message_hash = hashlib.sha256(message).digest()

signature = hmac.new(
    api_secret.encode(),
    message_hash,
    hashlib.sha512
).digest()
```

## Troubleshooting

**"Module not found" error**: Make sure `exchange_credential_manager.py` and `wizard_template_generator.py` are in the same directory as `pt_hub.py`.

**Credentials not saving**: Check file permissions and ensure the directory is writable.

**API test failing**: Verify credentials are correct and API is accessible. Check network/firewall.

**Import errors in wizard**: Ensure all dependencies in `requirements.txt` are installed.

## Next Steps

1. Choose your exchange from the planned list (Binance, Kraken, Coinbase, Bybit)
2. Read the exchange's API documentation
3. Follow the "Quick Start" steps above
4. Implement the market data and trading classes
5. Test with small amounts or sandbox mode
6. Submit a pull request!

---

For questions or issues, check the existing implementations in `pt_thinker.py` and `pt_trader.py` for reference patterns.
