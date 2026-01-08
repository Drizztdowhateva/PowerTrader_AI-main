# API Setup Wizards — User Quick Guide

## 🚀 Getting Started with New Exchanges

### Access the Setup Wizards

1. **Open PowerTrader** (run `python pt_hub.py`)
2. **Click Settings menu** (top menu bar)
3. **Click Settings** (opens settings dialog)
4. **Scroll down** to "Future Exchange Platforms"
5. **Check the exchange** you want to enable (☑ Binance, Kraken, Coinbase, or Bybit)
6. **Click "Setup Wizard"** button
7. **Follow the instructions in the window**

---

## 📊 Binance Setup (5 minutes)

**For Spot & Futures Trading**

1. Click "Setup Wizard" next to Binance checkbox
2. Read the instructions in the window
3. Click the link: https://www.binance.com/en/my/settings/api-management
4. Create new API key called "PowerTrader"
5. Copy your **API Key** (long string)
6. Copy your **Secret Key** (another long string)
7. Return to wizard, paste into the text fields
8. Click "Test" to verify (optional but recommended)
9. Click "Save" to store credentials
10. Success! ✅ Credentials saved to `binance_key.txt` and `binance_secret.txt`

**What the wizard does:**
- ✅ Tests connectivity to Binance API
- ✅ Saves credentials securely to files
- ✅ Pre-fills credentials next time you open the wizard

---

## 🏛️ Kraken Setup (5 minutes)

**For Spot & Futures Trading**

1. Click "Setup Wizard" next to Kraken checkbox
2. Read the instructions
3. Click the link: https://www.kraken.com/u/settings/api
4. Click "Generate New Key"
5. Name it: "PowerTrader"
6. Select permissions:
   - ☑ Query Funds
   - ☑ Query Open Orders
   - ☑ Query Closed Orders
   - ☑ Create & Modify Orders
7. Copy the **API Key**
8. Copy the **Private Key**
9. Paste into wizard fields
10. Click "Test" (optional)
11. Click "Save"
12. Success! ✅ Credentials saved

---

## 🪙 Coinbase Setup (5 minutes)

**For Advanced Trading (Pro account required)**

1. Click "Setup Wizard" next to Coinbase checkbox
2. Note: You need a Coinbase Pro account
3. Click the link: https://coinbase.com/settings/api
4. Click "New API Key"
5. Name: "PowerTrader"
6. Permissions needed:
   - wallet:accounts:read
   - wallet:sells:create
   - wallet:buys:create
7. Copy the **API Key**
8. Copy the **Secret**
9. Paste into wizard
10. Click "Test" (optional)
11. Click "Save"
12. Success! ✅ Credentials saved

---

## ⚡ Bybit Setup (5 minutes)

**For Spot & Derivatives Trading**

1. Click "Setup Wizard" next to Bybit checkbox
2. Read instructions
3. Click: https://www.bybit.com/en/user-center/api-management
4. Click "Create New Key"
5. Permissions:
   - ☑ Account
   - ☑ Orders
   - ☑ Exchange
6. (Optional) Set IP whitelist to your current IP for security
7. Copy the **API Key**
8. Copy the **Secret Key**
9. Paste into wizard
10. Click "Test" (optional)
11. Click "Save"
12. Success! ✅ Credentials saved

---

## ❓ FAQ

### "What does the Test button do?"
The Test button checks if you can connect to the exchange's public API. It doesn't use your API key (no authentication needed). If you see a checkmark ✅, your internet connection and the exchange are working.

### "Where are my credentials saved?"
In the PowerTrader root folder:
- Binance: `binance_key.txt` and `binance_secret.txt`
- Kraken: `kraken_key.txt` and `kraken_secret.txt`
- Coinbase: `coinbase_key.txt` and `coinbase_secret.txt`
- Bybit: `bybit_key.txt` and `bybit_secret.txt`

### "Can I edit credentials later?"
Yes! Just open the Setup Wizard again. Your existing credentials will be pre-filled. You can modify them and click Save to update.

### "Is this secure?"
Credentials are stored as plain text files. **Important**: Add these files to `.gitignore` so they don't get uploaded to GitHub:
```
# .gitignore
*_key.txt
*_secret.txt
r_key.txt
r_secret.txt
```

### "What if I forget my API key?"
You can regenerate it on the exchange website. Then open the wizard again and paste the new key.

### "Can I delete my credentials?"
Yes, just delete the credential files. Or open the wizard and clear the text fields, then click Save (saves empty strings).

---

## ⚠️ Security Tips

1. **Never share your Secret Key** — It's like a password
2. **Use IP whitelisting** if the exchange supports it (Bybit recommended)
3. **Limit permissions** on the exchange (e.g., "Spot trading only")
4. **Rotate credentials regularly** (generate new keys every 3-6 months)
5. **Don't commit to git** — Make sure `.gitignore` includes `*_key.txt` and `*_secret.txt`
6. **Keep files private** — Only you should have access to these files

---

## 🔄 Workflow

### First Time Setup
1. Open Settings
2. Check exchange checkbox
3. Click "Setup Wizard"
4. Create API key on exchange website
5. Paste credentials in wizard
6. Click Save
7. Done! ✅

### Later Use
1. PowerTrader loads credentials automatically from files
2. No need to re-enter them
3. To update: Open wizard, modify, click Save

### Switch Exchanges
1. Check new exchange checkbox
2. Uncheck old one (optional)
3. Settings saved automatically

---

## 📞 Troubleshooting

### Wizard won't open
- Make sure you clicked the correct "Setup Wizard" button
- Check that the checkbox is available (should be for Binance, Kraken, Coinbase, Bybit)

### Test button fails
- Check your internet connection
- Make sure API Key and Secret are entered
- Wait a few seconds and try again
- Exchange might be temporarily down

### Save button doesn't work
- Make sure both API Key and Secret are filled in
- Check that the PowerTrader folder is readable/writable
- Try closing and reopening the wizard

### Credentials not saving
- Look for an error message in the popup
- Check that you have permission to write files in the PowerTrader folder
- Try saving with different credentials first to test

### Can't find my saved credentials
- Check the PowerTrader root folder for `binance_key.txt` etc.
- Look at the files created date (should be recent)
- If missing, run the wizard again and save

---

## 🎯 Next Steps

After setting up credentials:
1. PowerTrader will use them to fetch market data and execute trades
2. Check the thinker/trader logs for errors
3. Start with paper trading (if available on the exchange)
4. Monitor your first few automated trades carefully

---

**Ready to get started? Open PowerTrader Settings now! 🚀**
