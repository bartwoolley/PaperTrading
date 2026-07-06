import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from streamlit_autorefresh import st_autorefresh

from broker import DEFAULT_ASX_UNIVERSE, norm, code, quote, fetch_daily, fetch_intraday, indicators, latest_price, scan_one, cash_balance, portfolio_df
from state_store import load_state, save_state, next_id, now

st.set_page_config(page_title="ASX Paper Trader V4", page_icon="📈", layout="wide")
st_autorefresh(interval=60000, key="refresh_v4")

state=load_state()

st.title("📈 ASX Paper Trader V4 - Cloud Edition")
st.caption("Browser-hosted paper trading workbench. Educational only — not financial advice and not real trading.")

with st.sidebar:
    st.header("Data")
    st.write("Use export/import as your cloud backup.")
    st.download_button("Export Data JSON", data=json.dumps(state,indent=2).encode("utf-8"), file_name="asx_paper_trader_v4_backup.json", mime="application/json")
    up=st.file_uploader("Import Data JSON", type=["json"])
    if up and st.button("Load imported data"):
        state=json.load(up); save_state(state); st.success("Imported data loaded."); st.rerun()
    if st.button("Save current state"):
        save_state(state); st.success("Saved.")
    st.divider()
    state["starting_cash"]=st.number_input("Starting fake cash", value=float(state.get("starting_cash",100000.0)), step=1000.0)
    if st.button("Save starting cash"):
        save_state(state); st.success("Starting cash saved.")

cash=cash_balance(state); pdf=portfolio_df(state)
market=float(pdf["Market value"].fillna(0).sum()) if not pdf.empty else 0.0
unreal=float(pdf["Unrealised P/L"].fillna(0).sum()) if not pdf.empty else 0.0
realised=float(pdf["Realised P/L"].fillna(0).sum()) if not pdf.empty else 0.0
c1,c2,c3,c4,c5=st.columns(5)
c1.metric("Cash",f"${cash:,.2f}"); c2.metric("Holdings",f"${market:,.2f}"); c3.metric("Portfolio",f"${cash+market:,.2f}"); c4.metric("Unrealised P/L",f"${unreal:,.2f}"); c5.metric("Realised P/L",f"${realised:,.2f}")

st.divider()
tabs=st.tabs(["Dashboard","Trade","Portfolio & Ledger","Watchlists","Charts","Scanner","Journal"])

with tabs[0]:
    st.subheader("Dashboard")
    if pdf.empty: st.info("No holdings yet. Add a paper trade from the Trade tab.")
    else:
        st.dataframe(pdf,use_container_width=True,hide_index=True)
        st.plotly_chart(px.bar(pdf,x="Code",y="Market value",title="Holdings by market value"),use_container_width=True)
        st.plotly_chart(px.bar(pdf,x="Code",y="Unrealised P/L",title="Unrealised P/L"),use_container_width=True)

with tabs[1]:
    st.subheader("Record paper trade")
    a,b=st.columns(2)
    with a:
        side=st.radio("Side",["BUY","SELL"],horizontal=True)
        ticker=st.text_input("ASX code",placeholder="CBA")
        t=norm(ticker); lp=latest_price(t) if t else None
        st.info(f"{t or '—'} latest: {('$' + format(lp, ',.3f')) if lp else 'Unavailable'}")
        qty=st.number_input("Quantity",min_value=1,value=100)
        price=st.number_input("Price",min_value=0.0,value=float(lp or 0.0),format="%.3f")
        brokerage=st.number_input("Brokerage/slippage",min_value=0.0,value=0.0)
        notes=st.text_area("Notes")
        if st.button("Add paper trade",type="primary"):
            state["trades"].append({"id":next_id(state["trades"]),"trade_time":now(),"side":side,"ticker":t,"quantity":int(qty),"price":float(price),"brokerage":float(brokerage),"notes":notes})
            save_state(state); st.success("Trade added."); st.rerun()
    with b:
        st.subheader("Cash adjustment")
        amt=st.number_input("Adjustment amount (+/-)",value=0.0,step=100.0)
        cn=st.text_input("Adjustment note",value="Cash adjustment")
        if st.button("Add cash adjustment"):
            state["trades"].append({"id":next_id(state["trades"]),"trade_time":now(),"side":"CASH","ticker":"CASH","quantity":1,"price":float(amt),"brokerage":0.0,"notes":cn})
            save_state(state); st.success("Cash adjustment added."); st.rerun()

with tabs[2]:
    st.subheader("Portfolio")
    st.dataframe(pdf,use_container_width=True,hide_index=True)
    st.subheader("Editable ledger")
    if not state["trades"]: st.info("No trades yet.")
    else:
        df=pd.DataFrame(state["trades"]); df["delete"]=False
        ed=st.data_editor(df,use_container_width=True,hide_index=True,num_rows="fixed")
        s1,s2=st.columns(2)
        if s1.button("Save ledger changes"):
            keep=ed.drop(columns=["delete"],errors="ignore").to_dict("records")
            state["trades"]=keep; save_state(state); st.success("Ledger saved."); st.rerun()
        if s2.button("Delete selected rows"):
            state["trades"]=ed[ed["delete"]!=True].drop(columns=["delete"],errors="ignore").to_dict("records")
            save_state(state); st.success("Selected rows deleted."); st.rerun()

with tabs[3]:
    st.subheader("Multiple watchlists")
    wl_names=list(state["watchlists"].keys())
    selected=st.selectbox("Watchlist",wl_names)
    newname=st.text_input("Create new watchlist")
    if st.button("Create watchlist") and newname:
        state["watchlists"].setdefault(newname,[]); save_state(state); st.rerun()
    add=st.text_input("Add ticker to selected watchlist")
    if st.button("Add ticker") and add:
        state["watchlists"].setdefault(selected,[])
        if norm(add) not in state["watchlists"][selected]: state["watchlists"][selected].append(norm(add))
        save_state(state); st.rerun()
    tickers=state["watchlists"].get(selected,[])
    if tickers:
        rows=[quote(x) for x in tickers]
        st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
        rem=st.selectbox("Remove ticker",tickers)
        if st.button("Remove ticker"):
            state["watchlists"][selected]=[x for x in tickers if x!=rem]; save_state(state); st.rerun()
    else: st.info("This watchlist is empty.")

with tabs[4]:
    st.subheader("Charts")
    chart_ticker=st.text_input("Ticker",value="CBA.AX")
    period=st.selectbox("Period",["1d intraday","5d","1mo","3mo","6mo","1y","2y"],index=0)
    fast=st.number_input("Fast EMA",min_value=2,value=20); slow=st.number_input("Slow EMA",min_value=5,value=50); long=st.number_input("Long EMA",min_value=20,value=200)
    opts=st.multiselect("Indicators",["Fast EMA","Slow EMA","Long EMA","Bollinger Bands","VWAP","Volume","RSI","MACD","ATR %"],default=["Fast EMA","Slow EMA","Volume","RSI","MACD"])
    raw=fetch_intraday(chart_ticker).reset_index() if period=="1d intraday" else fetch_daily(chart_ticker,period).reset_index()
    if raw.empty: st.warning("No chart data returned.")
    else:
        data=indicators(raw,int(fast),int(slow),int(long)); x="Datetime" if "Datetime" in data else "Date"
        fig=go.Figure(); fig.add_trace(go.Scatter(x=data[x],y=data["Close"],mode="lines",name="Close"))
        if "Fast EMA" in opts: fig.add_trace(go.Scatter(x=data[x],y=data[f"EMA{int(fast)}"],name=f"EMA{int(fast)}"))
        if "Slow EMA" in opts: fig.add_trace(go.Scatter(x=data[x],y=data[f"EMA{int(slow)}"],name=f"EMA{int(slow)}"))
        if "Long EMA" in opts: fig.add_trace(go.Scatter(x=data[x],y=data[f"EMA{int(long)}"],name=f"EMA{int(long)}"))
        if "Bollinger Bands" in opts:
            fig.add_trace(go.Scatter(x=data[x],y=data["BB_upper"],name="BB upper")); fig.add_trace(go.Scatter(x=data[x],y=data["BB_lower"],name="BB lower"))
        if "VWAP" in opts: fig.add_trace(go.Scatter(x=data[x],y=data["VWAP"],name="VWAP"))
        st.plotly_chart(fig,use_container_width=True)
        if "Volume" in opts and "Volume" in data: st.plotly_chart(px.bar(data,x=x,y="Volume",title="Volume"),use_container_width=True)
        if "RSI" in opts:
            r=go.Figure(); r.add_trace(go.Scatter(x=data[x],y=data["RSI"],name="RSI")); r.add_hline(y=70); r.add_hline(y=50); r.add_hline(y=30); r.update_layout(title="RSI"); st.plotly_chart(r,use_container_width=True)
        if "MACD" in opts:
            m=go.Figure(); m.add_trace(go.Scatter(x=data[x],y=data["MACD"],name="MACD")); m.add_trace(go.Scatter(x=data[x],y=data["MACD_signal"],name="Signal")); m.add_trace(go.Bar(x=data[x],y=data["MACD_hist"],name="Hist")); m.update_layout(title="MACD"); st.plotly_chart(m,use_container_width=True)
        if "ATR %" in opts: st.plotly_chart(px.line(data,x=x,y="ATR_pct",title="ATR %"),use_container_width=True)

with tabs[5]:
    st.subheader("Configurable scanner")
    preset=st.selectbox("Preset",list(state["scanner_presets"].keys()))
    cfg=dict(state["scanner_presets"][preset])
    c1,c2,c3=st.columns(3)
    cfg["fast_ema"]=c1.number_input("Fast EMA",value=int(cfg.get("fast_ema",20)))
    cfg["slow_ema"]=c2.number_input("Slow EMA",value=int(cfg.get("slow_ema",50)))
    cfg["long_ema"]=c3.number_input("Long EMA",value=int(cfg.get("long_ema",200)))
    cfg["crossover_lookback"]=c1.number_input("Crossover lookback",value=int(cfg.get("crossover_lookback",20)))
    cfg["rsi_min"]=c2.number_input("RSI min",value=float(cfg.get("rsi_min",50.0)))
    cfg["rsi_max"]=c3.number_input("RSI max",value=float(cfg.get("rsi_max",70.0)))
    cfg["require_price_above_fast"]=st.checkbox("Price above fast EMA",value=bool(cfg.get("require_price_above_fast",True)))
    cfg["require_price_above_slow"]=st.checkbox("Price above slow EMA",value=bool(cfg.get("require_price_above_slow",True)))
    cfg["require_price_above_long"]=st.checkbox("Price above long EMA",value=bool(cfg.get("require_price_above_long",False)))
    cfg["require_recent_cross"]=st.checkbox("Recent fast/slow EMA cross",value=bool(cfg.get("require_recent_cross",True)))
    cfg["require_macd_above_signal"]=st.checkbox("MACD above signal",value=bool(cfg.get("require_macd_above_signal",True)))
    cfg["require_macd_above_zero"]=st.checkbox("MACD above zero",value=bool(cfg.get("require_macd_above_zero",True)))
    f1,f2,f3=st.columns(3)
    cfg["min_price"]=f1.number_input("Min price",value=float(cfg.get("min_price",0.0)))
    cfg["max_price"]=f2.number_input("Max price (0 off)",value=float(cfg.get("max_price",0.0)))
    cfg["min_avg_volume"]=f3.number_input("Min avg volume",value=int(cfg.get("min_avg_volume",0)))
    cfg["min_avg_turnover"]=f1.number_input("Min avg turnover",value=float(cfg.get("min_avg_turnover",0.0)))
    cfg["max_atr_pct"]=f2.number_input("Max ATR % (0 off)",value=float(cfg.get("max_atr_pct",0.0)))
    cfg["new_high_lookback"]=f3.number_input("New high lookback (0 off)",value=int(cfg.get("new_high_lookback",0)))
    if st.button("Save preset changes"):
        state["scanner_presets"][preset]=cfg; save_state(state); st.success("Preset saved.")
    universe=st.radio("Universe",["Starter ASX list","Current selected watchlist","Custom list"],horizontal=True)
    if universe=="Starter ASX list": scan_codes=DEFAULT_ASX_UNIVERSE
    elif universe=="Current selected watchlist": scan_codes=[code(x) for x in state["watchlists"].get(list(state["watchlists"].keys())[0],[])]
    else:
        custom=st.text_area("Comma-separated tickers",value="CBA,BHP,WES,CSL,NAB")
        scan_codes=[x.strip() for x in custom.split(",") if x.strip()]
    if st.button("Run scanner",type="primary"):
        rows=[]; prog=st.progress(0)
        for i,t in enumerate(scan_codes): rows.append(scan_one(t,cfg)); prog.progress((i+1)/len(scan_codes))
        res=pd.DataFrame(rows).sort_values("Score",ascending=False)
        st.success(f"Scanner complete. Matches: {int(res['Match'].sum()) if 'Match' in res else 0} of {len(res)}")
        st.dataframe(res,use_container_width=True,hide_index=True)
        st.download_button("Download results CSV",data=res.to_csv(index=False).encode("utf-8"),file_name="asx_scanner_v4_results.csv",mime="text/csv")

with tabs[6]:
    st.subheader("Trade journal")
    with st.form("journal_form"):
        jt=st.text_input("Ticker",placeholder="CBA")
        setup=st.selectbox("Setup",["Momentum","Breakout","Pullback","Dividend","Other"])
        reason=st.text_area("Reason / thesis")
        risk=st.text_area("Risk / invalidation")
        lesson=st.text_area("Lesson / review")
        submitted=st.form_submit_button("Add journal entry")
        if submitted:
            state["journal"].append({"id":next_id(state["journal"]),"time":now(),"ticker":norm(jt),"setup":setup,"reason":reason,"risk":risk,"lesson":lesson})
            save_state(state); st.success("Journal entry added."); st.rerun()
    if state["journal"]:
        jdf=pd.DataFrame(state["journal"])
        st.dataframe(jdf,use_container_width=True,hide_index=True)
        st.download_button("Download journal CSV",data=jdf.to_csv(index=False).encode("utf-8"),file_name="asx_trade_journal_v4.csv",mime="text/csv")
