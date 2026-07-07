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
        fi=yf.Ticker(norm(t)).fast_info
        val=None
        if hasattr(fi,"market_cap"): val=fi.market_cap
        if val is None and hasattr(fi,"get"): val=fi.get("market_cap") or fi.get("marketCap")
        if val: return float(val)
    except Exception: pass
    try:
        info=yf.Ticker(norm(t)).info
        val=info.get("marketCap")
        return float(val) if val else None
    except Exception: return None
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
    df["BB_mid"]=c.rolling(20).mean(); std=c.rolling(20).std(); df["BB_upper"]=df["BB_mid"]+2*std; df["BB_lower"]=df["BB_mid"]-2*std
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
def scan_one(t,cfg):
    t=norm(t); fast=int(cfg.get("fast_ema",20)); slow=int(cfg.get("slow_ema",50)); long=int(cfg.get("long_ema",200)); df=fetch_daily(t,"1y")
    if df.empty or len(df)<max(60,long): return {"Ticker":t,"Code":code(t),"Rank":None,"Score":0,"Match":False,"Setup Type":"No Data","Reason":"Not enough data"}
    df=indicators(df,fast,slow,long); x=df.iloc[-1]; close=float(x["Close"]); f=f"EMA{fast}"; s=f"EMA{slow}"; l=f"EMA{long}"
    fs=_slope(df[f],cfg.get("fast_ema_slope_lookback",5)); ss=_slope(df[s],cfg.get("slow_ema_slope_lookback",10)); fr=fs is not None and fs>=float(cfg.get("min_fast_ema_slope_pct",0)); sr=ss is not None and ss>=float(cfg.get("min_slow_ema_slope_pct",0))
    days=_days_above(df[f],df[s]); fresh=int(cfg.get("min_fast_above_slow_days",5))<=days<=int(cfg.get("max_fast_above_slow_days",20)); hist_inc=_inc_days(df["MACD_hist"],cfg.get("macd_hist_lookback",3))>=int(cfg.get("min_macd_hist_increase_days",2))
    avgvol=float(df["Volume"].tail(int(cfg.get("volume_avg_period",20))).mean()) if "Volume" in df else None; lastvol=float(df["Volume"].iloc[-1]) if "Volume" in df else None; ratio=(lastvol/avgvol) if avgvol and avgvol>0 and lastvol is not None else None; vol_exp=ratio is not None and ratio>=float(cfg.get("volume_expansion_multiplier",1.5)); avgturn=avgvol*close if avgvol else None
    cap=market_cap(t) if cfg.get("check_market_cap",False) else None
    checks=[]
    def add(n,ok,active=True):
        if active: checks.append((n,bool(ok)))
    add("Price above fast EMA",close>x[f],cfg.get("require_price_above_fast",True)); add("Price above slow EMA",close>x[s],cfg.get("require_price_above_slow",True)); add("Price above long EMA",close>x[l],cfg.get("require_price_above_long",False)); add("Rising fast EMA",fr,cfg.get("require_rising_fast_ema",True)); add("Rising slow EMA",sr,cfg.get("require_rising_slow_ema",False)); add("Fresh EMA alignment",fresh,cfg.get("require_fresh_ema_alignment",True)); add("MACD above signal",x["MACD"]>x["MACD_signal"],cfg.get("require_macd_above_signal",True)); add("MACD hist increasing",hist_inc,cfg.get("require_macd_hist_increasing",True)); add("Volume expansion",vol_exp,cfg.get("require_volume_expansion",True)); add("RSI range",float(cfg.get("rsi_min",50))<=x["RSI"]<=float(cfg.get("rsi_max",70)),True)
    add("Minimum price",close>=float(cfg.get("min_price",0)),float(cfg.get("min_price",0))>0); add("Maximum price",close<=float(cfg.get("max_price",0)),float(cfg.get("max_price",0))>0); add("Minimum avg volume",avgvol and avgvol>=float(cfg.get("min_avg_volume",0)),float(cfg.get("min_avg_volume",0))>0); add("Minimum avg turnover",avgturn and avgturn>=float(cfg.get("min_avg_turnover",0)),float(cfg.get("min_avg_turnover",0))>0); add("Maximum ATR %",x["ATR_pct"]<=float(cfg.get("max_atr_pct",0)),float(cfg.get("max_atr_pct",0))>0)
    add("Minimum market cap",cap is not None and cap>=float(cfg.get("min_market_cap",0)),cfg.get("check_market_cap",False) and float(cfg.get("min_market_cap",0))>0); add("Maximum market cap",cap is not None and cap<=float(cfg.get("max_market_cap",0)),cfg.get("check_market_cap",False) and float(cfg.get("max_market_cap",0))>0)
    passed=sum(1 for _,ok in checks if ok); total=len(checks); rule=round(passed/total*100,1) if total else 0; failed=[n for n,ok in checks if not ok]
    trend=(20 if close>x[f] else 0)+(20 if close>x[s] else 0)+(20 if close>x[l] else 0)+(20 if fr else 0)+(20 if sr else 0); momentum=(25 if x["MACD"]>x["MACD_signal"] else 0)+(25 if x["MACD"]>0 else 0)+(25 if hist_inc else 0)+(25 if float(cfg.get("rsi_min",50))<=x["RSI"]<=float(cfg.get("rsi_max",70)) else 0); volume=100 if vol_exp else (min(100,round((ratio or 0)/float(cfg.get("volume_expansion_multiplier",1.5))*100,1)) if ratio else 0); freshness=(40 if fresh else 0); risk=100 if x["RSI"]<=75 else 70; score=round(trend*.3+momentum*.3+volume*.2+freshness*.1+risk*.1,1)
    setup="Early Bounce" if fr and hist_inc and vol_exp and not sr else ("Fresh Trend" if fresh and fr and sr and vol_exp else ("Momentum Continuation" if days>int(cfg.get("max_fast_above_slow_days",20)) and fr and sr else ("Watch Only" if score>=70 else "Weak / Ignore")))
    return {"Ticker":t,"Code":code(t),"Rank":None,"Setup Type":setup,"Score":score,"Rule Score":rule,"Match":passed==total,"Reason":"Matched all active rules" if passed==total else "; ".join(failed),"Last close":close,"Market cap":cap,"Fast EMA rising":fr,"Slow EMA rising":sr,"Fast EMA > Slow EMA Days":days,"MACD hist increasing":hist_inc,"Volume expansion":vol_exp,"Volume expansion ratio":ratio,"Avg volume":avgvol,"Avg turnover":avgturn,"RSI":float(x["RSI"]),"ATR %":float(x["ATR_pct"]) if not pd.isna(x["ATR_pct"]) else None}
def rank_results(df):
    if df is None or df.empty: return df
    df=df.sort_values(["Score","Rule Score"],ascending=[False,False]).reset_index(drop=True); df["Rank"]=range(1,len(df)+1); pref=["Rank","Code","Setup Type","Score","Rule Score","Match","Last close","Market cap","Fast EMA rising","Slow EMA rising","Fast EMA > Slow EMA Days","MACD hist increasing","Volume expansion","Volume expansion ratio","RSI","Reason"]
    return df[[c for c in pref if c in df.columns]+[c for c in df.columns if c not in pref]]
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
