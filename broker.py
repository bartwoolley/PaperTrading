from datetime import datetime
import numpy as np
import pandas as pd
import yfinance as yf

DEFAULT_ASX_UNIVERSE = [
    "BHP", "CBA", "CSL", "NAB", "WBC", "ANZ", "WES", "MQG", "WOW", "TLS",
    "GMG", "FMG", "RIO", "TCL", "ALL", "WDS", "QBE", "COL", "STO", "REA",
    "XRO", "CPU", "S32", "NST", "ORG", "SUN", "IAG", "COH", "RMD", "CAR",
    "JHX", "BXB", "MIN", "SHL", "FPH", "SOL", "APA", "DMP", "SEK", "TWE"
]

def norm(code):
    code=(code or "").strip().upper()
    if not code:
        return ""
    if "." not in code:
        code += ".AX"
    return code

def code(ticker):
    return norm(ticker).replace(".AX", "")

def _flat(df):
    if isinstance(df.columns, pd.MultiIndex):
        df.columns=df.columns.get_level_values(0)
    return df.dropna(how="all")

@pd.api.extensions.register_dataframe_accessor("asxclean")
class _Cleaner:
    def __init__(self, pandas_obj): self._obj=pandas_obj

@pd.api.extensions.register_series_accessor("asxclean")
class _SCleaner:
    def __init__(self, pandas_obj): self._obj=pandas_obj

def fetch_intraday(ticker):
    try:
        return _flat(yf.download(norm(ticker), period="1d", interval="1m", auto_adjust=True, progress=False, threads=False))
    except Exception:
        return pd.DataFrame()

def fetch_daily(ticker, period="1y"):
    try:
        return _flat(yf.download(norm(ticker), period=period, interval="1d", auto_adjust=True, progress=False, threads=False))
    except Exception:
        return pd.DataFrame()

def latest_price(ticker):
    df=fetch_intraday(ticker)
    if not df.empty and "Close" in df:
        s=df["Close"].dropna()
        if not s.empty: return float(s.iloc[-1])
    df=fetch_daily(ticker,"5d")
    if not df.empty and "Close" in df:
        s=df["Close"].dropna()
        if not s.empty: return float(s.iloc[-1])
    return None

def quote(ticker):
    t=norm(ticker); df1=fetch_intraday(t); dfd=fetch_daily(t,"5d")
    last=prev=hi=lo=vol=None
    src="daily fallback"
    if not df1.empty:
        src="1m intraday"
        if "Close" in df1 and not df1["Close"].dropna().empty: last=float(df1["Close"].dropna().iloc[-1])
        if "High" in df1 and not df1["High"].dropna().empty: hi=float(df1["High"].dropna().max())
        if "Low" in df1 and not df1["Low"].dropna().empty: lo=float(df1["Low"].dropna().min())
        if "Volume" in df1 and not df1["Volume"].dropna().empty: vol=float(df1["Volume"].fillna(0).sum())
    if not dfd.empty and "Close" in dfd:
        cs=dfd["Close"].dropna()
        if len(cs)>=2: prev=float(cs.iloc[-2])
        elif len(cs)==1: prev=float(cs.iloc[0])
        if last is None and not cs.empty: last=float(cs.iloc[-1])
    chg=pct=None
    if last is not None and prev not in (None,0):
        chg=last-prev; pct=chg/prev*100
    return {"Ticker":t,"Code":code(t),"Last price":last,"Previous close":prev,"Day change":chg,"Day change %":pct,"High":hi,"Low":lo,"Volume":vol,"Source":src,"Updated":datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

def indicators(df, fast=20, slow=50, long=200, rsi_period=14, atr_period=14):
    df=df.copy()
    if df.empty or "Close" not in df: return df
    c=df["Close"]; h=df["High"] if "High" in df else c; l=df["Low"] if "Low" in df else c
    v=df["Volume"] if "Volume" in df else pd.Series(np.nan,index=df.index)
    for n in [int(fast),int(slow),int(long)]: df[f"EMA{n}"]=c.ewm(span=n, adjust=False).mean()
    delta=c.diff(); gain=delta.clip(lower=0).rolling(int(rsi_period)).mean(); loss=(-delta.clip(upper=0)).rolling(int(rsi_period)).mean()
    rs=gain/loss.replace(0,np.nan); df["RSI"]=100-(100/(1+rs))
    ema12=c.ewm(span=12,adjust=False).mean(); ema26=c.ewm(span=26,adjust=False).mean()
    df["MACD"]=ema12-ema26; df["MACD_signal"]=df["MACD"].ewm(span=9,adjust=False).mean(); df["MACD_hist"]=df["MACD"]-df["MACD_signal"]
    df["BB_mid"]=c.rolling(20).mean(); std=c.rolling(20).std(); df["BB_upper"]=df["BB_mid"]+2*std; df["BB_lower"]=df["BB_mid"]-2*std
    tp=(h+l+c)/3; df["VWAP"]=(tp*v.fillna(0)).cumsum()/v.fillna(0).replace(0,np.nan).cumsum()
    tr=pd.concat([(h-l),(h-c.shift(1)).abs(),(l-c.shift(1)).abs()],axis=1).max(axis=1)
    df["ATR"]=tr.rolling(int(atr_period)).mean(); df["ATR_pct"]=df["ATR"]/c*100
    return df

def scan_one(ticker,cfg):
    t=norm(ticker); df=fetch_daily(t,"1y")
    fast=int(cfg.get("fast_ema",20)); slow=int(cfg.get("slow_ema",50)); long=int(cfg.get("long_ema",200))
    if df.empty or len(df)<max(60,long):
        return {"Ticker":t,"Code":code(t),"Score":0,"Match":False,"Reason":"Not enough data"}
    df=indicators(df,fast,slow,long)
    x=df.iloc[-1]; close=float(x["Close"]); f=f"EMA{fast}"; s=f"EMA{slow}"; l=f"EMA{long}"
    look=int(cfg.get("crossover_lookback",20)); pf=df[f].iloc[-look-1:-1]; ps=df[s].iloc[-look-1:-1]
    cross=bool(((pf.shift(1)<=ps.shift(1))&(pf>ps)).any()) if len(pf)>1 else False
    avgvol=float(df["Volume"].tail(20).mean()) if "Volume" in df else None; avgturn=avgvol*close if avgvol else None
    checks=[]
    def add(name, ok, active=True):
        if active: checks.append((name,bool(ok)))
    add("Price above fast EMA", close>x[f], cfg.get("require_price_above_fast",True))
    add("Price above slow EMA", close>x[s], cfg.get("require_price_above_slow",True))
    add("Price above long EMA", close>x[l], cfg.get("require_price_above_long",False))
    add("Recent EMA cross", cross, cfg.get("require_recent_cross",True))
    add("MACD above signal", x["MACD"]>x["MACD_signal"], cfg.get("require_macd_above_signal",True))
    add("MACD above zero", x["MACD"]>0, cfg.get("require_macd_above_zero",True))
    add("RSI range", float(cfg.get("rsi_min",50))<=x["RSI"]<=float(cfg.get("rsi_max",70)), True)
    add("Minimum price", close>=float(cfg.get("min_price",0)), float(cfg.get("min_price",0))>0)
    add("Maximum price", close<=float(cfg.get("max_price",0)), float(cfg.get("max_price",0))>0)
    add("Minimum average volume", avgvol and avgvol>=float(cfg.get("min_avg_volume",0)), float(cfg.get("min_avg_volume",0))>0)
    add("Minimum average turnover", avgturn and avgturn>=float(cfg.get("min_avg_turnover",0)), float(cfg.get("min_avg_turnover",0))>0)
    add("Maximum ATR %", x["ATR_pct"]<=float(cfg.get("max_atr_pct",0)), float(cfg.get("max_atr_pct",0))>0)
    nh=int(cfg.get("new_high_lookback",0))
    if nh>0: add(f"New {nh}-day high", close>=float(df["Close"].tail(nh).max()), True)
    passed=sum(1 for _,ok in checks if ok); total=len(checks); score=round(passed/total*100,1) if total else 0
    failed=[n for n,ok in checks if not ok]
    return {"Ticker":t,"Code":code(t),"Last close":close,f:float(x[f]),s:float(x[s]),l:float(x[l]),"RSI":float(x["RSI"]),"MACD":float(x["MACD"]),"ATR %":float(x["ATR_pct"]) if not pd.isna(x["ATR_pct"]) else None,"Avg volume 20D":avgvol,"Avg turnover 20D":avgturn,"Recent EMA cross":cross,"Score":score,"Match":passed==total,"Reason":"Matched all active rules" if passed==total else "; ".join(failed[:6])}

def positions(trades):
    pos={}; realised_total=0
    for r in sorted(trades,key=lambda x:(x.get("trade_time",""),x.get("id",0))):
        side=r.get("side");
        if side=="CASH": continue
        t=norm(r.get("ticker")); qty=int(r.get("quantity",0)); price=float(r.get("price",0)); br=float(r.get("brokerage",0))
        p=pos.setdefault(t,{"quantity":0,"cost_base":0.0,"realised_pl":0.0})
        if side=="BUY": p["quantity"]+=qty; p["cost_base"]+=qty*price+br
        elif side=="SELL" and p["quantity"]>0:
            avg=p["cost_base"]/p["quantity"]; cb=avg*qty; proceeds=qty*price-br
            p["quantity"]-=qty; p["cost_base"]-=cb; p["realised_pl"]+=proceeds-cb; realised_total+=proceeds-cb
    return pos

def cash_balance(state):
    cash=float(state.get("starting_cash",100000))
    for r in state.get("trades",[]):
        side=r.get("side"); qty=int(r.get("quantity",0)); price=float(r.get("price",0)); br=float(r.get("brokerage",0))
        gross=qty*price
        if side=="BUY": cash-=gross+br
        elif side=="SELL": cash+=gross-br
        elif side=="CASH": cash+=gross
    return cash

def portfolio_df(state):
    rows=[]
    for t,p in positions(state.get("trades",[])).items():
        qty=int(p["quantity"])
        if qty<=0: continue
        lp=latest_price(t); mv=qty*lp if lp is not None else None; avg=p["cost_base"]/qty if qty else None; un=mv-p["cost_base"] if mv is not None else None
        rows.append({"Ticker":t,"Code":code(t),"Quantity":qty,"Average cost":avg,"Cost base":p["cost_base"],"Last price":lp,"Market value":mv,"Unrealised P/L":un,"Unrealised P/L %":un/p["cost_base"]*100 if un is not None and p["cost_base"] else None,"Realised P/L":p["realised_pl"]})
    return pd.DataFrame(rows)
