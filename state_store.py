import json
import os
from datetime import datetime
from copy import deepcopy

STATE_FILE = "asx_v4_state.json"

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

def now():
    return datetime.now().isoformat(timespec="seconds")

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data=json.load(f)
            merged=deepcopy(DEFAULT_STATE)
            merged.update(data)
            for k,v in DEFAULT_STATE.items():
                if isinstance(v, dict):
                    merged.setdefault(k, {})
            return merged
        except Exception:
            return deepcopy(DEFAULT_STATE)
    return deepcopy(DEFAULT_STATE)

def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)

def next_id(items):
    return max([int(x.get("id",0)) for x in items], default=0) + 1
