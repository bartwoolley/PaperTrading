import json, pandas as pd, streamlit as st
from streamlit_autorefresh import st_autorefresh
import plotly.express as px
import plotly.graph_objects as go
import sheets_db as db
from broker import DEFAULT_ASX_UNIVERSE,norm,quote,fetch_daily,fetch_intraday,indicators,latest_price,scan_one,rank_results,cash_balance,portfolio_df,dividends
st.set_page_config(page_title="ASX Paper Trader V5.4",page_icon="📈",layout="wide")
st_autorefresh(interval=300000,key="refresh_v54")
try: db.ensure_schema()
except Exception as e: st.error("Could not connect to Google Sheets. Check Streamlit Secrets and Sheet sharing."); st.exception(e); st.stop()
settings=db.settings_dict(); trades=db.read_trades(); pdf=portfolio_df(trades); cash=cash_balance(settings,trades)
market=float(pdf["Market value"].fillna(0).sum()) if not pdf.empty else 0.0; unreal=float(pdf["Unrealised P/L"].fillna(0).sum()) if not pdf.empty else 0.0; realised=float(pdf["Realised P/L"].fillna(0).sum()) if not pdf.empty else 0.0
st.title("📈 ASX Paper Trader V5.4")
st.caption("Navigation fix + ex-dividend chart markers.")
with st.sidebar:
    st.header("Navigation")
    page=st.radio("Page",["Dashboard","Trade","Ledger","Watchlists","Charts","Scanner","Journal","Data"],index=0)
    st.divider(); st.header("Cloud data"); st.success("Google Sheets connected")
    if st.button("Refresh Google Sheets cache"): db.clear_cache(); st.rerun()
    backup={"settings":settings,"trades":trades.to_dict("records"),"watchlists":db.read_watchlists().to_dict("records"),"journal":db.read_journal().to_dict("records"),"scanner_presets":db.presets_dict()}
    st.download_button("Export backup JSON",json.dumps(backup,indent=2).encode(),"asx_v54_backup.json","application/json")
    st.divider(); settings["starting_cash"]=st.number_input("Starting fake cash",value=float(settings.get("starting_cash",100000.0)),step=1000.0)
    if st.button("Save settings"): db.write_settings(settings); st.success("Settings saved."); st.rerun()
cols=st.columns(5); cols[0].metric("Cash",f"${cash:,.2f}"); cols[1].metric("Holdings",f"${market:,.2f}"); cols[2].metric("Portfolio",f"${cash+market:,.2f}"); cols[3].metric("Unrealised P/L",f"${unreal:,.2f}"); cols[4].metric("Realised P/L",f"${realised:,.2f}")
st.divider()
if page=="Dashboard":
    st.subheader("Dashboard")
    if pdf.empty: st.info("No holdings yet. Add a paper trade from the Trade page.")
    else: st.dataframe(pdf,use_container_width=True,hide_index=True); st.plotly_chart(px.bar(pdf,x="Code",y="Market value",title="Holdings by market value"),use_container_width=True); st.plotly_chart(px.bar(pdf,x="Code",y="Unrealised P/L",title="Unrealised P/L"),use_container_width=True)
elif page=="Trade":
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
elif page=="Ledger":
    st.subheader("Editable trade ledger")
    if trades.empty: st.info("No trades yet.")
    else:
        edit=trades.copy(); edit["delete"]=False; ed=st.data_editor(edit,use_container_width=True,hide_index=True,num_rows="fixed"); c1,c2,c3=st.columns(3)
        if c1.button("Save ledger changes"): db.write_trades(ed.drop(columns=["delete"],errors="ignore")); st.success("Ledger saved."); st.rerun()
        if c2.button("Delete selected rows"): db.write_trades(ed[ed["delete"]!=True].drop(columns=["delete"],errors="ignore")); st.success("Selected rows deleted."); st.rerun()
        c3.download_button("Download trades CSV",trades.to_csv(index=False).encode(),"asx_trades_v54.csv","text/csv")
elif page=="Watchlists":
    st.subheader("Watchlists"); wdf=db.read_watchlists(); names=db.watchlist_names(); selected=st.selectbox("Watchlist",names); c1,c2=st.columns(2); newname=c1.text_input("New watchlist name")
    if c1.button("Create watchlist") and newname: db.write_watchlists(pd.concat([wdf,pd.DataFrame([{"watchlist":newname,"ticker":""}])],ignore_index=True)); st.rerun()
    add=c2.text_input("Add ticker")
    if c2.button("Add ticker") and add: db.write_watchlists(pd.concat([wdf,pd.DataFrame([{"watchlist":selected,"ticker":norm(add)}])],ignore_index=True)); st.rerun()
    tickers=db.tickers_for(selected)
    if tickers:
        st.dataframe(pd.DataFrame([quote(x) for x in tickers]),use_container_width=True,hide_index=True); rem=st.selectbox("Remove ticker",tickers)
        if st.button("Remove selected ticker"): db.write_watchlists(wdf[~((wdf["watchlist"]==selected)&(wdf["ticker"]==rem))]); st.rerun()
    else: st.info("This watchlist is empty.")
elif page=="Charts":
    st.subheader("Charts with ex-dividend markers")
    chart_ticker=st.text_input("Ticker",value="CBA.AX"); period=st.selectbox("Period",["1d intraday","5d","1mo","3mo","6mo","1y","2y","5y"],index=5)
    show_div=st.checkbox("Show ex-dividend markers and payout labels",value=True)
    raw=fetch_intraday(chart_ticker).reset_index() if period=="1d intraday" else fetch_daily(chart_ticker,period).reset_index()
    if raw.empty: st.warning("No chart data returned.")
    else:
        data=indicators(raw); x="Datetime" if "Datetime" in data else "Date"; data[x]=pd.to_datetime(data[x]).dt.tz_localize(None)
        fig=go.Figure(); fig.add_trace(go.Scatter(x=data[x],y=data["Close"],mode="lines",name="Close")); fig.add_trace(go.Scatter(x=data[x],y=data["EMA20"],name="EMA20")); fig.add_trace(go.Scatter(x=data[x],y=data["EMA50"],name="EMA50"))
        div_df=dividends(chart_ticker,"5y") if show_div else pd.DataFrame()
        if show_div and not div_df.empty:
            start,end=data[x].min(),data[x].max(); dd=div_df[(div_df["Date"]>=start)&(div_df["Date"]<=end)].copy()
            if not dd.empty:
                prices=data[[x,"Close"]].rename(columns={x:"Date"}).sort_values("Date")
                dd=pd.merge_asof(dd.sort_values("Date"),prices,on="Date",direction="nearest")
                fig.add_trace(go.Scatter(x=dd["Date"],y=dd["Close"],mode="markers+text",text=[f"${v:.2f}" for v in dd["Dividend"]],textposition="top center",name="Ex-dividend",marker=dict(size=10,symbol="diamond")))
                for _,r in dd.iterrows(): fig.add_vline(x=r["Date"],line_width=1,line_dash="dot")
        st.plotly_chart(fig,use_container_width=True)
        st.plotly_chart(px.bar(data,x=x,y="Volume",title="Volume"),use_container_width=True)
        if show_div:
            st.subheader("Recent dividends / payouts")
            dshow=dividends(chart_ticker,"5y")
            if dshow.empty: st.info("No dividend data returned by Yahoo Finance for this ticker.")
            else: st.dataframe(dshow.sort_values("Date",ascending=False).head(20),use_container_width=True,hide_index=True)
elif page=="Scanner":
    st.subheader("Scanner V5.4")
    presets=db.presets_dict(); preset=st.selectbox("Preset",list(presets.keys())); cfg=dict(presets[preset])
    with st.expander("Core trend and bounce",expanded=True):
        c1,c2,c3=st.columns(3); cfg["fast_ema"]=c1.number_input("Fast EMA",value=int(cfg.get("fast_ema",20))); cfg["slow_ema"]=c2.number_input("Slow EMA",value=int(cfg.get("slow_ema",50))); cfg["long_ema"]=c3.number_input("Long EMA",value=int(cfg.get("long_ema",200))); cfg["rsi_min"]=c1.number_input("RSI min",value=float(cfg.get("rsi_min",50.0))); cfg["rsi_max"]=c2.number_input("RSI max",value=float(cfg.get("rsi_max",70.0))); cfg["volume_expansion_multiplier"]=c3.number_input("Volume expansion multiplier",value=float(cfg.get("volume_expansion_multiplier",1.5)),step=0.1)
        cfg["require_rising_fast_ema"]=st.checkbox("Require rising 20/Fast EMA",value=bool(cfg.get("require_rising_fast_ema",True))); cfg["require_rising_slow_ema"]=st.checkbox("Require rising 50/Slow EMA",value=bool(cfg.get("require_rising_slow_ema",False))); cfg["require_fresh_ema_alignment"]=st.checkbox("Require Fast EMA above Slow EMA for short period",value=bool(cfg.get("require_fresh_ema_alignment",True))); cfg["require_macd_hist_increasing"]=st.checkbox("Require increasing MACD histogram",value=bool(cfg.get("require_macd_hist_increasing",True))); cfg["require_volume_expansion"]=st.checkbox("Require volume expansion",value=bool(cfg.get("require_volume_expansion",True)))
    with st.expander("Price, liquidity, risk and company value filters",expanded=True):
        f1,f2,f3=st.columns(3); cfg["min_price"]=f1.number_input("Min share price",value=float(cfg.get("min_price",0.0))); cfg["max_price"]=f2.number_input("Max share price (0 = off)",value=float(cfg.get("max_price",0.0))); cfg["min_avg_volume"]=f3.number_input("Min average volume",value=int(cfg.get("min_avg_volume",0)))
        cfg["min_avg_turnover"]=f1.number_input("Min average turnover $",value=float(cfg.get("min_avg_turnover",0.0))); cfg["max_atr_pct"]=f2.number_input("Max ATR % (0 = off)",value=float(cfg.get("max_atr_pct",0.0))); cfg["new_high_lookback"]=f3.number_input("New high lookback days (0 = off)",value=int(cfg.get("new_high_lookback",0)))
        cfg["check_market_cap"]=st.checkbox("Check company value / market cap",value=bool(cfg.get("check_market_cap",False))); cfg["min_market_cap"]=f1.number_input("Min company value / market cap $",value=float(cfg.get("min_market_cap",0.0))); cfg["max_market_cap"]=f2.number_input("Max company value / market cap $ (0 = off)",value=float(cfg.get("max_market_cap",0.0)))
    if st.button("Save preset changes"): db.save_preset(preset,cfg); st.success("Preset saved.")
    universe=st.radio("Universe",["Starter ASX list","Custom list"],horizontal=True); scan_codes=DEFAULT_ASX_UNIVERSE if universe=="Starter ASX list" else [x.strip() for x in st.text_area("Comma-separated tickers",value="CBA,BHP,WES,CSL,NAB").split(",") if x.strip()]
    if st.button("Run scanner",type="primary"):
        rows=[]; prog=st.progress(0)
        for i,t in enumerate(scan_codes): rows.append(scan_one(t,cfg)); prog.progress((i+1)/len(scan_codes))
        res=rank_results(pd.DataFrame(rows)); st.success(f"Scanner complete. Matches: {int(res['Match'].sum()) if 'Match' in res else 0} of {len(res)}"); st.dataframe(res,use_container_width=True,hide_index=True); st.download_button("Download scanner CSV",res.to_csv(index=False).encode(),"asx_scanner_v54.csv","text/csv")
elif page=="Journal":
    st.subheader("Journal"); jdf=db.read_journal(); st.dataframe(jdf,use_container_width=True,hide_index=True)
elif page=="Data":
    st.subheader("V5.4 notes"); st.write("This version uses a sidebar page selector instead of Streamlit tabs to avoid the all-tabs-open glitch. Google Sheets reads remain cached for quota protection. Dividend markers use yfinance dividend history where Yahoo returns it.")
