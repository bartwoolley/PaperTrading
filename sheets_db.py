import json
from datetime import datetime
import pandas as pd
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

SHEET_ID = "1RnsybqzaXyALESQ7Gkim92Nub2cc1O6ip1H3jeN41Ck"

TAB_HEADERS = {
    "Settings": ["key", "value"],
    "Trades": ["id", "trade_time", "side", "ticker", "quantity", "price", "brokerage", "notes"],
    "Watchlists": ["watchlist", "ticker"],
    "Journal": ["id", "time", "ticker", "setup", "reason", "risk", "lesson"],
    "ScannerPresets": ["preset", "config_json"],
}

DEFAULT_PRESET = {
    "fast_ema": 20,
    "slow_ema": 50,
    "long_ema": 200,
    "crossover_lookback": 20,
    "rsi_min": 50.0,
    "rsi_max": 70.0,
    "require_price_above_fast": True,
    "require_price_above_slow": True,
    "require_price_above_long": False,
    "require_recent_cross": False,
    "require_macd_above_signal": True,
    "require_macd_above_zero": False,
    "min_price": 0.0,
    "max_price": 0.0,
    "min_avg_volume": 0,
    "min_avg_turnover": 0.0,
    "max_atr_pct": 0.0,
    "new_high_lookback": 0,
    "require_rising_fast_ema": True,
    "fast_ema_slope_lookback": 5,
    "min_fast_ema_slope_pct": 0.0,
    "require_rising_slow_ema": False,
    "slow_ema_slope_lookback": 10,
    "min_slow_ema_slope_pct": 0.0,
    "require_fresh_ema_alignment": True,
    "min_fast_above_slow_days": 5,
    "max_fast_above_slow_days": 20,
    "require_macd_hist_increasing": True,
    "macd_hist_lookback": 3,
    "min_macd_hist_increase_days": 2,
    "require_macd_hist_above_zero": False,
    "require_macd_hist_crossed_above_zero": False,
    "macd_hist_zero_cross_lookback": 5,
    "require_volume_expansion": True,
    "volume_avg_period": 20,
    "volume_expansion_multiplier": 1.5
}

def now():
    return datetime.now().isoformat(timespec="seconds")

def _credentials():
    info = dict(st.secrets["gcp_service_account"])
    if "private_key" in info:
        info["private_key"] = info["private_key"].replace("\\n", "\n")
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive.file"]
    return Credentials.from_service_account_info(info, scopes=scopes)

@st.cache_resource(show_spinner=False)
def client():
    return gspread.authorize(_credentials())

@st.cache_resource(show_spinner=False)
def spreadsheet():
    return client().open_by_key(SHEET_ID)

def ws(name):
    sh = spreadsheet()
    try:
        w = sh.worksheet(name)
    except gspread.exceptions.WorksheetNotFound:
        w = sh.add_worksheet(title=name, rows=1000, cols=max(10, len(TAB_HEADERS[name]) + 2))
        w.update("A1", [TAB_HEADERS[name]])
    vals = w.get_all_values()
    if not vals:
        w.update("A1", [TAB_HEADERS[name]])
    return w

def read_tab(name):
    w = ws(name)
    rows = w.get_all_records()
    return pd.DataFrame(rows, columns=TAB_HEADERS[name]) if rows else pd.DataFrame(columns=TAB_HEADERS[name])

def write_tab(name, df):
    df = df.copy()
    for c in TAB_HEADERS[name]:
        if c not in df.columns:
            df[c] = ""
    df = df[TAB_HEADERS[name]].fillna("")
    w = ws(name)
    w.clear()
    w.update("A1", [TAB_HEADERS[name]] + df.astype(str).values.tolist())

def read_settings():
    return read_tab("Settings")

def settings_dict():
    df = read_settings()
    out = {}
    for _, r in df.iterrows():
        if str(r.get("key", "")):
            val = r.get("value")
            try:
                val = float(val)
            except Exception:
                pass
            out[str(r.get("key"))] = val
    out.setdefault("starting_cash", 100000.0)
    return out

def write_settings(d):
    write_tab("Settings", pd.DataFrame([{"key": k, "value": v} for k, v in d.items()]))

def read_trades():
    df = read_tab("Trades")
    for c in ["id", "quantity"]:
        if c in df:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)
    for c in ["price", "brokerage"]:
        if c in df:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)
    return df

def write_trades(df):
    write_tab("Trades", df)

def next_id(df):
    if df is None or df.empty or "id" not in df.columns:
        return 1
    return int(pd.to_numeric(df["id"], errors="coerce").fillna(0).max()) + 1

def read_watchlists():
    return read_tab("Watchlists")

def write_watchlists(df):
    write_tab("Watchlists", df)

def watchlist_names():
    df = read_watchlists()
    names = [x for x in df["watchlist"].dropna().unique().tolist() if str(x)] if not df.empty else []
    return names or ["Momentum"]

def tickers_for(name):
    df = read_watchlists()
    if df.empty:
        return []
    return [x for x in df[df["watchlist"] == name]["ticker"].dropna().tolist() if str(x)]

def read_journal():
    return read_tab("Journal")

def write_journal(df):
    write_tab("Journal", df)

def read_presets():
    return read_tab("ScannerPresets")

def write_presets(df):
    write_tab("ScannerPresets", df)

def presets_dict():
    df = read_presets()
    out = {}
    for _, r in df.iterrows():
        try:
            out[str(r["preset"])] = json.loads(r["config_json"])
        except Exception:
            pass
    if not out:
        out["Bart Bounce Momentum"] = DEFAULT_PRESET
    # Backfill new V5.1 fields into old presets
    for k in list(out.keys()):
        merged = dict(DEFAULT_PRESET)
        merged.update(out[k])
        out[k] = merged
    return out

def save_preset(name, cfg):
    presets = presets_dict()
    presets[name] = cfg
    write_presets(pd.DataFrame([{"preset": k, "config_json": json.dumps(v)} for k, v in presets.items()]))

def ensure_schema():
    for name in TAB_HEADERS:
        ws(name)
    if read_settings().empty:
        write_settings({"starting_cash": 100000.0})
    if read_presets().empty:
        write_presets(pd.DataFrame([{"preset": "Bart Bounce Momentum", "config_json": json.dumps(DEFAULT_PRESET)}]))
    if read_watchlists().empty:
        write_watchlists(pd.DataFrame([
            {"watchlist": "Momentum", "ticker": "CBA.AX"},
            {"watchlist": "Momentum", "ticker": "BHP.AX"},
            {"watchlist": "Momentum", "ticker": "WES.AX"},
            {"watchlist": "Research", "ticker": ""},
            {"watchlist": "Paper Trades", "ticker": ""},
        ]))
