import json
from datetime import datetime
from copy import deepcopy

import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

DEFAULT_STATE = {
    "starting_cash": 100000.0,
    "watchlists": {
        "Momentum": ["CBA.AX", "BHP.AX", "WES.AX"],
        "Research": [],
        "Paper Trades": []
    },
    "trades": [],
    "journal": [],
    "scanner_presets": {
        "Bart Momentum": {
            "fast_ema": 20,
            "slow_ema": 50,
            "long_ema": 200,
            "crossover_lookback": 20,
            "rsi_min": 50.0,
            "rsi_max": 70.0,
            "require_price_above_fast": True,
            "require_price_above_slow": True,
            "require_price_above_long": False,
            "require_recent_cross": True,
            "require_macd_above_signal": True,
            "require_macd_above_zero": True,
            "min_price": 0.0,
            "max_price": 0.0,
            "min_avg_volume": 0,
            "min_avg_turnover": 0.0,
            "max_atr_pct": 0.0,
            "new_high_lookback": 0
        },
        "Breakout": {
            "fast_ema": 20,
            "slow_ema": 50,
            "long_ema": 200,
            "crossover_lookback": 30,
            "rsi_min": 55.0,
            "rsi_max": 75.0,
            "require_price_above_fast": True,
            "require_price_above_slow": True,
            "require_price_above_long": True,
            "require_recent_cross": False,
            "require_macd_above_signal": True,
            "require_macd_above_zero": True,
            "min_price": 0.0,
            "max_price": 0.0,
            "min_avg_volume": 0,
            "min_avg_turnover": 0.0,
            "max_atr_pct": 0.0,
            "new_high_lookback": 60
        }
    }
}

SHEET_ID = "1RnsybqzaXyALESQ7Gkim92Nub2cc1O6ip1H3jeN41Ck"
STATE_TAB = "State"


def now():
    return datetime.now().isoformat(timespec="seconds")


def _credentials():
    """Build Google service account credentials from Streamlit secrets."""
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive.file",
    ]
    info = dict(st.secrets["gcp_service_account"])
    # Streamlit TOML stores newlines escaped; convert them back for the private key.
    if "private_key" in info:
        info["private_key"] = info["private_key"].replace("\\n", "\n")
    return Credentials.from_service_account_info(info, scopes=scopes)


@st.cache_resource(show_spinner=False)
def _client():
    return gspread.authorize(_credentials())


def _worksheet():
    sh = _client().open_by_key(SHEET_ID)
    try:
        ws = sh.worksheet(STATE_TAB)
    except gspread.exceptions.WorksheetNotFound:
        ws = sh.add_worksheet(title=STATE_TAB, rows=10, cols=2)
        ws.update("A1", [[json.dumps(DEFAULT_STATE)]])
    return ws


def _merge_defaults(data):
    merged = deepcopy(DEFAULT_STATE)
    if isinstance(data, dict):
        merged.update(data)
        for k, v in DEFAULT_STATE.items():
            if isinstance(v, dict):
                merged.setdefault(k, {})
                for kk, vv in v.items():
                    merged[k].setdefault(kk, vv)
    return merged


def load_state():
    try:
        ws = _worksheet()
        raw = ws.acell("A1").value
        if not raw:
            save_state(DEFAULT_STATE)
            return deepcopy(DEFAULT_STATE)
        return _merge_defaults(json.loads(raw))
    except Exception as e:
        st.error("Could not load Google Sheets data. Check Streamlit secrets and Sheet sharing.")
        st.exception(e)
        return deepcopy(DEFAULT_STATE)


def save_state(state):
    ws = _worksheet()
    ws.update("A1", [[json.dumps(state)]])


def next_id(items):
    return max([int(x.get("id", 0)) for x in items], default=0) + 1
