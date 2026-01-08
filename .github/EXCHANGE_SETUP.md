# Exchange Integration Setup Guide

This document explains how to enable and configure different exchange integrations in PowerTrader AI.

## Supported Exchanges

### Active Platforms

#### Robinhood (Active - Trading)
- **Status**: Fully implemented and operational
- **Capabilities**: Crypto trading (buy/sell orders)
- **Setup Method**: GUI Setup Wizard
- **Credential Storage**: `r_key.txt` (API Key) and `r_secret.txt` (Private Key, base64-encoded)

**To enable Robinhood:**
1. Open Settings → find "Robinhood API" section
2. Click the ✓ checkbox to enable it
3. Click "Setup Wizard" to configure credentials
4. Follow the wizard steps to generate and register your API key

#### KuCoin (Active - Market Data)
- **Status**: Fully implemented (read-only market data)
- **Capabilities**: Historical candles (OHLCV data) for training
- **Setup Method**: GUI Setup Wizard (optional fallback to REST API)
- **Credential Storage**: `ku_key.txt`, `ku_secret.txt`, `ku_passphrase.txt`

**To enable KuCoin:**
1. Open Settings → find "KuCoin API" section
2. Click the ✓ checkbox to enable it
3. Click "Setup Wizard" to configure credentials (optional for public endpoints)
4. Click "Save" to persist changes

---

### Planned Platforms

These exchanges are not yet implemented but UI controls are available for future integration.

#### Binance
- **Type**: Spot & Futures trading
- **Status**: Coming in future updates
- **Expected Features**:
  - Market data: REST API (https://api.binance.com/api/v3/klines) or WebSocket
  - Order execution: Spot trading on `/api/v3/order`, Futures on `/fapi/v1/order`
  - Authentication: HMAC-SHA256 signature
- **Preparation Steps**:
  1. Create Binance API key: https://www.binance.com/en/my/settings/api-management
  2. Once setup wizard is available, prepare your credentials file structure

#### Kraken
- **Type**: European exchange (Spot + Futures)
- **Status**: Coming in future updates
- **Expected Features**:
  - Market data: REST API (https://api.kraken.com/0/public/OHLC)
  - Order execution: Private endpoints
  - Authentication: API-Sign header (SHA256 + HMAC-SHA512)
- **Preparation Steps**:
  1. Create Kraken API key: https://www.kraken.com/u/settings/api
  2. Ensure 2FA is enabled on your account for security

#### Coinbase
- **Type**: US-based exchange
- **Status**: Coming in future updates
- **Expected Features**:
  - Market data: REST API (https://api.coinbase.com/v2/products/{product_id}/candles)
  - Order execution: POST `/orders`
  - Authentication: HMAC-SHA256 signature
- **Preparation Steps**:
  1. Create Coinbase API key: https://coinbase.com/settings/api
  2. Enable appropriate permissions (trading, access account data)

#### Bybit
- **Type**: Derivatives platform
- **Status**: Coming in future updates
- **Expected Features**:
  - Market data: REST API (https://api.bybit.com/v5/market/kline) or WebSocket
  - Order execution: Spot and Futures `/order/create` endpoints
  - Authentication: API-Key header + X-BAPI-SIGN (HMAC-SHA256)
- **Preparation Steps**:
  1. Create Bybit API key: https://www.bybit.com/en/user-center/api-management
  2. Set appropriate IP whitelist for security

---

## Settings Dialog

### Access Settings
- From the main PowerTrader GUI, go to menu: **Settings** → **Settings**
- A scrollable dialog will open with all configuration options

### Exchange Configuration Section

The Exchange section is organized as follows:

#### Current Platforms
- **Robinhood API**: Enabled by default with Setup Wizard button
- **KuCoin API**: Enabled by default with Setup Wizard button

#### Future Platforms
- **Binance**: Checkbox to enable/disable (wizard coming soon)
- **Kraken**: Checkbox to enable/disable (wizard coming soon)
- **Coinbase**: Checkbox to enable/disable (wizard coming soon)
- **Bybit**: Checkbox to enable/disable (wizard coming soon)

### Saving Changes
1. Modify any settings including exchange enable/disable checkboxes
2. Scroll to the bottom of the Settings dialog
3. Click **"Save"** button
4. Settings are persisted to `gui_settings.json`

---

## Credential File Organization

### File Structure
All API credentials are stored as plain text files in the **PowerTrader root directory**:

```
PowerTrader_AI-main/
├── r_key.txt              # Robinhood API Key
├── r_secret.txt           # Robinhood Private Key (base64-encoded)
├── ku_key.txt             # KuCoin API Key
├── ku_secret.txt          # KuCoin Secret
├── ku_passphrase.txt      # KuCoin Passphrase
├── (future)
├── binance_key.txt        # Binance API Key (when implemented)
├── binance_secret.txt     # Binance Secret (when implemented)
├── kraken_key.txt         # Kraken API Key (when implemented)
├── kraken_secret.txt      # Kraken Secret (when implemented)
├── coinbase_key.txt       # Coinbase API Key (when implemented)
├── coinbase_secret.txt    # Coinbase Secret (when implemented)
├── bybit_key.txt          # Bybit API Key (when implemented)
└── bybit_secret.txt       # Bybit Secret (when implemented)
```

### Security Considerations
- **Never commit these files to version control** — add them to `.gitignore`
- **Treat private keys like passwords** — never share them
- **Use API key restrictions** — limit permissions to trading only if your exchange supports it
- **Rotate credentials regularly** — best practice for security
- **Use environment-specific keys** — consider separate keys for testnet vs. mainnet

---

## GUI Setup Wizards

### Robinhood Setup Wizard
The Robinhood wizard guides you through:
1. **Generating a keypair**: Creates an Ed25519 public/private key pair
2. **Registering with Robinhood**: Copy the public key and paste it into Robinhood's website
3. **Saving the API Key**: Robinhood provides an API key (usually starts with `rh...`)
4. **Persisting credentials**: Both keys are saved and encoded as needed

**Features:**
- Step-by-step instructions with links to Robinhood settings
- Copy-to-clipboard helpers for easy credential transfer
- Test button to verify credentials work
- Secure storage with base64 encoding for the private key

### KuCoin Setup Wizard
The KuCoin wizard helps you:
1. **Create API credentials**: Link to KuCoin API management
2. **Enter credentials**: Fields for API Key, Secret, and Passphrase
3. **Set permissions**: Configure appropriate API permissions
4. **Test connection**: Verify credentials with a public API call

**Features:**
- Support for API key rotation
- Simple text field entry for all three components
- Test button to validate settings

### Future Wizards (Placeholder)
When Binance, Kraken, Coinbase, and Bybit wizards are implemented, they will follow similar patterns:
- Clear instructions with external links
- Copy/paste helpers for credential transfer
- Test buttons to validate credentials
- Secure storage and rotation support

---

## Configuration File: gui_settings.json

The settings are saved to `gui_settings.json` with the following exchange-related keys:

```json
{
  "exchange_robinhood_enabled": true,
  "exchange_kucoin_enabled": true,
  "exchange_binance_enabled": false,
  "exchange_kraken_enabled": false,
  "exchange_coinbase_enabled": false,
  "exchange_bybit_enabled": false,
  "use_robinhood_api": true,
  "use_kucoin_api": true
}
```

### Key Meanings
- `exchange_*_enabled`: Controls whether the exchange is active (checkboxes in UI)
- `use_robinhood_api` / `use_kucoin_api`: Legacy compatibility flags (kept for backward compatibility)

---

## Troubleshooting

### "Not configured" error for Robinhood or KuCoin
- **Cause**: Setup wizard was skipped or credentials not saved
- **Solution**: Click "Setup Wizard" → enter credentials → click "Save"

### Exchange checkbox won't enable
- **Cause**: Feature not yet implemented
- **Solution**: This is normal for Binance, Kraken, Coinbase, Bybit until their wizards are built

### Can't find the settings dialog
- **Action**: In the main PowerTrader GUI, click menu → **Settings**

### Credentials seem to be missing
- **Check**: Look in the PowerTrader root folder for `*_key.txt` and `*_secret.txt` files
- **Note**: Some files may not exist until you run their setup wizard

### Setup wizard looks ugly or doesn't display properly
- **Try**: Resize the settings window
- **Try**: Check that tkinter is properly installed with `python -m tkinter`

---

## Development: Adding a New Exchange

To implement a new exchange (e.g., Binance):

1. **Add enable flag to DEFAULT_SETTINGS** (in `pt_hub.py`):
   ```python
   "exchange_binance_enabled": False,
   ```

2. **Create setup wizard function** (in `pt_hub.py`):
   ```python
   def _open_binance_api_wizard() -> None:
       # Build the wizard UI with steps
   ```

3. **Add UI checkbox and setup button** (in settings dialog):
   ```python
   binance_checkbox = ttk.Checkbutton(frm, variable=binance_enabled_var)
   binance_button = ttk.Button(frm, text="Setup Wizard", command=_open_binance_api_wizard)
   ```

4. **Implement credential helpers**:
   ```python
   def _binance_paths() -> Tuple[str, str]:
       # Return (key_path, secret_path)
   def _read_binance_files() -> Tuple[str, str]:
       # Read and return credentials
   ```

5. **Add credential file management** in `pt_thinker.py` and `pt_trader.py`:
   - Load credentials from `binance_key.txt` and `binance_secret.txt`
   - Implement REST API calls using Binance endpoints
   - Implement signing (HMAC-SHA256 for Binance)

6. **Update gui_settings.json save logic** to persist the enable flag

---

## Related Documentation
- [Copilot Instructions](./copilot-instructions.md) — Technical details on API patterns
- [README.md](../README.md) — General project information
- [pt_thinker.py](../pt_thinker.py) — Market data retrieval implementation
- [pt_trader.py](../pt_trader.py) — Trade execution implementation
