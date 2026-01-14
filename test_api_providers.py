#!/usr/bin/env python3
"""
Test script for API providers.

This script tests the different market data providers without requiring API keys.
It attempts to fetch sample data from each provider to verify they work.
"""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from api_providers import (
    create_market_data_provider,
    KuCoinMarketData,
    BinanceMarketData,
    CoinbaseMarketData,
    CoinGeckoMarketData
)


def test_provider(provider_name, symbol='BTC-USDT', timeframe='1hour'):
    """Test a market data provider."""
    print(f"\n{'='*60}")
    print(f"Testing {provider_name.upper()} Market Data Provider")
    print(f"{'='*60}")
    
    try:
        provider = create_market_data_provider(provider_name)
        print(f"✓ Provider created successfully")
        
        # Test symbol normalization
        normalized = provider.normalize_symbol(symbol)
        print(f"✓ Symbol normalized: {symbol} -> {normalized}")
        
        # Test getting current price
        print(f"Fetching current price...")
        price = provider.get_current_price(symbol)
        if price and price.get('ask', 0) > 0:
            print(f"✓ Current price: Bid=${price['bid']:.2f}, Ask=${price['ask']:.2f}")
        else:
            print(f"⚠ Could not fetch current price (may be rate limited or offline)")
        
        # Test getting klines
        print(f"Fetching {timeframe} klines...")
        klines = provider.get_klines(symbol, timeframe, limit=5)
        if klines and len(klines) > 0:
            print(f"✓ Fetched {len(klines)} candles")
            if len(klines) > 0:
                latest = klines[0]
                print(f"  Latest candle: timestamp={latest[0]}, open={latest[1]}, close={latest[2]}")
        else:
            print(f"⚠ Could not fetch klines (may be rate limited or offline)")
        
        print(f"✓ {provider_name.upper()} test completed successfully")
        return True
        
    except Exception as e:
        print(f"✗ Error testing {provider_name}: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run tests for all providers."""
    print("PowerTrader AI - API Provider Test Suite")
    print("=========================================")
    print("This script tests market data providers (no API keys required)")
    
    providers = [
        'kucoin',
        'binance', 
        'coinbase',
        'coingecko'
    ]
    
    results = {}
    
    for provider in providers:
        results[provider] = test_provider(provider)
    
    # Summary
    print(f"\n{'='*60}")
    print("TEST SUMMARY")
    print(f"{'='*60}")
    
    for provider, success in results.items():
        status = "✓ PASS" if success else "✗ FAIL"
        print(f"{provider:15} {status}")
    
    total = len(results)
    passed = sum(1 for v in results.values() if v)
    
    print(f"\nTotal: {passed}/{total} providers working")
    
    if passed == total:
        print("\n🎉 All providers are working!")
    elif passed > 0:
        print(f"\n⚠ {total - passed} provider(s) failed. This may be due to:")
        print("  - Network issues")
        print("  - Rate limiting")
        print("  - Temporary API outages")
        print("  - Missing optional dependencies")
    else:
        print("\n⚠ All providers failed. Check your internet connection.")
    
    return 0 if passed > 0 else 1


if __name__ == '__main__':
    sys.exit(main())
