# ASX Paper Trader V5.2 - Google Sheets Quota Fix

This package fixes the Google Sheets API 429 quota error by:

- Caching Google Sheets reads for 3 minutes
- Caching worksheet/schema checks for 1 hour
- Removing unnecessary worksheet reads during app start
- Reducing auto-refresh from 60 seconds to 5 minutes
- Adding a manual cache refresh button

Upload all files to your GitHub repo root and reboot the Streamlit app.

Use the same Streamlit Secrets you already configured. Do not upload your real Google JSON key to GitHub.
