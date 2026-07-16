# ASX Paper Trader V5.6 - Advanced Filters + Realised P/L Fix

V5.6 keeps the Stage 2 Breakout Scanner v3 workflow and restores advanced scanner controls.

## Key changes

### Scanner
- Stage A / B / C classification retained
- Advanced Filters section restored
- Minimum and maximum price
- Minimum average volume
- Minimum average turnover
- Market cap / company value min and max
- Rising 20 EMA and 50 EMA controls
- EMA slope controls
- EMA20 > EMA50 days range
- MACD above signal
- MACD above zero
- MACD histogram increasing
- MACD histogram increase days
- Recent MACD zero-cross
- Maximum ATR %
- Maximum distance above 20 EMA
- Maximum distance above 50 EMA
- Resistance lookback
- Higher-high / higher-low lookback

### Realised P/L fix
- Realised P/L is now calculated across **all trades**, including fully closed positions.
- Dashboard realised P/L no longer depends only on open holdings.
- New **Performance** page shows realised P/L by ticker, open/closed status, win/loss metrics and total P/L.
- SELL trade entry now checks current holding quantity before adding the sale.

## Deployment
Upload all files to the GitHub repo root and reboot the Streamlit Cloud app.

Files:
- app.py
- broker.py
- sheets_db.py
- requirements.txt
- README.md
- STREAMLIT_SECRETS_TEMPLATE.toml

No changes are required to Google Sheet, service account, or Streamlit secrets.
