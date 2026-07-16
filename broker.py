from datetime import datetime
import numpy as np, pandas as pd, yfinance as yf
DEFAULT_ASX_UNIVERSE=["BHP","CBA","CSL","NAB","WBC","ANZ","WES","MQG","WOW","TLS","GMG","FMG","RIO","TCL","ALL","WDS","QBE","COL","STO","REA","XRO","CPU","S32","NST","ORG","SUN","IAG","COH","RMD","CAR","JHX","BXB","MIN","SHL","FPH","SOL","APA","DMP","SEK","TWE"]
def norm(x):
    x=(x or "").strip().upper(); return f"{x}.AX" if x and "." not in x else x
def code(x): return norm(x).replace(".AX","")
def _flat(df):
    if isinstance(df.columns,pd.MultiIndex): df.columns=df.columns.get_level_values(0)
    return df.dropna(how="all")
def fetch_intraday(t):
    try: return _flat(yf.download(norm(t),period="1d",interval="1m",auto_adjust=True,progress=False,threads=False))
    except Exception: return pd.DataFrame()
def fetch_daily(t,period="1y"):
    try: return _flat(yf.download(norm(t),period=period,interval="1d",auto_adjust=True,progress=False,threads=False))
    except Exception: return pd.DataFrame()
def latest_price(t):
    for df in [fetch_intraday(t),fetch_daily(t,"5d")]:
        if not df.empty and "Close" in df:
            s=df["Close"].dropna()
            if not s.empty: return float(s.iloc[-1])
    return None
def market_cap(t):
    try:
        fi=yf.Ticker(norm(t)).fast_info; val=None
        if hasattr(fi,"market_cap"): val=fi.market_cap
        if val is None and hasattr(fi,"get"): val=fi.get("market_cap") or fi.get("marketCap")
        if val: return float(val)
    except Exception: pass
    try:
        val=yf.Ticker(norm(t)).info.get("marketCap"); return float(val) if val else None
    except Exception: return None
def dividends(t,period="5y"):
    try:
        s=yf.Ticker(norm(t)).get_dividends(period=period)
        if s is None or len(s)==0: return pd.DataFrame(columns=["Date","Dividend"])
        df=s.reset_index(); df.columns=["Date","Dividend"]; df["Date"]=pd.to_datetime(df["Date"]).dt.tz_localize(None); return df
    except Exception: return pd.DataFrame(columns=["Date","Dividend"])
def quote(t):
    t=norm(t); i=fetch_intraday(t); d=fetch_daily(t,"5d"); last=prev=hi=lo=vol=None; source="daily fallback"
    if not i.empty:
        source="1m intraday"
        if "Close" in i and not i["Close"].dropna().empty: last=float(i["Close"].dropna().iloc[-1])
        if "High" in i and not i["High"].dropna().empty: hi=float(i["High"].dropna().max())
        if "Low" in i and not i["Low"].dropna().empty: lo=float(i["Low"].dropna().min())
        if "Volume" in i and not i["Volume"].dropna().empty: vol=float(i["Volume"].fillna(0).sum())
    if not d.empty and "Close" in d:
        c=d["Close"].dropna(); prev=float(c.iloc[-2]) if len(c)>=2 else (float(c.iloc[0]) if len(c)==1 else None)
        if last is None and not c.empty: last=float(c.iloc[-1])
    chg=pct=None
    if last is not None and prev not in (None,0): chg=last-prev; pct=chg/prev*100
    return {"Ticker":t,"Code":code(t),"Last price":last,"Previous close":prev,"Day change":chg,"Day change %":pct,"High":hi,"Low":lo,"Volume":vol,"Source":source,"Updated":datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
def indicators(df,fast=20,slow=50,long=200,rsi_period=14,atr_period=14):
    df=df.copy()
    if df.empty or "Close" not in df: return df
    c=df["Close"]; h=df["High"] if "High" in df else c; l=df["Low"] if "Low" in df else c; v=df["Volume"] if "Volume" in df else pd.Series(np.nan,index=df.index)
    for n in [int(fast),int(slow),int(long)]: df[f"EMA{n}"]=c.ewm(span=n,adjust=False).mean()
    delta=c.diff(); gain=delta.clip(lower=0).rolling(int(rsi_period)).mean(); loss=(-delta.clip(upper=0)).rolling(int(rsi_period)).mean(); rs=gain/loss.replace(0,np.nan); df["RSI"]=100-(100/(1+rs))
    ema12=c.ewm(span=12,adjust=False).mean(); ema26=c.ewm(span=26,adjust=False).mean(); df["MACD"]=ema12-ema26; df["MACD_signal"]=df["MACD"].ewm(span=9,adjust=False).mean(); df["MACD_hist"]=df["MACD"]-df["MACD_signal"]
    tr=pd.concat([(h-l),(h-c.shift(1)).abs(),(l-c.shift(1)).abs()],axis=1).max(axis=1); df["ATR"]=tr.rolling(int(atr_period)).mean(); df["ATR_pct"]=df["ATR"]/c*100
    return df
def _slope(s,lb):
    s=s.dropna(); lb=int(lb); return None if len(s)<=lb or s.iloc[-lb-1]==0 else float((s.iloc[-1]-s.iloc[-lb-1])/s.iloc[-lb-1]*100)
def _days_above(a,b):
    days=0
    for v in reversed((a>b).fillna(False).tolist()):
        if v: days+=1
        else: break
    return days
def _inc_days(s,lb):
    d=s.dropna().tail(int(lb)+1).diff().dropna(); return int((d>0).sum()) if len(d) else 0
def _crossed_up(a,b,lookback):
    x=(a>b).tail(int(lookback)+1)
    return bool(((x.shift(1)==False)&(x==True)).any()) if len(x)>=2 else False
def _days_since_cross(a,b,max_lookback=80):
    cond=(a>b).fillna(False).tail(max_lookback).tolist(); days=0
    for v in reversed(cond):
        if v: days+=1
        else: break
    return days
def _higher_highs_lows(df,lookback=10):
    if len(df)<lookback+2: return False, False
    recent=df.tail(lookback)
    prior=df.iloc[-lookback*2:-lookback] if len(df)>=lookback*2 else df.iloc[:-lookback]
    if prior.empty: return False, False
    hh=recent["High"].max()>prior["High"].max(); hl=recent["Low"].min()>prior["Low"].min()
    return bool(hh), bool(hl)
def _upday_volume_ratio(df,lookback=20):
    recent=df.tail(int(lookback)).copy()
    recent["UpDay"]=recent["Close"]>recent["Close"].shift(1)
    up=recent[recent["UpDay"]]["Volume"].mean(); allv=recent["Volume"].mean()
    return float(up/allv) if allv and not pd.isna(up) else None
def _resistance_break(df,lookback=60):
    if len(df)<lookback+2: return False, None
    prior_high=float(df["High"].iloc[-lookback-1:-1].max()); close=float(df["Close"].iloc[-1])
    return close>prior_high, prior_high
def stage2_scan_one(t,cfg):
    t=norm(t); fast=int(cfg.get("fast_ema",20)); slow=int(cfg.get("slow_ema",50)); long=int(cfg.get("long_ema",200)); df=fetch_daily(t,"1y")
    if df.empty or len(df)<max(60,long): return {"Code":code(t),"Stage":"No Data","Confidence":0,"Reason":"Not enough data"}
    df=indicators(df,fast,slow,long); x=df.iloc[-1]; close=float(x["Close"]); f=f"EMA{fast}"; s=f"EMA{slow}"; l=f"EMA{long}"
    fast_slope=_slope(df[f],5); slow_slope=_slope(df[s],10); fast_up=fast_slope is not None and fast_slope>0; slow_flat_or_up=slow_slope is not None and slow_slope>=-0.15; slow_decline=slow_slope is not None and slow_slope<0
    macd_cross=_crossed_up(df["MACD"],df["MACD_signal"],10); macd_above_signal=bool(x["MACD"]>x["MACD_signal"]); macd_toward_zero=bool(x["MACD"]>-0.25 or x["MACD"]>df["MACD"].iloc[-5]); macd_above_zero=bool(x["MACD"]>0); hist_inc=_inc_days(df["MACD_hist"],3)>=2
    above20=bool(close>x[f]); above50=bool(close>x[s]); ema_order=bool(x[f]>x[s]>x[l]); cross_days=_days_since_cross(df[f],df[s],80); fresh_cross=int(cfg.get("ema_cross_min_days",5))<=cross_days<=int(cfg.get("ema_cross_max_days",15))
    hh,hl=_higher_highs_lows(df,int(cfg.get("higher_high_low_lookback",10))); upvol=_upday_volume_ratio(df,20); upvol_ok=upvol is not None and upvol>=1.05
    avgvol=float(df["Volume"].tail(20).mean()); lastvol=float(df["Volume"].iloc[-1]); vol_ratio=lastvol/avgvol if avgvol else None; strong_vol=vol_ratio is not None and vol_ratio>=float(cfg.get("volume_expansion_multiplier",1.5))
    breakout,resistance=_resistance_break(df,int(cfg.get("resistance_lookback",60))); dist20=(close-float(x[f]))/float(x[f])*100 if x[f] else None; not_extended=dist20 is not None and dist20<=float(cfg.get("max_distance_above_fast_pct",8.0))
    rsi=float(x["RSI"]); avgturn=avgvol*close; cap=market_cap(t) if cfg.get("check_market_cap",False) else None
    liquidity_ok=(avgvol>=float(cfg.get("min_avg_volume",0))) and (avgturn>=float(cfg.get("min_avg_turnover",0))) and (close>=float(cfg.get("min_price",0))) and (float(cfg.get("max_price",0))==0 or close<=float(cfg.get("max_price",0)))
    if cfg.get("check_market_cap",False):
        liquidity_ok=liquidity_ok and cap is not None and cap>=float(cfg.get("min_market_cap",0)) and (float(cfg.get("max_market_cap",0))==0 or cap<=float(cfg.get("max_market_cap",0)))
    stage_a_score=sum([fast_up, macd_cross, slow_decline or slow_flat_or_up, hl, upvol_ok])*20
    stage_b_score=sum([above20, above50, fresh_cross, fast_up, slow_flat_or_up, macd_above_signal and macd_toward_zero, 52<=rsi<=68, hh and hl])*12.5
    stage_c_score=sum([breakout, strong_vol, ema_order, macd_above_zero and hist_inc, close>x[f] and close>x[s], not_extended])*16.67
    if stage_b_score>=70 and liquidity_ok:
        stage="Stage B - Emerging Trend"; action="Primary Buy Zone"; confidence=round(stage_b_score,1)
    elif stage_a_score>=60 and liquidity_ok:
        stage="Stage A - Early Turnaround"; action="Watchlist Only"; confidence=round(stage_a_score,1)
    elif stage_c_score>=70 and liquidity_ok:
        stage="Stage C - Confirmed Stage 2"; action="Buy only if not extended"; confidence=round(stage_c_score,1)
    else:
        stage="No Clear Stage"; action="Ignore / Monitor"; confidence=round(max(stage_a_score,stage_b_score,stage_c_score),1)
    reasons=[]
    for name,val in [("20 EMA curling/rising",fast_up),("MACD bullish/crossed or above signal",macd_cross or macd_above_signal),("50 EMA flat/rising",slow_flat_or_up),("Higher highs",hh),("Higher lows",hl),("Price above 20 EMA",above20),("Price above 50 EMA",above50),("Fresh 20/50 EMA cross",fresh_cross),("Strong volume",strong_vol),("Breakout",breakout),("Not extended above 20 EMA",not_extended),("Liquidity filters",liquidity_ok)]:
        if val: reasons.append(name)
    warnings=[]
    if dist20 is not None and not not_extended: warnings.append(f"Extended {dist20:.1f}% above 20 EMA")
    if not strong_vol: warnings.append("No 1.5x volume expansion")
    if not liquidity_ok: warnings.append("Liquidity/value filter issue")
    return {"Code":code(t),"Ticker":t,"Stage":stage,"Action":action,"Confidence":confidence,"Stage A Score":round(stage_a_score,1),"Stage B Score":round(stage_b_score,1),"Stage C Score":round(stage_c_score,1),"Close":close,"RSI":round(rsi,1),"20 EMA Rising":fast_up,"50 EMA Flat/Rising":slow_flat_or_up,"20>50 Days":cross_days,"Fresh Cross":fresh_cross,"Higher Highs":hh,"Higher Lows":hl,"MACD Above Signal":macd_above_signal,"MACD Above Zero":macd_above_zero,"MACD Hist Increasing":hist_inc,"Volume Ratio":round(vol_ratio,2) if vol_ratio else None,"Distance Above 20 EMA %":round(dist20,2) if dist20 is not None else None,"Breakout":breakout,"Resistance Proxy":resistance,"Market cap":cap,"Reason":", ".join(reasons),"Warnings":"; ".join(warnings)}
def rank_stage_results(df):
    if df is None or df.empty: return df
    stage_order={"Stage B - Emerging Trend":0,"Stage A - Early Turnaround":1,"Stage C - Confirmed Stage 2":2,"No Clear Stage":3,"No Data":4}
    df=df.copy(); df["StageRank"]=df["Stage"].map(stage_order).fillna(9); df=df.sort_values(["StageRank","Confidence"],ascending=[True,False]).reset_index(drop=True); df["Rank"]=range(1,len(df)+1); pref=["Rank","Code","Stage","Action","Confidence","Stage A Score","Stage B Score","Stage C Score","Close","RSI","20 EMA Rising","50 EMA Flat/Rising","20>50 Days","Fresh Cross","Higher Highs","Higher Lows","Volume Ratio","Distance Above 20 EMA %","Breakout","Reason","Warnings"]
    return df[[c for c in pref if c in df.columns]+[c for c in df.columns if c not in pref and c!="StageRank"]]
def positions(trades):
    pos={}; rows=trades.to_dict("records") if isinstance(trades,pd.DataFrame) else trades or []
    for r in sorted(rows,key=lambda x:(str(x.get("trade_time","")),int(float(x.get("id",0) or 0)))):
        side=r.get("side")
        if side=="CASH": continue
        t=norm(r.get("ticker")); qty=int(float(r.get("quantity",0) or 0)); price=float(r.get("price",0) or 0); br=float(r.get("brokerage",0) or 0); p=pos.setdefault(t,{"quantity":0,"cost_base":0.0,"realised_pl":0.0})
        if side=="BUY": p["quantity"]+=qty; p["cost_base"]+=qty*price+br
        elif side=="SELL" and p["quantity"]>0:
            sell=min(qty,p["quantity"]); avg=p["cost_base"]/p["quantity"]; cb=avg*sell; proceeds=sell*price-br; p["quantity"]-=sell; p["cost_base"]-=cb; p["realised_pl"]+=proceeds-cb
    return pos
def cash_balance(settings,trades):
    cash=float(settings.get("starting_cash",100000)); rows=trades.to_dict("records") if isinstance(trades,pd.DataFrame) else trades or []
    for r in rows:
        side=r.get("side"); gross=int(float(r.get("quantity",0) or 0))*float(r.get("price",0) or 0); br=float(r.get("brokerage",0) or 0)
        if side=="BUY": cash-=gross+br
        elif side=="SELL": cash+=gross-br
        elif side=="CASH": cash+=gross
    return cash
def portfolio_df(trades):
    rows=[]
    for t,p in positions(trades).items():
        qty=int(p["quantity"])
        if qty<=0: continue
        lp=latest_price(t); mv=qty*lp if lp is not None else None; avg=p["cost_base"]/qty if qty else None; un=mv-p["cost_base"] if mv is not None else None
        rows.append({"Ticker":t,"Code":code(t),"Quantity":qty,"Average cost":avg,"Cost base":p["cost_base"],"Last price":lp,"Market value":mv,"Unrealised P/L":un,"Unrealised P/L %":un/p["cost_base"]*100 if un is not None and p["cost_base"] else None,"Realised P/L":p["realised_pl"]})
    return pd.DataFrame(rows)
