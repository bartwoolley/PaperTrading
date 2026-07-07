# ASX Paper Trader V5.1 - Scanner Upgrade

V5.1 adds the scanner improvements discussed:

- Rising 20 EMA / fast EMA
- Rising 50 EMA / slow EMA
- Days that fast EMA has been above slow EMA, with configurable min/max range
- Increasing MACD histogram
- MACD histogram crossed above zero recently
- Volume expansion versus average volume
- Ranked scanner results
- Setup type classification: Early Bounce, Fresh Trend, Momentum Continuation, Breakout, Watch Only
- Component scores: Trend, Momentum, Volume, Freshness, Risk

Upload these files to your GitHub repo root:

- app.py
- broker.py
- sheets_db.py
- requirements.txt
- README.md
- STREAMLIT_SECRETS_TEMPLATE.toml

Do not upload your real Google JSON key to GitHub. Keep it in Streamlit Cloud secrets.
