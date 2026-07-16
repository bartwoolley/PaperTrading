# ASX Paper Trader V5.6.1 Hotfix

This hotfix keeps V5.6 features but fixes the Google Sheets 429 quota issue caused by repeated worksheet metadata reads during startup.

## Fixes

- Replaces repeated `spreadsheet().worksheet(name)` calls with one cached worksheet map.
- `ensure_schema()` now checks worksheet names from a cached metadata call instead of fetching metadata for every tab.
- Keeps Google Sheets reads cached for 3 minutes.
- Keeps automatic refresh at 5 minutes.
- Keeps V5.6 advanced Stage 2 scanner filters.
- Keeps realised P/L fix using all historical SELL transactions, including closed positions.
- Keeps the Performance page.

## Upload

Replace your GitHub repo root files with:

- `app.py`
- `broker.py`
- `sheets_db.py`
- `requirements.txt`
- `README.md`
- `STREAMLIT_SECRETS_TEMPLATE.toml`

Then commit to `main` and reboot the Streamlit Cloud app.

No changes are required to your Google Sheet, service account, or Streamlit Secrets.
