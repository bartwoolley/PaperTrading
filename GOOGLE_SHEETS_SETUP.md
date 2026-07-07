# ASX Paper Trader V4.1 - Google Sheets setup

## Your confirmed values

- Google Cloud Project ID: `papertrading-501606`
- Service account email: `tradingbot@papertrading-501606.iam.gserviceaccount.com`
- Google Sheet ID: `1RnsybqzaXyALESQ7Gkim92Nub2cc1O6ip1H3jeN41Ck`

## 1. Share the Google Sheet

Open the Google Sheet and share it with:

`tradingbot@papertrading-501606.iam.gserviceaccount.com`

Permission: **Editor**

## 2. Make sure Google Sheets API is enabled

In Google Cloud Console, go to APIs & Services > Library and enable:

- Google Sheets API
- Google Drive API

## 3. Create/download JSON key

Go to IAM & Admin > Service Accounts > tradingbot > Keys > Add key > Create new key > JSON.

Do not upload the JSON key file to GitHub.

## 4. Add Streamlit secrets

Open your Streamlit Cloud app > Settings > Secrets.

Use `STREAMLIT_SECRETS_TEMPLATE.toml` as the structure, copying values from your downloaded JSON key.

## 5. Upload this V4.1 package to GitHub

Replace the existing V4 files with this package and commit to `main`.

Streamlit should redeploy automatically. If not, reboot the app.

## What V4.1 changes

V4 stored app data in a local JSON file. V4.1 stores the app state in your Google Sheet tab called `State`, cell `A1`. That means trades, watchlists, presets and journal entries can follow you across PCs.
