from datetime import datetime
import numpy as np
import pandas as pd
import yfinance as yf

DEFAULT_ASX_UNIVERSE = ["BHP", "CBA", "CSL", "NAB", "WBC", "ANZ", "WES", "MQG", "WOW", "TLS", "GMG", "FMG", "RIO", "TCL", "ALL", "WDS", "QBE", "COL", "STO", "REA", "XRO", "CPU", "S32", "NST", "ORG", "SUN", "IAG", "COH", "RMD", "CAR", "JHX", "BXB", "MIN", "SHL", "FPH", "SOL", "APA", "DMP", "SEK", "TWE"]

def norm(x):
    x = (x or "").strip().upper()
    return f"{x}.AX" if x and "." not in x else x

def code(x):
    return norm(x).replace(".AX", "")

def _flat(df):
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df.dropna(how="all")

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
    for df in [fetch_intraday(ticker), fetch_daily(ticker, "5d")]:
        if not df.empty and "Close" in df:
            s = df["Close"].dropna()
            if not s.empty:
                return float(s.iloc[-1])
    return None

def quote(ticker):
    t = norm(ticker); i = fetch_intraday(t); d = fetch_daily(t, "5d")
    last = prev = hi = lo = vol = None; source = "daily fallback"
    if not i.empty:
        source = "1m intraday"
        if "Close" in i and not i["Close"].dropna().empty: last = float(i["Close"].dropna().iloc[-1])
        if "High" in i and not i["High"].dropna().empty: hi = float(i["High"].dropna().max())
        if "Low" in i and not i["Low"].dropna().empty: lo = float(i["Low"].dropna().min())
        if "Volume" in i and not i["Volume"].dropna().empty: vol = float(i["Volume"].fillna(0).sum())
    if not d.empty and "Close" in d:
        c = d["Close"].dropna()
        if len(c) >= 2: prev = float(c.iloc[-2])
        elif len(c) == 1: prev = float(c.iloc[0])
        if last is None and not c.empty: last = float(c.iloc[-1])
    chg = pct = None
    if last is not None and prev not in (None, 0):
        chg = last - prev; pct = chg / prev * 100
    return {"Ticker": t, "Code": code(t), "Last price": last, "Previous close": prev, "Day change": chg, "Day change %": pct, "High": hi, "Low": lo, "Volume": vol, "Source": source, "Updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

def indicators(df, fast=20, slow=50, long=200, rsi_period=14, atr_period=14):
    df = df.copy()
    if df.empty or "Close" not in df:
        return df
    c = df["Close"]
    h = df["High"] if "High" in df else c
    l = df["Low"] if "Low" in df else c
    v = df["Volume"] if "Volume" in df else pd.Series(np.nan, index=df.index)
    for n in [int(fast), int(slow), int(long)]:
        df[f"EMA{n}"] = c.ewm(span=n, adjust=False).mean()
    delta = c.diff()
    gain = delta.clip(lower=0).rolling(int(rsi_period)).mean()
    loss = (-delta.clip(upper=0)).rolling(int(rsi_period)).mean()
    rs = gain / loss.replace(0, np.nan)
    df["RSI"] = 100 - (100 / (1 + rs))
    ema12 = c.ewm(span=12, adjust=False).mean()
    ema26 = c.ewm(span=26, adjust=False).mean()
    df["MACD"] = ema12 - ema26
    df["MACD_signal"] = df["MACD"].ewm(span=9, adjust=False).mean()
    df["MACD_hist"] = df["MACD"] - df["MACD_signal"]
    df["BB_mid"] = c.rolling(20).mean()
    std = c.rolling(20).std()
    df["BB_upper"] = df["BB_mid"] + 2 * std
    df["BB_lower"] = df["BB_mid"] - 2 * std
    tp = (h + l + c) / 3
    df["VWAP"] = (tp * v.fillna(0)).cumsum() / v.fillna(0).replace(0, np.nan).cumsum()
    tr = pd.concat([(h-l), (h-c.shift(1)).abs(), (l-c.shift(1)).abs()], axis=1).max(axis=1)
    df["ATR"] = tr.rolling(int(atr_period)).mean()
    df["ATR_pct"] = df["ATR"] / c * 100
    return df

def _slope_pct(series, lookback):
    lookback = int(lookback)
    s = series.dropna()
    if len(s) <= lookback or s.iloc[-lookback-1] == 0:
        return None
    return float((s.iloc[-1] - s.iloc[-lookback-1]) / s.iloc[-lookback-1] * 100)

def _days_fast_above_slow(fast_series, slow_series):
    cond = (fast_series > slow_series).fillna(False).tolist()
    days = 0
    for value in reversed(cond):
        if value:
            days += 1
        else:
            break
    return days

def _increased_days(series, lookback):
    lookback = int(lookback)
    s = series.dropna().tail(lookback + 1)
    if len(s) < 2:
        return 0
    diffs = s.diff().dropna()
    return int((diffs > 0).sum())

def _crossed_above_zero_recent(series, lookback):
    lookback = int(lookback)
    s = series.dropna().tail(lookback + 1)
    if len(s) < 2:
        return False
    return bool(((s.shift(1) <= 0) & (s > 0)).any())

def scan_one(ticker, cfg):
    t = norm(ticker)
    fast = int(cfg.get("fast_ema", 20)); slow = int(cfg.get("slow_ema", 50)); long = int(cfg.get("long_ema", 200))
    df = fetch_daily(t, "1y")
    min_needed = max(60, long, int(cfg.get("volume_avg_period", 20)) + 2)
    if df.empty or len(df) < min_needed:
        return {"Ticker": t, "Code": code(t), "Rank": None, "Score": 0, "Match": False, "Setup Type": "No Data", "Reason": "Not enough data"}
    df = indicators(df, fast, slow, long)
    x = df.iloc[-1]
    close = float(x["Close"]); f = f"EMA{fast}"; s = f"EMA{slow}"; l = f"EMA{long}"
    look = int(cfg.get("crossover_lookback", 20))
    pf = df[f].iloc[-look-1:-1]; ps = df[s].iloc[-look-1:-1]
    recent_cross = bool(((pf.shift(1) <= ps.shift(1)) & (pf > ps)).any()) if len(pf) > 1 else False
    fast_slope = _slope_pct(df[f], cfg.get("fast_ema_slope_lookback", 5))
    slow_slope = _slope_pct(df[s], cfg.get("slow_ema_slope_lookback", 10))
    fast_rising = fast_slope is not None and fast_slope >= float(cfg.get("min_fast_ema_slope_pct", 0.0))
    slow_rising = slow_slope is not None and slow_slope >= float(cfg.get("min_slow_ema_slope_pct", 0.0))
    fast_above_slow_days = _days_fast_above_slow(df[f], df[s])
    fresh_alignment = int(cfg.get("min_fast_above_slow_days", 5)) <= fast_above_slow_days <= int(cfg.get("max_fast_above_slow_days", 20))
    hist_inc_days = _increased_days(df["MACD_hist"], cfg.get("macd_hist_lookback", 3))
    macd_hist_increasing = hist_inc_days >= int(cfg.get("min_macd_hist_increase_days", 2))
    macd_hist_above_zero = bool(x["MACD_hist"] > 0)
    macd_hist_cross_recent = _crossed_above_zero_recent(df["MACD_hist"], cfg.get("macd_hist_zero_cross_lookback", 5))
    vol_period = int(cfg.get("volume_avg_period", 20))
    avgvol = float(df["Volume"].tail(vol_period).mean()) if "Volume" in df else None
    lastvol = float(df["Volume"].iloc[-1]) if "Volume" in df else None
    avgturn = avgvol * close if avgvol else None
    vol_expansion_ratio = (lastvol / avgvol) if avgvol and avgvol > 0 and lastvol is not None else None
    volume_expansion = vol_expansion_ratio is not None and vol_expansion_ratio >= float(cfg.get("volume_expansion_multiplier", 1.5))
    new_high = None
    nh = int(cfg.get("new_high_lookback", 0))
    if nh > 0:
        new_high = close >= float(df["Close"].tail(nh).max())

    checks = []
    def add(name, ok, active=True):
        if active:
            checks.append((name, bool(ok)))
    add("Price above fast EMA", close > x[f], cfg.get("require_price_above_fast", True))
    add("Price above slow EMA", close > x[s], cfg.get("require_price_above_slow", True))
    add("Price above long EMA", close > x[l], cfg.get("require_price_above_long", False))
    add("Recent EMA cross", recent_cross, cfg.get("require_recent_cross", False))
    add("MACD above signal", x["MACD"] > x["MACD_signal"], cfg.get("require_macd_above_signal", True))
    add("MACD above zero", x["MACD"] > 0, cfg.get("require_macd_above_zero", False))
    add("RSI range", float(cfg.get("rsi_min", 50)) <= x["RSI"] <= float(cfg.get("rsi_max", 70)), True)
    add("Minimum price", close >= float(cfg.get("min_price", 0)), float(cfg.get("min_price", 0)) > 0)
    add("Maximum price", close <= float(cfg.get("max_price", 0)), float(cfg.get("max_price", 0)) > 0)
    add("Minimum average volume", avgvol and avgvol >= float(cfg.get("min_avg_volume", 0)), float(cfg.get("min_avg_volume", 0)) > 0)
    add("Minimum average turnover", avgturn and avgturn >= float(cfg.get("min_avg_turnover", 0)), float(cfg.get("min_avg_turnover", 0)) > 0)
    add("Maximum ATR %", x["ATR_pct"] <= float(cfg.get("max_atr_pct", 0)), float(cfg.get("max_atr_pct", 0)) > 0)
    if nh > 0: add(f"New {nh}-day high", new_high, True)
    add("Rising fast EMA", fast_rising, cfg.get("require_rising_fast_ema", True))
    add("Rising slow EMA", slow_rising, cfg.get("require_rising_slow_ema", False))
    add("Fresh EMA alignment", fresh_alignment, cfg.get("require_fresh_ema_alignment", True))
    add("MACD histogram increasing", macd_hist_increasing, cfg.get("require_macd_hist_increasing", True))
    add("MACD histogram above zero", macd_hist_above_zero, cfg.get("require_macd_hist_above_zero", False))
    add("MACD histogram crossed above zero recently", macd_hist_cross_recent, cfg.get("require_macd_hist_crossed_above_zero", False))
    add("Volume expansion", volume_expansion, cfg.get("require_volume_expansion", True))

    passed = sum(1 for _, ok in checks if ok); total = len(checks)
    rule_score = round(passed / total * 100, 1) if total else 0
    failed = [n for n, ok in checks if not ok]

    trend_score = 0
    trend_score += 20 if close > x[f] else 0
    trend_score += 20 if close > x[s] else 0
    trend_score += 20 if close > x[l] else 0
    trend_score += 20 if fast_rising else 0
    trend_score += 20 if slow_rising else 0
    momentum_score = 0
    momentum_score += 25 if x["MACD"] > x["MACD_signal"] else 0
    momentum_score += 25 if x["MACD"] > 0 else 0
    momentum_score += 25 if macd_hist_increasing else 0
    momentum_score += 25 if float(cfg.get("rsi_min", 50)) <= x["RSI"] <= float(cfg.get("rsi_max", 70)) else 0
    volume_score = 100 if volume_expansion else (min(100, round((vol_expansion_ratio or 0) / float(cfg.get("volume_expansion_multiplier", 1.5)) * 100, 1)) if vol_expansion_ratio else 0)
    freshness_score = 0
    freshness_score += 40 if fresh_alignment else 0
    freshness_score += 30 if recent_cross else 0
    freshness_score += 30 if macd_hist_cross_recent else 0
    risk_score = 100
    if float(cfg.get("max_atr_pct", 0)) > 0 and not (x["ATR_pct"] <= float(cfg.get("max_atr_pct", 0))): risk_score -= 40
    if x["RSI"] > 75: risk_score -= 30
    risk_score = max(0, risk_score)
    weighted_score = round(trend_score*0.30 + momentum_score*0.30 + volume_score*0.20 + freshness_score*0.10 + risk_score*0.10, 1)

    if fast_rising and macd_hist_increasing and volume_expansion and not slow_rising:
        setup_type = "Early Bounce"
    elif fresh_alignment and fast_rising and slow_rising and volume_expansion:
        setup_type = "Fresh Trend"
    elif fast_above_slow_days > int(cfg.get("max_fast_above_slow_days", 20)) and fast_rising and slow_rising:
        setup_type = "Momentum Continuation"
    elif new_high and volume_expansion:
        setup_type = "Breakout"
    elif weighted_score >= 70:
        setup_type = "Watch Only"
    else:
        setup_type = "Weak / Ignore"

    return {
        "Ticker": t,
        "Code": code(t),
        "Rank": None,
        "Setup Type": setup_type,
        "Score": weighted_score,
        "Rule Score": rule_score,
        "Trend Score": trend_score,
        "Momentum Score": momentum_score,
        "Volume Score": volume_score,
        "Freshness Score": freshness_score,
        "Risk Score": risk_score,
        "Match": passed == total,
        "Reason": "Matched all active rules" if passed == total else "; ".join(failed[:8]),
        "Last close": close,
        f"EMA{fast}": float(x[f]),
        f"EMA{slow}": float(x[s]),
        f"EMA{long}": float(x[l]),
        "Fast EMA slope %": fast_slope,
        "Slow EMA slope %": slow_slope,
        "Fast EMA rising": fast_rising,
        "Slow EMA rising": slow_rising,
        "Fast EMA > Slow EMA Days": fast_above_slow_days,
        "Fresh EMA Alignment": fresh_alignment,
        "Recent EMA cross": recent_cross,
        "RSI": float(x["RSI"]),
        "MACD": float(x["MACD"]),
        "MACD signal": float(x["MACD_signal"]),
        "MACD histogram": float(x["MACD_hist"]),
        "MACD hist increasing": macd_hist_increasing,
        "MACD hist increase days": hist_inc_days,
        "MACD hist > 0": macd_hist_above_zero,
        "MACD hist crossed > 0 recent": macd_hist_cross_recent,
        "Volume": lastvol,
        "Avg volume": avgvol,
        "Volume expansion ratio": vol_expansion_ratio,
        "Volume expansion": volume_expansion,
        "Avg turnover": avgturn,
        "ATR %": float(x["ATR_pct"]) if not pd.isna(x["ATR_pct"]) else None,
        "New high": new_high
    }

def rank_results(df):
    if df is None or df.empty or "Score" not in df.columns:
        return df
    df = df.sort_values(["Score", "Rule Score"], ascending=[False, False]).reset_index(drop=True)
    df["Rank"] = range(1, len(df)+1)
    preferred = ["Rank", "Code", "Setup Type", "Score", "Rule Score", "Match", "Last close", "Fast EMA rising", "Slow EMA rising", "Fast EMA > Slow EMA Days", "MACD hist increasing", "Volume expansion", "Volume expansion ratio", "RSI", "Reason"]
    cols = [c for c in preferred if c in df.columns] + [c for c in df.columns if c not in preferred]
    return df[cols]

def positions(trades):
    pos = {}
    rows = trades.to_dict("records") if isinstance(trades, pd.DataFrame) else trades or []
    for r in sorted(rows, key=lambda x: (str(x.get("trade_time", "")), int(float(x.get("id", 0) or 0)))):
        side = r.get("side")
        if side == "CASH": continue
        t = norm(r.get("ticker")); qty = int(float(r.get("quantity", 0) or 0)); price = float(r.get("price", 0) or 0); br = float(r.get("brokerage", 0) or 0)
        p = pos.setdefault(t, {"quantity": 0, "cost_base": 0.0, "realised_pl": 0.0})
        if side == "BUY":
            p["quantity"] += qty; p["cost_base"] += qty * price + br
        elif side == "SELL" and p["quantity"] > 0:
            sell_qty = min(qty, p["quantity"]); avg = p["cost_base"] / p["quantity"]; cb = avg * sell_qty; proceeds = sell_qty * price - br
            p["quantity"] -= sell_qty; p["cost_base"] -= cb; p["realised_pl"] += proceeds - cb
    return pos

def cash_balance(settings, trades):
    cash = float(settings.get("starting_cash", 100000))
    rows = trades.to_dict("records") if isinstance(trades, pd.DataFrame) else trades or []
    for r in rows:
        side = r.get("side"); gross = int(float(r.get("quantity", 0) or 0)) * float(r.get("price", 0) or 0); br = float(r.get("brokerage", 0) or 0)
        if side == "BUY": cash -= gross + br
        elif side == "SELL": cash += gross - br
        elif side == "CASH": cash += gross
    return cash

def portfolio_df(trades):
    rows = []
    for t, p in positions(trades).items():
        qty = int(p["quantity"])
        if qty <= 0: continue
        lp = latest_price(t); mv = qty * lp if lp is not None else None; avg = p["cost_base"] / qty if qty else None; un = mv - p["cost_base"] if mv is not None else None
        rows.append({"Ticker": t, "Code": code(t), "Quantity": qty, "Average cost": avg, "Cost base": p["cost_base"], "Last price": lp, "Market value": mv, "Unrealised P/L": un, "Unrealised P/L %": un / p["cost_base"] * 100 if un is not None and p["cost_base"] else None, "Realised P/L": p["realised_pl"]})
    return pd.DataFrame(rows)
