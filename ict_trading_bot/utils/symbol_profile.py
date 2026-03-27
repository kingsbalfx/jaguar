import os
from typing import Dict, List


FX_CODES = {
    "AUD",
    "BRL",
    "CAD",
    "CHF",
    "DKK",
    "EUR",
    "GBP",
    "HKD",
    "JPY",
    "MXN",
    "NOK",
    "NZD",
    "PLN",
    "SEK",
    "SGD",
    "THB",
    "TRY",
    "USD",
    "ZAR",
    "ZWL",
}

LIQUID_FOREX = [
    "EURUSD",
    "GBPUSD",
    "USDJPY",
    "AUDUSD",
    "NZDUSD",
    "USDCAD",
    "USDCHF",
    "EURJPY",
    "GBPJPY",
    "EURGBP",
    "EURCHF",
    "GBPCHF",
    "AUDJPY",
    "CADJPY",
]

LIQUID_METALS = [
    "XAUUSD",
    "XAGUSD",
    "XPTUSD",
    "XPDUSD",
]

LIQUID_CRYPTO = [
    "BTCUSD",
    "ETHUSD",
    "SOLUSD",
    "BNBUSD",
    "XRPUSD",
    "DOGEUSD",
    "ADAUSD",
    "LTCUSD",
    "BCHUSD",
    "TRXUSD",
    "TONUSD",
    "AVAXUSD",
]

ASSET_CLASS_EXAMPLES = {
    "forex": "EURUSD",
    "metals": "XAUUSD",
    "crypto": "BTCUSD",
    "other": "SPX500",
}


def normalize_symbol(symbol: str) -> str:
    return str(symbol or "").strip().upper()


def infer_asset_class(symbol: str) -> str:
    normalized = normalize_symbol(symbol)
    if normalized in LIQUID_METALS or normalized.startswith(("XAU", "XAG", "XPT", "XPD")):
        return "metals"
    if normalized in LIQUID_CRYPTO:
        return "crypto"
    if len(normalized) >= 6 and normalized[:3] in FX_CODES and normalized[3:6] in FX_CODES:
        return "forex"
    return "other"


def _float_env(name: str, fallback: float) -> float:
    return float(os.getenv(name, str(fallback)))


def _int_env(name: str, fallback: int) -> int:
    return int(os.getenv(name, str(fallback)))


def get_entry_profile(symbol: str = None) -> Dict[str, float]:
    asset_class = infer_asset_class(symbol)
    defaults = {
        "forex": {
            "fib_buffer_ratio": 0.08,
            "atr_buffer_multiplier": 0.20,
            "recent_candles": 32,
        },
        "metals": {
            "fib_buffer_ratio": 0.10,
            "atr_buffer_multiplier": 0.28,
            "recent_candles": 36,
        },
        "crypto": {
            "fib_buffer_ratio": 0.14,
            "atr_buffer_multiplier": 0.45,
            "recent_candles": 40,
        },
        "other": {
            "fib_buffer_ratio": 0.10,
            "atr_buffer_multiplier": 0.25,
            "recent_candles": 32,
        },
    }
    baseline = defaults.get(asset_class, defaults["other"])
    asset_key = asset_class.upper()
    return {
        "asset_class": asset_class,
        "fib_buffer_ratio": _float_env(
            f"ENTRY_FIB_BUFFER_RATIO_{asset_key}",
            _float_env("ENTRY_FIB_BUFFER_RATIO", baseline["fib_buffer_ratio"]),
        ),
        "atr_buffer_multiplier": _float_env(
            f"ENTRY_ATR_BUFFER_MULTIPLIER_{asset_key}",
            baseline["atr_buffer_multiplier"],
        ),
        "recent_candles": _int_env(
            f"PRICE_ACTION_RECENT_CANDLES_{asset_key}",
            baseline["recent_candles"],
        ),
    }


def get_backtest_thresholds(symbol: str = None) -> Dict[str, float]:
    asset_class = infer_asset_class(symbol)
    defaults = {
        "forex": {
            "min_win_rate": 0.70,
            "min_occurrences": 8,
            "min_profit_factor": 1.20,
            "min_expectancy": 0.0,
            "max_drawdown": 1500.0,
        },
        "metals": {
            "min_win_rate": 0.65,
            "min_occurrences": 6,
            "min_profit_factor": 1.15,
            "min_expectancy": 0.0,
            "max_drawdown": 1800.0,
        },
        "crypto": {
            "min_win_rate": 0.60,
            "min_occurrences": 4,
            "min_profit_factor": 1.10,
            "min_expectancy": 0.0,
            "max_drawdown": 2500.0,
        },
        "other": {
            "min_win_rate": 0.60,
            "min_occurrences": 5,
            "min_profit_factor": 1.10,
            "min_expectancy": 0.0,
            "max_drawdown": 2000.0,
        },
    }
    baseline = defaults.get(asset_class, defaults["other"])
    asset_key = asset_class.upper()
    return {
        "asset_class": asset_class,
        "min_win_rate": _float_env(
            f"BACKTEST_MIN_WIN_RATE_{asset_key}",
            _float_env("BACKTEST_MIN_WIN_RATE", baseline["min_win_rate"]),
        ),
        "min_occurrences": _int_env(
            f"SETUP_BACKTEST_MIN_OCCURRENCES_{asset_key}",
            _int_env("SETUP_BACKTEST_MIN_OCCURRENCES", baseline["min_occurrences"]),
        ),
        "min_profit_factor": _float_env(
            f"BACKTEST_MIN_PROFIT_FACTOR_{asset_key}",
            _float_env("BACKTEST_MIN_PROFIT_FACTOR", baseline["min_profit_factor"]),
        ),
        "min_expectancy": _float_env(
            f"BACKTEST_MIN_EXPECTANCY_{asset_key}",
            _float_env("BACKTEST_MIN_EXPECTANCY", baseline["min_expectancy"]),
        ),
        "max_drawdown": _float_env(
            f"BACKTEST_MAX_DRAWDOWN_{asset_key}",
            _float_env("BACKTEST_MAX_DRAWDOWN", baseline["max_drawdown"]),
        ),
    }


def get_confirmation_profile(symbol: str = None) -> Dict[str, object]:
    asset_class = infer_asset_class(symbol)
    defaults = {
        "forex": {"min_score": 5.0},
        "metals": {"min_score": 5.0},
        "crypto": {"min_score": 4.0},
        "other": {"min_score": 4.0},
    }
    default_weights = {
        "liquidity_setup": 2.0,
        "bos": 1.0,
        "price_action": 2.0,
        "smt": 1.0,
        "rule_quality": 2.0,
        "ml": 1.0,
        "fundamentals": 1.0,
    }
    baseline = defaults.get(asset_class, defaults["other"])
    asset_key = asset_class.upper()
    weights = {
        key: _float_env(f"CONFIRMATION_WEIGHT_{key.upper()}", value)
        for key, value in default_weights.items()
    }
    return {
        "asset_class": asset_class,
        "min_score": _float_env(
            f"MIN_CONFIRMATION_SCORE_{asset_key}",
            _float_env("MIN_CONFIRMATION_SCORE", baseline["min_score"]),
        ),
        "weights": weights,
    }


def related_symbols(symbol: str) -> List[str]:
    normalized = normalize_symbol(symbol)
    asset_class = infer_asset_class(normalized)
    env_symbols = [
        normalize_symbol(item)
        for item in os.getenv("SYMBOLS", "").split(",")
        if normalize_symbol(item)
    ]

    if asset_class == "forex":
        base_pool = LIQUID_FOREX
        default_limit = 8
    elif asset_class == "metals":
        base_pool = LIQUID_METALS
        default_limit = 4
    elif asset_class == "crypto":
        base_pool = LIQUID_CRYPTO
        default_limit = 8
    else:
        base_pool = [normalized]
        default_limit = 4

    limit = _int_env("SETUP_BACKTEST_MAX_PEER_SYMBOLS", default_limit)
    pool = [normalized]
    pool.extend(item for item in env_symbols if infer_asset_class(item) == asset_class and item != normalized)
    pool.extend(item for item in base_pool if item != normalized)

    unique_symbols = []
    seen = set()
    for item in pool:
        if item and item not in seen:
            seen.add(item)
            unique_symbols.append(item)
    return unique_symbols[: max(1, limit)]


def build_symbol_profile_snapshot() -> Dict[str, object]:
    snapshot = {
        "setup_backtest_max_peer_symbols": _int_env("SETUP_BACKTEST_MAX_PEER_SYMBOLS", 8),
        "setup_backtest_same_symbol_min_score": _int_env("SETUP_BACKTEST_SAME_SYMBOL_MIN_SCORE", 6),
        "setup_backtest_asset_class_min_score": _int_env("SETUP_BACKTEST_ASSET_CLASS_MIN_SCORE", 5),
        "setup_backtest_asset_class_fallback": os.getenv("SETUP_BACKTEST_ASSET_CLASS_FALLBACK", "true").lower() in ("1", "true", "yes"),
        "entry_atr_period": _int_env("ENTRY_ATR_PERIOD", 14),
    }
    for asset_key in ("FOREX", "METALS", "CRYPTO"):
        example_symbol = ASSET_CLASS_EXAMPLES[asset_key.lower()]
        entry_profile = get_entry_profile(example_symbol)
        backtest_thresholds = get_backtest_thresholds(example_symbol)
        confirmation_profile = get_confirmation_profile(example_symbol)
        snapshot[f"entry_fib_buffer_ratio_{asset_key.lower()}"] = _float_env(
            f"ENTRY_FIB_BUFFER_RATIO_{asset_key}",
            entry_profile["fib_buffer_ratio"],
        )
        snapshot[f"entry_atr_buffer_multiplier_{asset_key.lower()}"] = _float_env(
            f"ENTRY_ATR_BUFFER_MULTIPLIER_{asset_key}",
            entry_profile["atr_buffer_multiplier"],
        )
        snapshot[f"price_action_recent_candles_{asset_key.lower()}"] = _int_env(
            f"PRICE_ACTION_RECENT_CANDLES_{asset_key}",
            int(entry_profile["recent_candles"]),
        )
        snapshot[f"backtest_min_win_rate_{asset_key.lower()}"] = _float_env(
            f"BACKTEST_MIN_WIN_RATE_{asset_key}",
            backtest_thresholds["min_win_rate"],
        )
        snapshot[f"setup_backtest_min_occurrences_{asset_key.lower()}"] = _int_env(
            f"SETUP_BACKTEST_MIN_OCCURRENCES_{asset_key}",
            int(backtest_thresholds["min_occurrences"]),
        )
        snapshot[f"backtest_min_profit_factor_{asset_key.lower()}"] = _float_env(
            f"BACKTEST_MIN_PROFIT_FACTOR_{asset_key}",
            backtest_thresholds["min_profit_factor"],
        )
        snapshot[f"backtest_min_expectancy_{asset_key.lower()}"] = _float_env(
            f"BACKTEST_MIN_EXPECTANCY_{asset_key}",
            backtest_thresholds["min_expectancy"],
        )
        snapshot[f"backtest_max_drawdown_{asset_key.lower()}"] = _float_env(
            f"BACKTEST_MAX_DRAWDOWN_{asset_key}",
            backtest_thresholds["max_drawdown"],
        )
        snapshot[f"min_confirmation_score_{asset_key.lower()}"] = _float_env(
            f"MIN_CONFIRMATION_SCORE_{asset_key}",
            confirmation_profile["min_score"],
        )
    for key in ("liquidity_setup", "bos", "price_action", "smt", "rule_quality", "ml", "fundamentals"):
        snapshot[f"confirmation_weight_{key}"] = _float_env(
            f"CONFIRMATION_WEIGHT_{key.upper()}",
            get_confirmation_profile("EURUSD")["weights"][key],
        )
    return snapshot
