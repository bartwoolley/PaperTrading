# ASX Paper Trader V5.4 - Navigation + Dividend Chart Fix

V5.4 fixes the intermittent Streamlit tab issue by replacing `st.tabs()` with a sidebar page selector. Only one page renders at a time, so selecting a scanner preset should no longer cause all tab content to appear at once.

V5.4 also adds dividend overlays to charts:

- Ex-dividend markers on the price chart
- Dividend amount labels
- Recent dividend table below the chart

The dividend data is sourced from yfinance / Yahoo Finance where available.

Upload all files to your GitHub repo root and reboot the Streamlit app.
