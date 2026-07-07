# ASX Paper Trader V5.3 - Scanner Restore + Company Value

V5.3 restores the scanner controls that were simplified in V5.2 and adds company value / market cap filtering.

## Restored scanner filters

- Min price
- Max price
- Minimum average volume
- Minimum average turnover
- Maximum ATR %
- New high lookback

## New scanner filters

- Company value / market cap
- Minimum market cap
- Maximum market cap

## Note on company value

The scanner uses Yahoo Finance data through `yfinance`. Company value is treated as **market capitalisation** where Yahoo provides it.

Upload all files to GitHub root and reboot Streamlit.
