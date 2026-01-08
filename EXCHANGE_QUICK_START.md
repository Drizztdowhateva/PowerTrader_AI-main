# Quick Start: Exchange Configuration

## For Users

### See Your Exchange Settings
1. Open PowerTrader GUI
2. Click **Settings** menu → **Settings**
3. Scroll down to find "Exchange Platforms" section
4. You'll see checkboxes for:
   - ✅ Robinhood (enabled by default)
   - ✅ KuCoin (enabled by default)
   - ☐ Binance (coming soon)
   - ☐ Kraken (coming soon)
   - ☐ Coinbase (coming soon)
   - ☐ Bybit (coming soon)

### Setup Robinhood (Required for Trading)
1. In Settings dialog, check the Robinhood checkbox
2. Click **"Setup Wizard"** button
3. Follow the step-by-step wizard:
   - Generate a keypair
   - Copy public key to Robinhood website
   - Paste API key back into wizard
   - Click Save
4. Click **"Save"** at bottom of Settings dialog

### Setup KuCoin (For Market Data)
1. In Settings dialog, check the KuCoin checkbox
2. Click **"Setup Wizard"** button
3. Enter your KuCoin API credentials
4. Click **"Save"** at bottom of Settings dialog

### Future Exchanges
When clicked, each future exchange button will show a helpful message with:
- What the exchange is used for
- Where to create API keys
- What credential files to prepare

---

## For Developers

### Add a New Exchange

#### 1. Add Default Settings (pt_hub.py)
```python
DEFAULT_SETTINGS = {
    # ... existing settings ...
    "exchange_myexchange_enabled": False,
}
```

#### 2. Create Setup Wizard (pt_hub.py)
```python
def _open_myexchange_api_wizard() -> None:
    """Build and show the setup wizard window."""
    wiz = tk.Toplevel(win)
    wiz.title("MyExchange API Setup")
    # ... build UI with credential fields ...
    # ... add test button ...
    # ... add save button ...
```

#### 3. Add UI Checkbox (pt_hub.py)
```python
myexchange_enabled_var = tk.BooleanVar(value=bool(...))
# In the exchange section of settings dialog:
ex_chk = ttk.Checkbutton(ex_row, variable=myexchange_enabled_var)
# Add button:
ttk.Button(ex_row, text="Setup Wizard", command=_open_myexchange_api_wizard)
```

#### 4. Add Save Logic (pt_hub.py)
```python
def save():
    # ... existing code ...
    self.settings["exchange_myexchange_enabled"] = bool(myexchange_enabled_var.get())
    self._save_settings()
```

#### 5. Implement Market Data (pt_thinker.py)
```python
class MyExchangeMarketData:
    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret
    
    def get_candles(self, symbol: str, timeframe: str, limit: int = 120) -> List[dict]:
        # Fetch OHLCV candles from your exchange
        pass
```

#### 6. Implement Trading (pt_trader.py)
```python
class MyExchangeTrader:
    def __init__(self, api_key: str, api_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret
    
    def place_order(self, symbol: str, side: str, qty: float, price: float = None) -> dict:
        # Place buy/sell orders
        pass
    
    def get_account_value(self) -> float:
        # Get current account balance
        pass
```

#### 7. Load Credentials When Needed
```python
# In pt_thinker.py or pt_trader.py:
settings = ...
if settings.get("exchange_myexchange_enabled"):
    try:
        with open("myexchange_key.txt") as f:
            api_key = f.read().strip()
        with open("myexchange_secret.txt") as f:
            api_secret = f.read().strip()
        market_data = MyExchangeMarketData(api_key, api_secret)
    except Exception as e:
        log_error(f"MyExchange not configured: {e}")
```

---

## File Reference

### Main Implementation
- `pt_hub.py` — GUI, settings dialog, wizards
- `pt_thinker.py` — Market data fetching
- `pt_trader.py` — Order execution
- `gui_settings.json` — Saved settings

### Documentation
- `.github/EXCHANGE_SETUP.md` — Full user guide
- `API_SETUP_IMPLEMENTATION.md` — Technical implementation details
- `.github/copilot-instructions.md` — API patterns and conventions

### Credential Files
- `r_key.txt` — Robinhood API key
- `r_secret.txt` — Robinhood private key (base64)
- `ku_key.txt` — KuCoin API key
- `ku_secret.txt` — KuCoin secret
- `ku_passphrase.txt` — KuCoin passphrase
- `{exchange}_key.txt` — Future exchange API keys
- `{exchange}_secret.txt` — Future exchange secrets

---

## Testing Checklist

- [ ] Open Settings dialog
- [ ] See all exchange checkboxes
- [ ] Toggle Robinhood checkbox on/off
- [ ] Toggle KuCoin checkbox on/off
- [ ] Toggle future exchange checkboxes (Binance, Kraken, etc.)
- [ ] Click each "Setup Wizard" button for future exchanges
- [ ] Verify placeholder info dialogs appear
- [ ] Click "Save" in Settings dialog
- [ ] Check `gui_settings.json` has all exchange_*_enabled flags
- [ ] Reopen Settings dialog
- [ ] Verify checkbox states match saved settings
- [ ] Robinhood setup wizard still works
- [ ] KuCoin setup wizard still works

---

**Status**: ✅ Implementation complete and tested
