# Quick Start: Using Different Exchange APIs

This quick guide shows you how to switch to a different exchange API in PowerTrader AI.

## Default Setup (No Changes Needed)

By default, PowerTrader AI uses:
- **KuCoin** for market data (free, works automatically)
- **Robinhood** for trading (requires setup via GUI)

This works great and requires no additional configuration!

## Why Use Different Providers?

You might want to switch providers if:
- ✅ You want faster market data (try Binance)
- ✅ You want to trade on a different exchange (Binance, Coinbase)
- ✅ KuCoin is experiencing issues (switch to Binance or Coinbase)
- ✅ You're outside the US and can't use Robinhood (try Binance)
- ✅ You want a backup data source (CoinGecko)

## Method 1: Using the GUI (Easiest) ⭐

1. **Open PowerTrader AI Hub**
   ```bash
   python pt_hub.py
   ```

2. **Open Settings**
   - Click the "Settings" button

3. **Select Your Providers**
   - Find "Market Data Provider" dropdown
   - Select your choice: `kucoin`, `binance`, `binance_us`, `coinbase`, or `coingecko`
   - Find "Trading Provider" dropdown
   - Select your choice: `robinhood`, `binance`, `binance_us`, or `coinbase`

4. **Save**
   - Click "Save"
   - That's it!

**Note**: For trading providers other than Robinhood, you'll need to set up API keys (see below).

## Method 2: Edit Config File

1. **Open `gui_settings.json`** in a text editor

2. **Add these lines**:
   ```json
   {
     "coins": ["BTC", "ETH"],
     "main_neural_dir": "/your/path",
     "market_data_provider": "binance",
     "trading_provider": "robinhood"
   }
   ```

3. **Save and restart** PowerTrader AI

## Setting Up Trading on Other Exchanges

### For Binance

1. **Create Binance Account**: Go to [binance.com](https://www.binance.com) (or [binance.us](https://www.binance.us) for US)

2. **Generate API Keys**:
   - Account → API Management
   - Create new key
   - Enable "Enable Spot & Margin Trading"
   - Save your API Key and Secret

3. **Set Environment Variables** (Before running PowerTrader AI):
   
   **Windows (Command Prompt)**:
   ```cmd
   set BINANCE_API_KEY=your_api_key_here
   set BINANCE_API_SECRET=your_secret_here
   python pt_hub.py
   ```
   
   **macOS/Linux (Terminal)**:
   ```bash
   export BINANCE_API_KEY="your_api_key_here"
   export BINANCE_API_SECRET="your_secret_here"
   python pt_hub.py
   ```

4. **Select Binance in Settings** (see Method 1 above)

### For Coinbase

1. **Create Coinbase Account**: Go to [coinbase.com](https://www.coinbase.com)

2. **Generate API Keys**:
   - Settings → API
   - Create API key for "Advanced Trade"
   - Enable trading permissions
   - Save your API Key and Secret

3. **Set Environment Variables**:
   
   **Windows**:
   ```cmd
   set COINBASE_API_KEY=your_api_key_here
   set COINBASE_API_SECRET=your_secret_here
   python pt_hub.py
   ```
   
   **macOS/Linux**:
   ```bash
   export COINBASE_API_KEY="your_api_key_here"
   export COINBASE_API_SECRET="your_secret_here"
   python pt_hub.py
   ```

4. **Select Coinbase in Settings**

## Common Configurations

### Configuration 1: Fast Data + Robinhood Trading
**Best for**: US users who want fast market data

**Settings**:
```json
{
  "market_data_provider": "binance",
  "trading_provider": "robinhood"
}
```

**Setup**: No additional setup needed! Binance market data is free.

---

### Configuration 2: All Binance
**Best for**: International users, lower fees

**Settings**:
```json
{
  "market_data_provider": "binance",
  "trading_provider": "binance"
}
```

**Setup**: 
```bash
export BINANCE_API_KEY="..."
export BINANCE_API_SECRET="..."
```

---

### Configuration 3: US Compliant
**Best for**: US users who want Coinbase

**Settings**:
```json
{
  "market_data_provider": "coinbase",
  "trading_provider": "coinbase"
}
```

**Setup**:
```bash
export COINBASE_API_KEY="..."
export COINBASE_API_SECRET="..."
```

---

### Configuration 4: Fallback Data Source
**Best for**: When other providers are down

**Settings**:
```json
{
  "market_data_provider": "coingecko",
  "trading_provider": "robinhood"
}
```

**Setup**: No additional setup needed!

**Note**: CoinGecko has limited granularity, so it's best as a backup.

## Testing Your Setup

### Test Market Data
1. Start PowerTrader AI Hub
2. Click "Start All"
3. Watch the charts - they should populate with candles
4. If you see data, it's working! ✅

### Test Trading (Carefully!)
1. Make sure you have very small test amounts
2. Lower your trade amounts in settings
3. Let the bot make ONE small trade
4. Verify it appears on your exchange
5. If it works, gradually increase amounts

## Troubleshooting

### "Can't fetch data" or Empty Charts
- **Check internet connection**
- **Try a different provider** (switch to `binance` or `coinbase`)
- **Wait a few minutes** (might be temporary rate limit)
- **Check exchange status** (exchange might be down for maintenance)

### "Authentication failed" for Trading
- **Verify API keys** are correct
- **Check key permissions** on exchange (need trading enabled)
- **Regenerate keys** if old ones expired
- **Try Robinhood** as fallback (easier setup)

### "Provider not found" Error
- **Check spelling** in gui_settings.json
- **Valid options**: 
  - Market: `kucoin`, `binance`, `binance_us`, `coinbase`, `coingecko`
  - Trading: `robinhood`, `binance`, `binance_us`, `coinbase`

## Security Tips 🔒

1. **Never share API keys** with anyone
2. **Use API keys with minimal permissions** (only what you need)
3. **Enable IP whitelisting** on exchange if available
4. **Regularly rotate keys** (generate new ones periodically)
5. **Keep keys in environment variables** (not in code)
6. **Start with small amounts** when testing

## Getting More Help

- **Detailed docs**: Read `API_PROVIDERS_GUIDE.md` (comprehensive guide)
- **Developer guide**: Read `ADDING_NEW_PROVIDERS.md` (if you want to add exchanges)
- **Community**: Open an issue on GitHub if you need help

## Summary

✅ **Switching providers is easy**: Just use the GUI Settings dropdown
✅ **Most data providers are free**: No API keys needed for market data
✅ **Trading requires setup**: Set environment variables for API keys
✅ **Always start small**: Test with tiny amounts first
✅ **Backup providers**: Can switch anytime if one fails

Happy trading! 🚀
