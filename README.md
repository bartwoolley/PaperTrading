# ASX Paper Trader V5.5 - Stage 2 Breakout Scanner v3

This version shifts the scanner from a single Stage 2 event to a three-stage progression:

- Stage A - Early Turnaround / Watchlist
- Stage B - Emerging Trend / Primary Buy Zone
- Stage C - Confirmed Stage 2 / Momentum

## Key additions

- Stage A/B/C classification
- Automatic confidence score out of 100
- Stage-specific reasons and warnings
- Distance above 20 EMA to avoid overextended entries
- Recent resistance / breakout proxy
- Higher highs and higher lows proxy
- Up-day volume behaviour proxy
- Manual scoring tab for chart structure, volume quality, resistance overhead, catalysts and notes
- Sidebar page navigation retained to avoid the Streamlit tabs-rendering bug
- Existing Google Sheets persistence retained

## Upload

Replace your GitHub repo files with:

- app.py
- broker.py
- sheets_db.py
- requirements.txt
- README.md
- STREAMLIT_SECRETS_TEMPLATE.toml

Then commit to main and reboot Streamlit Cloud.
