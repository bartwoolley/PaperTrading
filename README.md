# ASX Paper Trader V4 - Cloud Edition

A Streamlit Cloud-ready ASX paper-trading workbench using Yahoo Finance data via `yfinance`.

> Educational/testing tool only. It does not place real trades and is not financial advice.

## Main features

- Browser-hosted Streamlit Cloud deployment
- Paper buy/sell trades
- Editable trade ledger
- Cash adjustments
- Multiple watchlists
- Configurable scanner presets
- Scanner scoring engine
- Portfolio dashboard
- Indicator-enabled charts
- Trade journal
- Data import/export as JSON

## Deploy to Streamlit Cloud

1. Create a GitHub repo, for example `asx-paper-trader-v4`.
2. Upload all files in this package to the root of the repo.
3. Go to Streamlit Community Cloud.
4. Create a new app.
5. Select your repo, branch `main`, and main file path `app.py`.
6. Deploy.

## Important persistence note

Streamlit Community Cloud local file storage is not intended as a permanent database. This app includes **Export Data** and **Import Data** tools so you can back up your paper portfolio and restore it later.

For a future production version, use Supabase, Azure SQL, PostgreSQL, or another durable database.
