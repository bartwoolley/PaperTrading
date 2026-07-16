import json
from datetime import datetime
import pandas as pd
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

SHEET_ID = st.secrets.get("GOOGLE_SHEET_ID", "1RnsybqzaXyALESQ7Gkim92Nub2cc1O6ip1H3jeN41Ck")

TAB_HEADERS = {
    "Settings": ["key", "value"],
    "Trades": ["id", "trade_time", "side", "ticker", "quantity", "price", "brokerage", "notes"],
    "Watchlists": ["watchlist", "ticker"],
    "Journal": ["id", "time", "ticker", "setup", "reason", "risk", "lesson"],
    "ScannerPresets": ["preset", "config_json"],
    "ManualScores": ["ticker", "manual_stage", "chart_structure", "volume_quality", "distance_quality", "resistance_overhead", "catalyst_score", "manual_confidence", "notes", "updated"],
}

DEFAULT_PRESET = {
    "fast_ema": 20,
    "slow_ema": 50,
    "long_ema": 200,
    "rsi_min_b": 52.0,
    "rsi_max_b": 68.0,
    "ema_cross_min_days": 5,
    "ema_cross_max_days": 15,
    "volume_expansion_multiplier": 1.5,
    "max_distance_above_fast_pct": 8.0,
    "max_distance_above_slow_pct": 15.0,
    "resistance_lookback": 60,
    "higher_high_low_lookback": 10,
    "min_avg_volume": 0,
    "min_avg_turnover": 0.0,
    "min_price": 0.0,
    "max_price": 0.0,
    "max_atr_pct": 0.0,
    "check_market_cap": False,
    "min_market_cap": 0.0,
    "max_market_cap": 0.0,
    "require_rising_fast_ema": True,
    "require_rising_slow_ema": False,
    "fast_ema_slope_lookback": 5,
    "slow_ema_slope_lookback": 10,
    "min_fast_ema_slope_pct": 0.0,
    "min_slow_ema_slope_pct": 0.0,
    "require_macd_above_signal": True,
    "require_macd_above_zero": False,
    "require_macd_hist_increasing": True,
    "macd_hist_lookback": 3,
    "min_macd_hist_increase_days": 2,
    "require_macd_zero_cross_recent": False,
    "macd_zero_cross_lookback": 10,
    "require_volume_expansion": False,
    "require_not_extended": True,
}


def now():
    return datetime.now().isoformat(timespec="seconds")


def clear_cache():
    """Clear local Streamlit caches after writes or when user forces a refresh."""
    for fn in [worksheet_map, read_tab_cached, ensure_schema_cached]:
        try:
            fn.clear()
        except Exception:
            pass


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


@st.cache_resource(show_spinner=False)
def worksheet_map():
    """One metadata call only. Avoid per-tab fetch_sheet_metadata calls."""
    return {w.title: w for w in spreadsheet().worksheets()}


def ws(name):
    mapping = worksheet_map()
    if name in mapping:
        return mapping[name]
    # Missing tab: create once, then refresh the worksheet map.
    w = spreadsheet().add_worksheet(title=name, rows=1000, cols=max(10, len(TAB_HEADERS[name]) + 2))
    w.update("A1", [TAB_HEADERS[name]])
    clear_cache()
    return w


@st.cache_data(ttl=180, show_spinner=False)
def read_tab_cached(name):
    return ws(name).get_all_records()


def read_tab(name):
    rows = read_tab_cached(name)
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
    clear_cache()


def read_settings(): return read_tab("Settings")


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


def write_trades(df): write_tab("Trades", df)


def next_id(df):
    return 1 if df is None or df.empty or "id" not in df.columns else int(pd.to_numeric(df["id"], errors="coerce").fillna(0).max()) + 1


def read_watchlists(): return read_tab("Watchlists")
def write_watchlists(df): write_tab("Watchlists", df)


def watchlist_names():
    df = read_watchlists()
    names = [x for x in df["watchlist"].dropna().unique().tolist() if str(x)] if not df.empty else []
    return names or ["Momentum"]


def tickers_for(name):
    df = read_watchlists()
    return [] if df.empty else [x for x in df[df["watchlist"] == name]["ticker"].dropna().tolist() if str(x)]


def read_journal(): return read_tab("Journal")
def write_journal(df): write_tab("Journal", df)
def read_presets(): return read_tab("ScannerPresets")
def write_presets(df): write_tab("ScannerPresets", df)


def presets_dict():
    df = read_presets()
    out = {}
    for _, r in df.iterrows():
        try:
            if str(r.get("preset", "")):
                out[str(r["preset"])] = json.loads(r["config_json"])
        except Exception:
            pass
    if not out:
        out["Stage 2 Breakout v3 - Advanced"] = DEFAULT_PRESET
    for k in list(out.keys()):
        merged = dict(DEFAULT_PRESET)
        merged.update(out[k])
        out[k] = merged
    return out


def save_preset(name, cfg):
    presets = presets_dict()
    presets[name] = cfg
    write_presets(pd.DataFrame([{"preset": k, "config_json": json.dumps(v)} for k, v in presets.items()]))


def read_manual_scores(): return read_tab("ManualScores")
def write_manual_scores(df): write_tab("ManualScores", df)


@st.cache_data(ttl=3600, show_spinner=False)
def ensure_schema_cached():
    existing = set(worksheet_map().keys())
    missing = [name for name in TAB_HEADERS if name not in existing]
    if missing:
        for name in missing:
            w = spreadsheet().add_worksheet(title=name, rows=1000, cols=max(10, len(TAB_HEADERS[name]) + 2))
            w.update("A1", [TAB_HEADERS[name]])
        clear_cache()
    return True


def ensure_schema():
    # Only checks tab existence. Does not repeatedly call spreadsheet().worksheet(name).
    ensure_schema_cached()

    # Seed only when the tab is genuinely empty. These reads are cached.
    if read_settings().empty:
        write_settings({"starting_cash": 100000.0})
    if read_presets().empty:
        write_presets(pd.DataFrame([{"preset": "Stage 2 Breakout v3 - Advanced", "config_json": json.dumps(DEFAULT_PRESET)}]))
    if read_watchlists().empty:
        write_watchlists(pd.DataFrame([
            {"watchlist": "Momentum", "ticker": "CBA.AX"},
            {"watchlist": "Momentum", "ticker": "BHP.AX"},
            {"watchlist": "Momentum", "ticker": "WES.AX"},
        ]))
    # ManualScores is optional and only created as a sheet. Do not read/write unless page is opened.
