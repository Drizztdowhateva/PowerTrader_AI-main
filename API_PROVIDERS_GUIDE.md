# API Provider Configuration Guide

PowerTrader AI now supports multiple cryptocurrency exchange APIs for both market data and trading execution. This guide explains how to configure and use different providers.

## Overview

The system separates concerns into two types of providers:

1. **Market Data Providers**: Fetch historical candlestick data and current prices
2. **Trading Providers**: Execute buy/sell orders and manage account information

## Currently Supported Providers

### Market Data Providers
- **KuCoin** (default) - Free, no API key required for market data
- **Binance** - Fast and reliable, no API key required for market data
- **Binance US** - US-compliant version of Binance
- **Coinbase** - Good for US users
- **CoinGecko** - Free tier fallback option (limited features)

### Trading Providers
- **Robinhood** (default) - US-only, crypto trading
- **Binance** - Global exchange with high liquidity
- **Binance US** - US-compliant version
- **Coinbase** - US-based, regulated exchange

## Configuration

### Method 1: Using gui_settings.json (Recommended)

Edit your `gui_settings.json` file to include provider settings:

```json
{
  "coins": ["BTC", "ETH", "XRP", "BNB", "DOGE"],
  "main_neural_dir": "/path/to/your/data",
  "market_data_provider": "kucoin",
  "trading_provider": "robinhood"
}
```

### Method 2: Using Environment Variables

Set environment variables before running PowerTrader AI:

```bash
# Market data provider
export MARKET_DATA_PROVIDER=binance

# Trading provider  
export TRADING_PROVIDER=robinhood
```

## Provider-Specific Setup

### KuCoin (Default - Market Data)

**Pros**: Free, no signup required for market data, reliable
**Cons**: Not available for US trading

**Setup**: No configuration needed! Works out of the box.

```json
{
  "market_data_provider": "kucoin"
}
```

---

### Binance (Market Data & Trading)

**Pros**: High liquidity, low fees, reliable API
**Cons**: Not available in some regions (use Binance US for USA)

#### Market Data Only (No API Key Needed)

```json
{
  "market_data_provider": "binance"
}
```

#### Trading Setup (Requires API Keys)

1. **Create Binance Account**: Sign up at [binance.com](https://www.binance.com)
2. **Generate API Keys**:
   - Go to Account → API Management
   - Create a new API key
   - Enable "Enable Spot & Margin Trading"
   - Save your API Key and Secret Key
3. **Configure Environment Variables**:

```bash
export BINANCE_API_KEY="your_api_key_here"
export BINANCE_API_SECRET="your_secret_key_here"
```

4. **Update Settings**:

```json
{
  "market_data_provider": "binance",
  "trading_provider": "binance"
}
```

---

### Binance US (Market Data & Trading)

**Pros**: US-compliant, reliable
**Cons**: Fewer coins than global Binance, state restrictions apply

#### Setup (Similar to Binance)

1. Create account at [binance.us](https://www.binance.us)
2. Generate API keys with trading permissions
3. **Configure**:

```bash
export BINANCE_API_KEY="your_api_key_here"
export BINANCE_API_SECRET="your_secret_key_here"
export BINANCE_USE_US="true"
```

```json
{
  "market_data_provider": "binance_us",
  "trading_provider": "binance_us"
}
```

---

### Coinbase (Market Data & Trading)

**Pros**: US-regulated, beginner-friendly, trusted
**Cons**: Higher fees than Binance, fewer coins

#### Market Data Only (No API Key Needed)

```json
{
  "market_data_provider": "coinbase"
}
```

#### Trading Setup (Requires API Keys)

1. **Create Coinbase Account**: Sign up at [coinbase.com](https://www.coinbase.com)
2. **Generate Advanced Trade API Keys**:
   - Go to Settings → API
   - Create a new API key for **Advanced Trade**
   - Enable trading permissions
   - Save your API Key and Secret
3. **Configure Environment Variables**:

```bash
export COINBASE_API_KEY="your_api_key_here"
export COINBASE_API_SECRET="your_secret_here"
```

4. **Update Settings**:

```json
{
  "market_data_provider": "coinbase",
  "trading_provider": "coinbase"
}
```

---

### CoinGecko (Market Data Only - Fallback)

**Pros**: Free, no API key needed, covers almost all coins
**Cons**: Limited granularity, rate limits, approximate OHLC data

**Best Used**: As a fallback or for price checking only

```json
{
  "market_data_provider": "coingecko"
}
```

**Note**: CoinGecko provides limited historical data granularity. It's suitable for checking prices but not ideal for the AI training which requires detailed candlestick data.

---

### Robinhood (Trading Only - Default)

**Pros**: Easy to use, no trading fees, US-regulated
**Cons**: US-only, limited coins

**Setup**: Already configured if you followed the main setup guide.

Files needed:
- `r_key.txt` - Your Robinhood API key
- `r_secret.txt` - Your base64-encoded private key

The Hub's Settings → Robinhood API Setup wizard creates these files for you.

---

## Mixing Providers

You can use different providers for market data vs trading. This is useful for:

- Getting market data from a free source (KuCoin, CoinGecko) while trading on Robinhood
- Using Binance for fast market data while trading on Coinbase

**Example Configuration**:

```json
{
  "market_data_provider": "binance",
  "trading_provider": "robinhood"
}
```

## Credential Management

### Security Best Practices

1. **Never commit API keys to git**
2. **Use environment variables** for sensitive data
3. **Enable IP whitelisting** on exchange accounts
4. **Use API keys with minimal permissions** (only enable what you need)
5. **Regularly rotate API keys**

### Where to Store Credentials

**Option 1: Environment Variables (Recommended)**

```bash
# Add to your ~/.bashrc or ~/.zshrc
export BINANCE_API_KEY="your_key"
export BINANCE_API_SECRET="your_secret"
export COINBASE_API_KEY="your_key"
export COINBASE_API_SECRET="your_secret"
```

**Option 2: Separate Config File (Advanced)**

Create a `.env` file in your PowerTrader AI directory (add to .gitignore):

```env
BINANCE_API_KEY=your_key_here
BINANCE_API_SECRET=your_secret_here
COINBASE_API_KEY=your_key_here
COINBASE_API_SECRET=your_secret_here
```

Then load it before running:
```bash
export $(cat .env | xargs)
python pt_hub.py
```

## Troubleshooting

### "Unknown market data provider" Error

**Cause**: Typo in provider name or unsupported provider
**Solution**: Check spelling, must be one of: `kucoin`, `binance`, `binance_us`, `coinbase`, `coingecko`

### "Failed to fetch klines" or Empty Data

**Causes**:
1. API rate limits exceeded
2. Wrong symbol format for provider
3. Network issues
4. Exchange maintenance

**Solutions**:
- Wait a few minutes and retry
- Check exchange status pages
- Try a different market data provider
- Verify your internet connection

### "Authentication failed" for Trading

**Causes**:
1. Wrong API keys
2. Keys don't have trading permission
3. IP not whitelisted (if you enabled IP whitelist)
4. API key expired or revoked

**Solutions**:
- Regenerate API keys on the exchange
- Verify permissions are enabled
- Check IP whitelist settings
- Ensure keys are correctly set in environment variables

### Symbol Not Found

Different exchanges use different symbol formats:
- **KuCoin**: `BTC-USDT`
- **Binance**: `BTCUSDT` (no separator)
- **Coinbase**: `BTC-USD`
- **Robinhood**: `BTC-USD`

The system automatically converts symbols, but if you encounter issues, check the exchange's symbol list.

## Testing Your Configuration

### Test Market Data Provider

Run Python and test:

```python
from api_providers import create_market_data_provider

# Test KuCoin
provider = create_market_data_provider('kucoin')
klines = provider.get_klines('BTC-USDT', '1hour')
print(f"Fetched {len(klines)} candles from KuCoin")

# Test Binance
provider = create_market_data_provider('binance')
price = provider.get_current_price('BTCUSDT')
print(f"BTC price from Binance: ${price['ask']}")
```

### Test Trading Provider (Careful!)

**WARNING**: This places a real order! Use small amounts for testing.

```python
import os
from api_providers import create_trading_provider

# Test Robinhood (example)
provider = create_trading_provider(
    'robinhood',
    api_key=os.environ.get('ROBINHOOD_API_KEY'),
    private_key=os.environ.get('ROBINHOOD_PRIVATE_KEY')
)

# Check account first
account = provider.get_account_info()
print(f"Account info: {account}")
```

## Adding Your Own Provider

The system is designed to be extensible. To add a new exchange:

1. **Edit `api_providers.py`**
2. **Create a new class** inheriting from `MarketDataProvider` or `TradingProvider`
3. **Implement required methods**: `get_klines()`, `get_current_price()`, etc.
4. **Add to factory functions**: Update `create_market_data_provider()` or `create_trading_provider()`
5. **Test thoroughly** before using with real money

See the existing provider implementations in `api_providers.py` as examples.

## FAQ

**Q: Can I use multiple market data providers at once?**
A: Currently, the system uses one primary provider, but it automatically falls back if the primary fails.

**Q: Which provider is fastest?**
A: Binance typically has the fastest API response times, followed by KuCoin.

**Q: Which provider is most reliable?**
A: All major providers (KuCoin, Binance, Coinbase) are reliable. KuCoin and Binance have excellent uptime for market data.

**Q: Can I use one provider for some coins and another for others?**
A: Not currently, but this could be added as a feature. All coins use the same configured provider.

**Q: Do I need API keys for market data?**
A: No! Market data APIs are typically public and free. You only need API keys for trading execution.

**Q: What happens if my provider goes down?**
A: The system will attempt to use fallback methods. For KuCoin, it tries the Python client, then REST API. Consider setting up a backup provider.

**Q: Are there rate limits?**
A: Yes, all providers have rate limits:
- **KuCoin**: Very generous for public endpoints
- **Binance**: 1200 requests/minute (weight-based)
- **Coinbase**: Varies by endpoint
- **CoinGecko**: 10-50 calls/minute on free tier

PowerTrader AI is designed to stay well under these limits.

## Support

If you have issues with a specific provider:
1. Check the provider's status page
2. Review your API key permissions
3. Look at the PowerTrader AI logs for detailed errors
4. Try a different provider to isolate the issue
5. Open an issue on GitHub with:
   - Provider name
   - Error message
   - What you were trying to do

## Contributing

Want to add support for another exchange? Contributions are welcome!

1. Fork the repository
2. Add your provider implementation to `api_providers.py`
3. Test thoroughly with paper trading first
4. Submit a pull request with documentation
5. Include example configuration

Popular exchanges to consider adding:
- Kraken
- OKX
- Bitfinex
- HTX (Huobi)
- Bybit
- Gate.io
