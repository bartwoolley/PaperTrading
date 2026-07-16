import json, pandas as pd, streamlit as st
from streamlit_autorefresh import st_autorefresh
import plotly.express as px
import plotly.graph_objects as go
import sheets_db as db
from broker import DEFAULT_ASX_UNIVERSE,norm,quote,fetch_daily,fetch_intraday,indicators,latest_price,stage2_scan_one,rank_stage_results,cash_balance,portfolio_df,dividends
st.set_page_config(page_title="ASX Paper Trader V5.5",page_icon="📈",layout="wide")
st_autorefresh(interval=300000,key="refresh_v55")
try: db.ensure_schema()
except Exception as e: st.error("Could not connect to Google Sheets. Check Streamlit Secrets and Sheet sharing."); st.exception(e); st.stop()
settings=db.settings_dict(); trades=db.read_trades(); pdf=portfolio_df(trades); cash=cash_balance(settings,trades)
market=float(pdf["Market value"].fillna(0).sum()) if not pdf.empty else 0.0; unreal=float(pdf["Unrealised P/L"].fillna(0).sum()) if not pdf.empty else 0.0; realised=float(pdf["Realised P/L"].fillna(0).sum()) if not pdf.empty else 0.0
st.title("📈 ASX Paper Trader V5.5")
st.caption("Stage 2 Breakout Scanner v3: Stage A watchlist, Stage B buy zone, Stage C momentum.")
with st.sidebar:
    st.header("Navigation")
    page=st.radio("Page",["Dashboard","Trade","Ledger","Watchlists","Charts","Stage 2 Scanner","Manual Scores","Journal","Data"],index=5)
    st.divider(); st.header("Cloud data"); st.success("Google Sheets connected")
    if st.button("Refresh Google Sheets cache"): db.clear_cache(); st.rerun()
    backup={"settings":settings,"trades":trades.to_dict("records"),"watchlists":db.read_watchlists().to_dict("records"),"journal":db.read_journal().to_dict("records"),"scanner_presets":db.presets_dict(),"manual_scores":db.read_manual_scores().to_dict("records")}
    st.download_button("Export backup JSON",json.dumps(backup,indent=2).encode(),"asx_v55_backup.json","application/json")
    st.divider(); settings["starting_cash"]=st.number_input("Starting fake cash",value=float(settings.get("starting_cash",100000.0)),step=1000.0)
    if st.button("Save settings"): db.write_settings(settings); st.success("Settings saved."); st.rerun()
cols=st.columns(5); cols[0].metric("Cash",f"${cash:,.2f}"); cols[1].metric("Holdings",f"${market:,.2f}"); cols[2].metric("Portfolio",f"${cash+market:,.2f}"); cols[3].metric("Unrealised P/L",f"${unreal:,.2f}"); cols[4].metric("Realised P/L",f"${realised:,.2f}")
st.divider()
if page=="Dashboard":
    st.subheader("Dashboard")
    if pdf.empty: st.info("No holdings yet.")
    else: st.dataframe(pdf,use_container_width=True,hide_index=True); st.plotly_chart(px.bar(pdf,x="Code",y="Market value",title="Holdings by market value"),use_container_width=True)
elif page=="Trade":
    st.subheader("Record paper trade"); a,b=st.columns(2)
    with a:
        side=st.radio("Side",["BUY","SELL"],horizontal=True); ticker=st.text_input("ASX code",placeholder="CBA"); t=norm(ticker); lp=latest_price(t) if t else None; st.info(f"{t or '—'} latest: {('$'+format(lp,',.3f')) if lp else 'Unavailable'}")
        qty=st.number_input("Quantity",min_value=1,value=100); price=st.number_input("Price",min_value=0.0,value=float(lp or 0.0),format="%.3f"); brokerage=st.number_input("Brokerage/slippage",min_value=0.0,value=0.0); notes=st.text_area("Notes")
        if st.button("Add paper trade",type="primary"):
            db.write_trades(pd.concat([trades,pd.DataFrame([{"id":db.next_id(trades),"trade_time":db.now(),"side":side,"ticker":t,"quantity":int(qty),"price":float(price),"brokerage":float(brokerage),"notes":notes}])],ignore_index=True)); st.success("Trade added."); st.rerun()
    with b:
        amt=st.number_input("Cash adjustment amount (+/-)",value=0.0,step=100.0); cn=st.text_input("Adjustment note",value="Cash adjustment")
        if st.button("Add cash adjustment"):
            db.write_trades(pd.concat([trades,pd.DataFrame([{"id":db.next_id(trades),"trade_time":db.now(),"side":"CASH","ticker":"CASH","quantity":1,"price":float(amt),"brokerage":0.0,"notes":cn}])],ignore_index=True)); st.success("Cash adjustment added."); st.rerun()
elif page=="Ledger":
    st.subheader("Editable trade ledger")
    if trades.empty: st.info("No trades yet.")
    else:
        edit=trades.copy(); edit["delete"]=False; ed=st.data_editor(edit,use_container_width=True,hide_index=True,num_rows="fixed")
        c1,c2=st.columns(2)
        if c1.button("Save ledger changes"): db.write_trades(ed.drop(columns=["delete"],errors="ignore")); st.success("Ledger saved."); st.rerun()
        if c2.button("Delete selected rows"): db.write_trades(ed[ed["delete"]!=True].drop(columns=["delete"],errors="ignore")); st.success("Selected rows deleted."); st.rerun()
elif page=="Watchlists":
    st.subheader("Watchlists"); wdf=db.read_watchlists(); names=db.watchlist_names(); selected=st.selectbox("Watchlist",names); c1,c2=st.columns(2); newname=c1.text_input("New watchlist name")
    if c1.button("Create watchlist") and newname: db.write_watchlists(pd.concat([wdf,pd.DataFrame([{"watchlist":newname,"ticker":""}])],ignore_index=True)); st.rerun()
    add=c2.text_input("Add ticker")
    if c2.button("Add ticker") and add: db.write_watchlists(pd.concat([wdf,pd.DataFrame([{"watchlist":selected,"ticker":norm(add)}])],ignore_index=True)); st.rerun()
    tickers=db.tickers_for(selected)
    if tickers: st.dataframe(pd.DataFrame([quote(x) for x in tickers]),use_container_width=True,hide_index=True)
    else: st.info("This watchlist is empty.")
elif page=="Charts":
    st.subheader("Charts with ex-dividend markers")
    chart_ticker=st.text_input("Ticker",value="CBA.AX"); period=st.selectbox("Period",["1d intraday","5d","1mo","3mo","6mo","1y","2y","5y"],index=5); show_div=st.checkbox("Show ex-dividend markers",value=True)
    raw=fetch_intraday(chart_ticker).reset_index() if period=="1d intraday" else fetch_daily(chart_ticker,period).reset_index()
    if raw.empty: st.warning("No chart data returned.")
    else:
        data=indicators(raw); x="Datetime" if "Datetime" in data else "Date"; data[x]=pd.to_datetime(data[x]).dt.tz_localize(None); fig=go.Figure(); fig.add_trace(go.Scatter(x=data[x],y=data["Close"],mode="lines",name="Close")); fig.add_trace(go.Scatter(x=data[x],y=data["EMA20"],name="EMA20")); fig.add_trace(go.Scatter(x=data[x],y=data["EMA50"],name="EMA50"))
        if show_div:
            div_df=dividends(chart_ticker,"5y")
            if not div_df.empty:
                dd=div_df[(div_df["Date"]>=data[x].min())&(div_df["Date"]<=data[x].max())].copy()
                if not dd.empty:
                    prices=data[[x,"Close"]].rename(columns={x:"Date"}).sort_values("Date"); dd=pd.merge_asof(dd.sort_values("Date"),prices,on="Date",direction="nearest"); fig.add_trace(go.Scatter(x=dd["Date"],y=dd["Close"],mode="markers+text",text=[f"${v:.2f}" for v in dd["Dividend"]],textposition="top center",name="Ex-dividend",marker=dict(size=10,symbol="diamond")))
        st.plotly_chart(fig,use_container_width=True); st.plotly_chart(px.bar(data,x=x,y="Volume",title="Volume"),use_container_width=True)
        if show_div:
            dshow=dividends(chart_ticker,"5y"); st.subheader("Recent dividends / payouts"); st.dataframe(dshow.sort_values("Date",ascending=False).head(20),use_container_width=True,hide_index=True) if not dshow.empty else st.info("No dividend data returned.")
elif page=="Stage 2 Scanner":
    st.subheader("Stage 2 Breakout Scanner v3")
    st.write("Ranks by Stage B first, then Stage A, then Stage C, so emerging buy-zone candidates appear before mature breakouts.")
    presets=db.presets_dict(); preset=st.selectbox("Preset",list(presets.keys())); cfg=dict(presets[preset])
    with st.expander("Automatic scan settings",expanded=True):
        c1,c2,c3=st.columns(3)
        cfg["fast_ema"]=c1.number_input("Fast EMA",value=int(cfg.get("fast_ema",20))); cfg["slow_ema"]=c2.number_input("Slow EMA",value=int(cfg.get("slow_ema",50))); cfg["long_ema"]=c3.number_input("Long EMA",value=int(cfg.get("long_ema",200)))
        cfg["ema_cross_min_days"]=c1.number_input("Stage B min days since 20/50 cross",value=int(cfg.get("ema_cross_min_days",5))); cfg["ema_cross_max_days"]=c2.number_input("Stage B max days since 20/50 cross",value=int(cfg.get("ema_cross_max_days",15))); cfg["max_distance_above_fast_pct"]=c3.number_input("Max distance above 20 EMA %",value=float(cfg.get("max_distance_above_fast_pct",8.0)),step=0.5)
        cfg["rsi_min_b"]=c1.number_input("Stage B RSI min",value=float(cfg.get("rsi_min_b",52.0))); cfg["rsi_max_b"]=c2.number_input("Stage B RSI max",value=float(cfg.get("rsi_max_b",68.0))); cfg["volume_expansion_multiplier"]=c3.number_input("Stage C volume multiplier",value=float(cfg.get("volume_expansion_multiplier",1.5)),step=0.1)
        cfg["min_price"]=c1.number_input("Min price",value=float(cfg.get("min_price",0.0))); cfg["max_price"]=c2.number_input("Max price (0 off)",value=float(cfg.get("max_price",0.0))); cfg["min_avg_volume"]=c3.number_input("Min avg volume",value=int(cfg.get("min_avg_volume",0)))
        cfg["min_avg_turnover"]=c1.number_input("Min avg turnover $",value=float(cfg.get("min_avg_turnover",0.0))); cfg["check_market_cap"]=c2.checkbox("Check market cap",value=bool(cfg.get("check_market_cap",False))); cfg["min_market_cap"]=c3.number_input("Min market cap $",value=float(cfg.get("min_market_cap",0.0)))
    if st.button("Save preset"): db.save_preset(preset,cfg); st.success("Preset saved")
    universe=st.radio("Universe",["Starter ASX list","Custom list"],horizontal=True); scan_codes=DEFAULT_ASX_UNIVERSE if universe=="Starter ASX list" else [x.strip() for x in st.text_area("Comma-separated tickers",value="NAB,CBA,ANZ,BGA").split(",") if x.strip()]
    if st.button("Run Stage 2 scan",type="primary"):
        rows=[]; prog=st.progress(0)
        for i,t in enumerate(scan_codes): rows.append(stage2_scan_one(t,cfg)); prog.progress((i+1)/len(scan_codes))
        res=rank_stage_results(pd.DataFrame(rows)); st.success(f"Scan complete. Stage B: {(res['Stage']=='Stage B - Emerging Trend').sum()} | Stage A: {(res['Stage']=='Stage A - Early Turnaround').sum()} | Stage C: {(res['Stage']=='Stage C - Confirmed Stage 2').sum()}"); st.dataframe(res,use_container_width=True,hide_index=True); st.download_button("Download Stage 2 scan CSV",res.to_csv(index=False).encode(),"asx_stage2_scan_v55.csv","text/csv")
elif page=="Manual Scores":
    st.subheader("Manual scoring layer")
    mdf=db.read_manual_scores()
    if mdf.empty: mdf=pd.DataFrame(columns=["ticker","manual_stage","chart_structure","volume_quality","distance_quality","resistance_overhead","catalyst_score","manual_confidence","notes","updated"])
    st.write("Use this after reviewing charts manually. Higher score = stronger candidate.")
    ed=st.data_editor(mdf,use_container_width=True,hide_index=True,num_rows="dynamic")
    if st.button("Save manual scores"):
        ed["updated"]=db.now(); db.write_manual_scores(ed); st.success("Manual scores saved"); st.rerun()
elif page=="Journal":
    st.subheader("Journal"); jdf=db.read_journal(); st.dataframe(jdf,use_container_width=True,hide_index=True)
elif page=="Data":
    st.subheader("V5.5 notes")
    st.markdown("""
**Stage A** is watchlist only. It looks for early short-term improvement before the 50 EMA has fully turned.  
**Stage B** is the primary buy zone. It looks for price above 20/50 EMA, recent 20/50 cross, RSI 52-68 and higher high/higher low structure.  
**Stage C** is confirmed momentum. It looks for breakout, volume expansion, EMA alignment and not being too extended above the 20 EMA.

The scanner uses automated proxies for chart structure. Use the **Manual Scores** page for items that need visual judgement, such as resistance overhead, volume quality and catalysts.
""")
