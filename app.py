import json, pandas as pd, streamlit as st
from streamlit_autorefresh import st_autorefresh
import plotly.express as px
import plotly.graph_objects as go
import sheets_db as db
from broker import DEFAULT_ASX_UNIVERSE,norm,quote,fetch_daily,fetch_intraday,indicators,latest_price,scan_one,rank_results,cash_balance,portfolio_df
st.set_page_config(page_title="ASX Paper Trader V5.2",page_icon="📈",layout="wide")
st_autorefresh(interval=300000,key="refresh_v52")
try: db.ensure_schema()
except Exception as e: st.error("Could not connect to Google Sheets. Check Streamlit Secrets and Sheet sharing."); st.exception(e); st.stop()
settings=db.settings_dict(); trades=db.read_trades(); pdf=portfolio_df(trades); cash=cash_balance(settings,trades)
market=float(pdf["Market value"].fillna(0).sum()) if not pdf.empty else 0.0; unreal=float(pdf["Unrealised P/L"].fillna(0).sum()) if not pdf.empty else 0.0; realised=float(pdf["Realised P/L"].fillna(0).sum()) if not pdf.empty else 0.0
st.title("📈 ASX Paper Trader V5.2")
st.caption("Quota fix: cached Google Sheets reads + V5.1 bounce/momentum scanner.")
with st.sidebar:
    st.header("Cloud data"); st.success("Google Sheets connected")
    if st.button("Refresh Google Sheets cache"): db.clear_cache(); st.rerun()
    backup={"settings":settings,"trades":trades.to_dict("records"),"watchlists":db.read_watchlists().to_dict("records"),"journal":db.read_journal().to_dict("records"),"scanner_presets":db.presets_dict()}
    st.download_button("Export full backup JSON",json.dumps(backup,indent=2).encode(),"asx_v52_backup.json","application/json")
    st.divider(); settings["starting_cash"]=st.number_input("Starting fake cash",value=float(settings.get("starting_cash",100000.0)),step=1000.0)
    if st.button("Save settings"): db.write_settings(settings); st.success("Settings saved."); st.rerun()
cols=st.columns(5); cols[0].metric("Cash",f"${cash:,.2f}"); cols[1].metric("Holdings",f"${market:,.2f}"); cols[2].metric("Portfolio",f"${cash+market:,.2f}"); cols[3].metric("Unrealised P/L",f"${unreal:,.2f}"); cols[4].metric("Realised P/L",f"${realised:,.2f}")
st.divider(); tabs=st.tabs(["Dashboard","Trade","Ledger","Watchlists","Charts","Scanner V5.2","Journal","Data"])
with tabs[0]:
    st.subheader("Dashboard")
    if pdf.empty: st.info("No holdings yet. Add a paper trade from the Trade tab.")
    else:
        st.dataframe(pdf,use_container_width=True,hide_index=True); st.plotly_chart(px.bar(pdf,x="Code",y="Market value",title="Holdings by market value"),use_container_width=True); st.plotly_chart(px.bar(pdf,x="Code",y="Unrealised P/L",title="Unrealised P/L"),use_container_width=True)
with tabs[1]:
    st.subheader("Record paper trade"); a,b=st.columns(2)
    with a:
        side=st.radio("Side",["BUY","SELL"],horizontal=True); ticker=st.text_input("ASX code",placeholder="CBA"); t=norm(ticker); lp=latest_price(t) if t else None; st.info(f"{t or '—'} latest: {('$'+format(lp,',.3f')) if lp else 'Unavailable'}")
        qty=st.number_input("Quantity",min_value=1,value=100); price=st.number_input("Price",min_value=0.0,value=float(lp or 0.0),format="%.3f"); brokerage=st.number_input("Brokerage/slippage",min_value=0.0,value=0.0); notes=st.text_area("Notes")
        if st.button("Add paper trade",type="primary"):
            db.write_trades(pd.concat([trades,pd.DataFrame([{"id":db.next_id(trades),"trade_time":db.now(),"side":side,"ticker":t,"quantity":int(qty),"price":float(price),"brokerage":float(brokerage),"notes":notes}])],ignore_index=True)); st.success("Trade added."); st.rerun()
    with b:
        st.subheader("Cash adjustment"); amt=st.number_input("Adjustment amount (+/-)",value=0.0,step=100.0); cn=st.text_input("Adjustment note",value="Cash adjustment")
        if st.button("Add cash adjustment"):
            db.write_trades(pd.concat([trades,pd.DataFrame([{"id":db.next_id(trades),"trade_time":db.now(),"side":"CASH","ticker":"CASH","quantity":1,"price":float(amt),"brokerage":0.0,"notes":cn}])],ignore_index=True)); st.success("Cash adjustment added."); st.rerun()
with tabs[2]:
    st.subheader("Editable trade ledger")
    if trades.empty: st.info("No trades yet.")
    else:
        edit=trades.copy(); edit["delete"]=False; ed=st.data_editor(edit,use_container_width=True,hide_index=True,num_rows="fixed"); c1,c2,c3=st.columns(3)
        if c1.button("Save ledger changes"): db.write_trades(ed.drop(columns=["delete"],errors="ignore")); st.success("Ledger saved."); st.rerun()
        if c2.button("Delete selected rows"): db.write_trades(ed[ed["delete"]!=True].drop(columns=["delete"],errors="ignore")); st.success("Selected rows deleted."); st.rerun()
        c3.download_button("Download trades CSV",trades.to_csv(index=False).encode(),"asx_trades_v52.csv","text/csv")
with tabs[3]:
    st.subheader("Watchlists"); wdf=db.read_watchlists(); names=db.watchlist_names(); selected=st.selectbox("Watchlist",names); c1,c2=st.columns(2); newname=c1.text_input("New watchlist name")
    if c1.button("Create watchlist") and newname: db.write_watchlists(pd.concat([wdf,pd.DataFrame([{"watchlist":newname,"ticker":""}])],ignore_index=True)); st.rerun()
    add=c2.text_input("Add ticker")
    if c2.button("Add ticker") and add: db.write_watchlists(pd.concat([wdf,pd.DataFrame([{"watchlist":selected,"ticker":norm(add)}])],ignore_index=True)); st.rerun()
    tickers=db.tickers_for(selected)
    if tickers:
        st.dataframe(pd.DataFrame([quote(x) for x in tickers]),use_container_width=True,hide_index=True); rem=st.selectbox("Remove ticker",tickers)
        if st.button("Remove selected ticker"): db.write_watchlists(wdf[~((wdf["watchlist"]==selected)&(wdf["ticker"]==rem))]); st.rerun()
    else: st.info("This watchlist is empty.")
with tabs[4]:
    st.subheader("Charts"); chart_ticker=st.text_input("Ticker",value="CBA.AX"); period=st.selectbox("Period",["1d intraday","5d","1mo","3mo","6mo","1y","2y"],index=0); fast=st.number_input("Fast EMA",min_value=2,value=20); slow=st.number_input("Slow EMA",min_value=5,value=50); long=st.number_input("Long EMA",min_value=20,value=200); opts=st.multiselect("Indicators",["Fast EMA","Slow EMA","Long EMA","Volume","RSI","MACD"],default=["Fast EMA","Slow EMA","Volume","RSI","MACD"])
    raw=fetch_intraday(chart_ticker).reset_index() if period=="1d intraday" else fetch_daily(chart_ticker,period).reset_index()
    if raw.empty: st.warning("No chart data returned.")
    else:
        data=indicators(raw,int(fast),int(slow),int(long)); x="Datetime" if "Datetime" in data else "Date"; fig=go.Figure(); fig.add_trace(go.Scatter(x=data[x],y=data["Close"],mode="lines",name="Close"))
        if "Fast EMA" in opts: fig.add_trace(go.Scatter(x=data[x],y=data[f"EMA{int(fast)}"],name=f"EMA{int(fast)}"))
        if "Slow EMA" in opts: fig.add_trace(go.Scatter(x=data[x],y=data[f"EMA{int(slow)}"],name=f"EMA{int(slow)}"))
        if "Long EMA" in opts: fig.add_trace(go.Scatter(x=data[x],y=data[f"EMA{int(long)}"],name=f"EMA{int(long)}"))
        st.plotly_chart(fig,use_container_width=True)
        if "Volume" in opts: st.plotly_chart(px.bar(data,x=x,y="Volume",title="Volume"),use_container_width=True)
        if "RSI" in opts: st.plotly_chart(px.line(data,x=x,y="RSI",title="RSI"),use_container_width=True)
        if "MACD" in opts: st.plotly_chart(px.line(data,x=x,y=["MACD","MACD_signal","MACD_hist"],title="MACD"),use_container_width=True)
with tabs[5]:
    st.subheader("Scanner V5.2 - Bounce & Momentum Ranking"); presets=db.presets_dict(); preset=st.selectbox("Preset",list(presets.keys())); cfg=dict(presets[preset])
    with st.expander("Scanner settings",expanded=True):
        c1,c2,c3=st.columns(3); cfg["fast_ema"]=c1.number_input("Fast EMA",value=int(cfg.get("fast_ema",20))); cfg["slow_ema"]=c2.number_input("Slow EMA",value=int(cfg.get("slow_ema",50))); cfg["long_ema"]=c3.number_input("Long EMA",value=int(cfg.get("long_ema",200))); cfg["rsi_min"]=c1.number_input("RSI min",value=float(cfg.get("rsi_min",50.0))); cfg["rsi_max"]=c2.number_input("RSI max",value=float(cfg.get("rsi_max",70.0)))
        cfg["require_rising_fast_ema"]=st.checkbox("Require rising fast EMA",value=bool(cfg.get("require_rising_fast_ema",True))); cfg["require_rising_slow_ema"]=st.checkbox("Require rising slow EMA",value=bool(cfg.get("require_rising_slow_ema",False))); cfg["require_fresh_ema_alignment"]=st.checkbox("Require fast EMA above slow EMA for 5-20 days",value=bool(cfg.get("require_fresh_ema_alignment",True))); cfg["require_macd_hist_increasing"]=st.checkbox("Require increasing MACD histogram",value=bool(cfg.get("require_macd_hist_increasing",True))); cfg["require_volume_expansion"]=st.checkbox("Require volume expansion",value=bool(cfg.get("require_volume_expansion",True)))
        cfg["fast_ema_slope_lookback"]=c1.number_input("Fast EMA slope lookback",value=int(cfg.get("fast_ema_slope_lookback",5))); cfg["slow_ema_slope_lookback"]=c2.number_input("Slow EMA slope lookback",value=int(cfg.get("slow_ema_slope_lookback",10))); cfg["volume_expansion_multiplier"]=c3.number_input("Volume expansion multiplier",value=float(cfg.get("volume_expansion_multiplier",1.5)),step=0.1); cfg["min_fast_above_slow_days"]=c1.number_input("Min fast > slow days",value=int(cfg.get("min_fast_above_slow_days",5))); cfg["max_fast_above_slow_days"]=c2.number_input("Max fast > slow days",value=int(cfg.get("max_fast_above_slow_days",20))); cfg["min_macd_hist_increase_days"]=c3.number_input("Min increasing MACD hist days",value=int(cfg.get("min_macd_hist_increase_days",2)))
    if st.button("Save preset changes"): db.save_preset(preset,cfg); st.success("Preset saved.")
    universe=st.radio("Universe",["Starter ASX list","Custom list"],horizontal=True); scan_codes=DEFAULT_ASX_UNIVERSE if universe=="Starter ASX list" else [x.strip() for x in st.text_area("Comma-separated tickers",value="CBA,BHP,WES,CSL,NAB").split(",") if x.strip()]
    if st.button("Run V5.2 scanner",type="primary"):
        rows=[]; prog=st.progress(0)
        for i,t in enumerate(scan_codes): rows.append(scan_one(t,cfg)); prog.progress((i+1)/len(scan_codes))
        res=rank_results(pd.DataFrame(rows)); st.success(f"Scanner complete. Matches: {int(res['Match'].sum()) if 'Match' in res else 0} of {len(res)}"); st.dataframe(res,use_container_width=True,hide_index=True); st.download_button("Download scanner CSV",res.to_csv(index=False).encode(),"asx_scanner_v52.csv","text/csv")
with tabs[6]:
    st.subheader("Journal"); jdf=db.read_journal()
    with st.form("journal"):
        jt=st.text_input("Ticker",placeholder="CBA"); setup=st.selectbox("Setup",["Momentum","Breakout","Pullback","Dividend","Other"]); reason=st.text_area("Reason / thesis"); risk=st.text_area("Risk / invalidation"); lesson=st.text_area("Lesson / review")
        if st.form_submit_button("Add journal entry"):
            db.write_journal(pd.concat([jdf,pd.DataFrame([{"id":db.next_id(jdf),"time":db.now(),"ticker":norm(jt),"setup":setup,"reason":reason,"risk":risk,"lesson":lesson}])],ignore_index=True)); st.success("Journal entry added."); st.rerun()
    if not jdf.empty: st.dataframe(jdf,use_container_width=True,hide_index=True)
with tabs[7]:
    st.subheader("Quota fix details"); st.write("Reads are cached for 3 minutes. Schema checks are cached for 1 hour. Automatic refresh is every 5 minutes. Use the sidebar refresh button only when needed.")
