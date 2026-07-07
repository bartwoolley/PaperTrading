import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from streamlit_autorefresh import st_autorefresh

import sheets_db as db
from broker import DEFAULT_ASX_UNIVERSE, norm, code, quote, fetch_daily, fetch_intraday, indicators, latest_price, scan_one, rank_results, cash_balance, portfolio_df

st.set_page_config(page_title="ASX Paper Trader V5.1", page_icon="📈", layout="wide")
st_autorefresh(interval=60000, key="refresh_v51")

try:
    db.ensure_schema()
except Exception as e:
    st.error("Could not connect to Google Sheets. Check Streamlit Secrets and Google Sheet sharing.")
    st.exception(e)
    st.stop()

settings = db.settings_dict()
trades = db.read_trades()
pdf = portfolio_df(trades)
cash = cash_balance(settings, trades)
market = float(pdf["Market value"].fillna(0).sum()) if not pdf.empty else 0.0
unreal = float(pdf["Unrealised P/L"].fillna(0).sum()) if not pdf.empty else 0.0
realised = float(pdf["Realised P/L"].fillna(0).sum()) if not pdf.empty else 0.0

st.title("📈 ASX Paper Trader V5.1")
st.caption("Scanner upgrade: rising EMAs, fresh EMA alignment, increasing MACD histogram, volume expansion and ranked results.")

with st.sidebar:
    st.header("Cloud data")
    st.success("Google Sheets connected")
    backup = {"settings": settings, "trades": trades.to_dict("records"), "watchlists": db.read_watchlists().to_dict("records"), "journal": db.read_journal().to_dict("records"), "scanner_presets": db.presets_dict()}
    st.download_button("Export full backup JSON", json.dumps(backup, indent=2).encode(), "asx_v51_backup.json", "application/json")
    st.divider()
    settings["starting_cash"] = st.number_input("Starting fake cash", value=float(settings.get("starting_cash", 100000.0)), step=1000.0)
    if st.button("Save settings"):
        db.write_settings(settings); st.success("Settings saved."); st.rerun()

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Cash", f"${cash:,.2f}"); m2.metric("Holdings", f"${market:,.2f}"); m3.metric("Portfolio", f"${cash+market:,.2f}"); m4.metric("Unrealised P/L", f"${unreal:,.2f}"); m5.metric("Realised P/L", f"${realised:,.2f}")
st.divider()

tabs = st.tabs(["Dashboard", "Trade", "Ledger", "Watchlists", "Charts", "Scanner V5.1", "Journal", "Data"])

with tabs[0]:
    st.subheader("Dashboard")
    if pdf.empty:
        st.info("No holdings yet. Add a paper trade from the Trade tab.")
    else:
        st.dataframe(pdf, use_container_width=True, hide_index=True)
        st.plotly_chart(px.bar(pdf, x="Code", y="Market value", title="Holdings by market value"), use_container_width=True)
        st.plotly_chart(px.bar(pdf, x="Code", y="Unrealised P/L", title="Unrealised P/L"), use_container_width=True)

with tabs[1]:
    st.subheader("Record paper trade")
    a, b = st.columns(2)
    with a:
        side = st.radio("Side", ["BUY", "SELL"], horizontal=True)
        ticker = st.text_input("ASX code", placeholder="CBA")
        t = norm(ticker); lp = latest_price(t) if t else None
        st.info(f"{t or '—'} latest: {('$' + format(lp, ',.3f')) if lp else 'Unavailable'}")
        qty = st.number_input("Quantity", min_value=1, value=100)
        price = st.number_input("Price", min_value=0.0, value=float(lp or 0.0), format="%.3f")
        brokerage = st.number_input("Brokerage/slippage", min_value=0.0, value=0.0)
        notes = st.text_area("Notes")
        if st.button("Add paper trade", type="primary"):
            new = {"id": db.next_id(trades), "trade_time": db.now(), "side": side, "ticker": t, "quantity": int(qty), "price": float(price), "brokerage": float(brokerage), "notes": notes}
            db.write_trades(pd.concat([trades, pd.DataFrame([new])], ignore_index=True)); st.success("Trade added."); st.rerun()
    with b:
        st.subheader("Cash adjustment")
        amt = st.number_input("Adjustment amount (+/-)", value=0.0, step=100.0)
        cn = st.text_input("Adjustment note", value="Cash adjustment")
        if st.button("Add cash adjustment"):
            new = {"id": db.next_id(trades), "trade_time": db.now(), "side": "CASH", "ticker": "CASH", "quantity": 1, "price": float(amt), "brokerage": 0.0, "notes": cn}
            db.write_trades(pd.concat([trades, pd.DataFrame([new])], ignore_index=True)); st.success("Cash adjustment added."); st.rerun()

with tabs[2]:
    st.subheader("Editable trade ledger")
    if trades.empty:
        st.info("No trades yet.")
    else:
        edit = trades.copy(); edit["delete"] = False
        ed = st.data_editor(edit, use_container_width=True, hide_index=True, num_rows="fixed")
        c1, c2, c3 = st.columns(3)
        if c1.button("Save ledger changes"):
            db.write_trades(ed.drop(columns=["delete"], errors="ignore")); st.success("Ledger saved."); st.rerun()
        if c2.button("Delete selected rows"):
            db.write_trades(ed[ed["delete"] != True].drop(columns=["delete"], errors="ignore")); st.success("Selected rows deleted."); st.rerun()
        c3.download_button("Download trades CSV", trades.to_csv(index=False).encode(), "asx_trades_v51.csv", "text/csv")

with tabs[3]:
    st.subheader("Watchlists")
    wdf = db.read_watchlists(); names = db.watchlist_names(); selected = st.selectbox("Watchlist", names)
    c1, c2 = st.columns(2)
    newname = c1.text_input("New watchlist name")
    if c1.button("Create watchlist") and newname:
        db.write_watchlists(pd.concat([wdf, pd.DataFrame([{"watchlist": newname, "ticker": ""}])], ignore_index=True)); st.rerun()
    add = c2.text_input("Add ticker")
    if c2.button("Add ticker") and add:
        db.write_watchlists(pd.concat([wdf, pd.DataFrame([{"watchlist": selected, "ticker": norm(add)}])], ignore_index=True)); st.rerun()
    tickers = db.tickers_for(selected)
    if tickers:
        st.dataframe(pd.DataFrame([quote(x) for x in tickers]), use_container_width=True, hide_index=True)
        rem = st.selectbox("Remove ticker", tickers)
        if st.button("Remove selected ticker"):
            db.write_watchlists(wdf[~((wdf["watchlist"] == selected) & (wdf["ticker"] == rem))]); st.rerun()
    else:
        st.info("This watchlist is empty.")

with tabs[4]:
    st.subheader("Charts")
    chart_ticker = st.text_input("Ticker", value="CBA.AX")
    period = st.selectbox("Period", ["1d intraday", "5d", "1mo", "3mo", "6mo", "1y", "2y"], index=0)
    fast = st.number_input("Fast EMA", min_value=2, value=20); slow = st.number_input("Slow EMA", min_value=5, value=50); long = st.number_input("Long EMA", min_value=20, value=200)
    opts = st.multiselect("Indicators", ["Fast EMA", "Slow EMA", "Long EMA", "Bollinger Bands", "VWAP", "Volume", "RSI", "MACD", "ATR %"], default=["Fast EMA", "Slow EMA", "Volume", "RSI", "MACD"])
    raw = fetch_intraday(chart_ticker).reset_index() if period == "1d intraday" else fetch_daily(chart_ticker, period).reset_index()
    if raw.empty:
        st.warning("No chart data returned.")
    else:
        data = indicators(raw, int(fast), int(slow), int(long)); x = "Datetime" if "Datetime" in data else "Date"
        fig = go.Figure(); fig.add_trace(go.Scatter(x=data[x], y=data["Close"], mode="lines", name="Close"))
        if "Fast EMA" in opts: fig.add_trace(go.Scatter(x=data[x], y=data[f"EMA{int(fast)}"], name=f"EMA{int(fast)}"))
        if "Slow EMA" in opts: fig.add_trace(go.Scatter(x=data[x], y=data[f"EMA{int(slow)}"], name=f"EMA{int(slow)}"))
        if "Long EMA" in opts: fig.add_trace(go.Scatter(x=data[x], y=data[f"EMA{int(long)}"], name=f"EMA{int(long)}"))
        if "Bollinger Bands" in opts:
            fig.add_trace(go.Scatter(x=data[x], y=data["BB_upper"], name="BB upper")); fig.add_trace(go.Scatter(x=data[x], y=data["BB_lower"], name="BB lower"))
        if "VWAP" in opts: fig.add_trace(go.Scatter(x=data[x], y=data["VWAP"], name="VWAP"))
        st.plotly_chart(fig, use_container_width=True)
        if "Volume" in opts: st.plotly_chart(px.bar(data, x=x, y="Volume", title="Volume"), use_container_width=True)
        if "RSI" in opts:
            r = go.Figure(); r.add_trace(go.Scatter(x=data[x], y=data["RSI"], name="RSI")); r.add_hline(y=70); r.add_hline(y=50); r.add_hline(y=30); r.update_layout(title="RSI"); st.plotly_chart(r, use_container_width=True)
        if "MACD" in opts:
            m = go.Figure(); m.add_trace(go.Scatter(x=data[x], y=data["MACD"], name="MACD")); m.add_trace(go.Scatter(x=data[x], y=data["MACD_signal"], name="Signal")); m.add_trace(go.Bar(x=data[x], y=data["MACD_hist"], name="Hist")); m.update_layout(title="MACD"); st.plotly_chart(m, use_container_width=True)
        if "ATR %" in opts: st.plotly_chart(px.line(data, x=x, y="ATR_pct", title="ATR %"), use_container_width=True)

with tabs[5]:
    st.subheader("Scanner V5.1 - Bounce & Momentum Ranking")
    presets = db.presets_dict(); preset = st.selectbox("Preset", list(presets.keys())); cfg = dict(presets[preset])
    with st.expander("Core trend and momentum", expanded=True):
        c1, c2, c3 = st.columns(3)
        cfg["fast_ema"] = c1.number_input("Fast EMA", value=int(cfg.get("fast_ema", 20)))
        cfg["slow_ema"] = c2.number_input("Slow EMA", value=int(cfg.get("slow_ema", 50)))
        cfg["long_ema"] = c3.number_input("Long EMA", value=int(cfg.get("long_ema", 200)))
        cfg["crossover_lookback"] = c1.number_input("Crossover lookback", value=int(cfg.get("crossover_lookback", 20)))
        cfg["rsi_min"] = c2.number_input("RSI min", value=float(cfg.get("rsi_min", 50.0)))
        cfg["rsi_max"] = c3.number_input("RSI max", value=float(cfg.get("rsi_max", 70.0)))
        for key,label,default in [("require_price_above_fast","Price above fast EMA",True),("require_price_above_slow","Price above slow EMA",True),("require_price_above_long","Price above long EMA",False),("require_recent_cross","Recent fast/slow EMA cross",False),("require_macd_above_signal","MACD above signal",True),("require_macd_above_zero","MACD above zero",False)]:
            cfg[key] = st.checkbox(label, value=bool(cfg.get(key, default)))
    with st.expander("V5.1 bounce filters", expanded=True):
        e1, e2, e3 = st.columns(3)
        cfg["require_rising_fast_ema"] = e1.checkbox("Require rising fast EMA", value=bool(cfg.get("require_rising_fast_ema", True)))
        cfg["fast_ema_slope_lookback"] = e2.number_input("Fast EMA slope lookback", value=int(cfg.get("fast_ema_slope_lookback", 5)))
        cfg["min_fast_ema_slope_pct"] = e3.number_input("Min fast EMA slope %", value=float(cfg.get("min_fast_ema_slope_pct", 0.0)), step=0.1)
        cfg["require_rising_slow_ema"] = e1.checkbox("Require rising slow EMA", value=bool(cfg.get("require_rising_slow_ema", False)))
        cfg["slow_ema_slope_lookback"] = e2.number_input("Slow EMA slope lookback", value=int(cfg.get("slow_ema_slope_lookback", 10)))
        cfg["min_slow_ema_slope_pct"] = e3.number_input("Min slow EMA slope %", value=float(cfg.get("min_slow_ema_slope_pct", 0.0)), step=0.1)
        cfg["require_fresh_ema_alignment"] = e1.checkbox("Require fast EMA above slow EMA for short period", value=bool(cfg.get("require_fresh_ema_alignment", True)))
        cfg["min_fast_above_slow_days"] = e2.number_input("Min fast > slow days", value=int(cfg.get("min_fast_above_slow_days", 5)))
        cfg["max_fast_above_slow_days"] = e3.number_input("Max fast > slow days", value=int(cfg.get("max_fast_above_slow_days", 20)))
        cfg["require_macd_hist_increasing"] = e1.checkbox("Require increasing MACD histogram", value=bool(cfg.get("require_macd_hist_increasing", True)))
        cfg["macd_hist_lookback"] = e2.number_input("MACD hist lookback days", value=int(cfg.get("macd_hist_lookback", 3)))
        cfg["min_macd_hist_increase_days"] = e3.number_input("Min increasing hist days", value=int(cfg.get("min_macd_hist_increase_days", 2)))
        cfg["require_macd_hist_above_zero"] = e1.checkbox("Require MACD histogram > 0", value=bool(cfg.get("require_macd_hist_above_zero", False)))
        cfg["require_macd_hist_crossed_above_zero"] = e2.checkbox("Require MACD hist crossed > 0 recently", value=bool(cfg.get("require_macd_hist_crossed_above_zero", False)))
        cfg["macd_hist_zero_cross_lookback"] = e3.number_input("MACD hist zero-cross lookback", value=int(cfg.get("macd_hist_zero_cross_lookback", 5)))
        cfg["require_volume_expansion"] = e1.checkbox("Require volume expansion", value=bool(cfg.get("require_volume_expansion", True)))
        cfg["volume_avg_period"] = e2.number_input("Volume avg period", value=int(cfg.get("volume_avg_period", 20)))
        cfg["volume_expansion_multiplier"] = e3.number_input("Volume expansion multiplier", value=float(cfg.get("volume_expansion_multiplier", 1.5)), step=0.1)
    with st.expander("Other filters", expanded=False):
        f1, f2, f3 = st.columns(3)
        cfg["min_price"] = f1.number_input("Min price", value=float(cfg.get("min_price", 0.0)))
        cfg["max_price"] = f2.number_input("Max price (0 off)", value=float(cfg.get("max_price", 0.0)))
        cfg["min_avg_volume"] = f3.number_input("Min avg volume", value=int(cfg.get("min_avg_volume", 0)))
        cfg["min_avg_turnover"] = f1.number_input("Min avg turnover", value=float(cfg.get("min_avg_turnover", 0.0)))
        cfg["max_atr_pct"] = f2.number_input("Max ATR % (0 off)", value=float(cfg.get("max_atr_pct", 0.0)))
        cfg["new_high_lookback"] = f3.number_input("New high lookback (0 off)", value=int(cfg.get("new_high_lookback", 0)))
    if st.button("Save preset changes"):
        db.save_preset(preset, cfg); st.success("Preset saved.")
    universe = st.radio("Universe", ["Starter ASX list", "Custom list"], horizontal=True)
    scan_codes = DEFAULT_ASX_UNIVERSE if universe == "Starter ASX list" else [x.strip() for x in st.text_area("Comma-separated tickers", value="CBA,BHP,WES,CSL,NAB").split(",") if x.strip()]
    if st.button("Run V5.1 scanner", type="primary"):
        rows = []; prog = st.progress(0)
        for i, t in enumerate(scan_codes):
            rows.append(scan_one(t, cfg)); prog.progress((i+1)/len(scan_codes))
        res = rank_results(pd.DataFrame(rows))
        st.success(f"Scanner complete. Matches: {int(res['Match'].sum()) if 'Match' in res else 0} of {len(res)}")
        st.dataframe(res, use_container_width=True, hide_index=True)
        st.download_button("Download scanner CSV", res.to_csv(index=False).encode(), "asx_scanner_v51.csv", "text/csv")

with tabs[6]:
    st.subheader("Journal")
    jdf = db.read_journal()
    with st.form("journal"):
        jt = st.text_input("Ticker", placeholder="CBA"); setup = st.selectbox("Setup", ["Momentum", "Breakout", "Pullback", "Dividend", "Other"]); reason = st.text_area("Reason / thesis"); risk = st.text_area("Risk / invalidation"); lesson = st.text_area("Lesson / review")
        if st.form_submit_button("Add journal entry"):
            new = {"id": db.next_id(jdf), "time": db.now(), "ticker": norm(jt), "setup": setup, "reason": reason, "risk": risk, "lesson": lesson}
            db.write_journal(pd.concat([jdf, pd.DataFrame([new])], ignore_index=True)); st.success("Journal entry added."); st.rerun()
    if not jdf.empty:
        st.dataframe(jdf, use_container_width=True, hide_index=True)
        st.download_button("Download journal CSV", jdf.to_csv(index=False).encode(), "asx_journal_v51.csv", "text/csv")

with tabs[7]:
    st.subheader("Readable Google Sheet tables")
    st.write("V5.1 continues using separate worksheet tabs: Settings, Trades, Watchlists, Journal and ScannerPresets.")
    st.write("The scanner preset is stored in the ScannerPresets tab as JSON so your selected V5.1 settings persist between sessions.")
