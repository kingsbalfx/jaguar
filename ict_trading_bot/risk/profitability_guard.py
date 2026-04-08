import os
from typing import Any, Dict, Iterable, Tuple

from risk.symbol_stats import load_symbol_stats
from utils.symbol_profile import canonical_symbol, infer_asset_class


def _float_env(name: str, fallback: float) -> float:
    try:
        return float(os.getenv(name, str(fallback)))
    except Exception:
        return fallback


def _int_env(name: str, fallback: int) -> int:
    try:
        return int(float(os.getenv(name, str(fallback))))
    except Exception:
        return fallback


def _asset_float_env(name: str, asset_class: str, fallback: float) -> float:
    asset_key = str(asset_class or "other").upper()
    return _float_env(f"{name}_{asset_key}", _float_env(name, fallback))


def _enabled() -> bool:
    return os.getenv("PROFITABILITY_GUARD_ENABLED", "true").lower() in ("1", "true", "yes", "on")


def _safe_float(value: Any, fallback: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return fallback


def _rr(direction: str, entry: float, sl: float, tp: float) -> Tuple[float, str]:
    side = str(direction or "").lower()
    entry = _safe_float(entry)
    sl = _safe_float(sl)
    tp = _safe_float(tp)

    if entry <= 0 or sl <= 0 or tp <= 0:
        return 0.0, "invalid_price"

    if side == "buy":
        if not sl < entry < tp:
            return 0.0, "invalid_buy_geometry"
        return (tp - entry) / max(entry - sl, 1e-12), "ok"

    if side == "sell":
        if not tp < entry < sl:
            return 0.0, "invalid_sell_geometry"
        return (entry - tp) / max(sl - entry, 1e-12), "ok"

    return 0.0, "invalid_direction"


def normalize_rr_after_sl_adjustment(
    direction: str,
    entry: float,
    sl: float,
    tp: float,
    min_rr: float = None,
):
    """Retarget TP after an intelligent SL change so the real RR stays valid."""
    min_rr = min_rr or _float_env("MIN_RR_RATIO", 2.0)
    current_rr, reason = _rr(direction, entry, sl, tp)
    if current_rr >= min_rr or not _enabled():
        return sl, tp, {
            "rr": round(current_rr, 3),
            "min_rr": min_rr,
            "adjusted_tp": False,
            "reason": reason,
        }

    if os.getenv("PROFITABILITY_GUARD_RETARGET_TP", "true").lower() not in ("1", "true", "yes", "on"):
        return sl, tp, {
            "rr": round(current_rr, 3),
            "min_rr": min_rr,
            "adjusted_tp": False,
            "reason": "tp_retarget_disabled",
        }

    risk = abs(float(entry) - float(sl))
    if str(direction or "").lower() == "buy":
        tp = float(entry) + risk * min_rr
    else:
        tp = float(entry) - risk * min_rr

    next_rr, next_reason = _rr(direction, entry, sl, tp)
    return sl, tp, {
        "rr": round(next_rr, 3),
        "previous_rr": round(current_rr, 3),
        "min_rr": min_rr,
        "adjusted_tp": True,
        "reason": next_reason,
    }


def _symbol_history_guard(symbol: str, confidence: float) -> Dict[str, Any]:
    stats = load_symbol_stats()
    symbol_key = canonical_symbol(symbol)
    symbol_stats = stats.get(symbol_key) or {}
    total_trades = int(symbol_stats.get("total_trades") or 0)
    wins = int(symbol_stats.get("wins") or 0)
    losses = int(symbol_stats.get("losses") or 0)
    win_rate = _safe_float(symbol_stats.get("win_rate"), 0.0)
    min_sample = _int_env("PROFITABILITY_GUARD_MIN_SYMBOL_TRADES", 6)
    min_win_rate = _float_env("PROFITABILITY_GUARD_MIN_SYMBOL_WIN_RATE", 0.35)
    recovery_confidence = _float_env("PROFITABILITY_GUARD_RECOVERY_CONFIDENCE", 88.0)

    result = {
        "symbol": symbol_key,
        "total_trades": total_trades,
        "wins": wins,
        "losses": losses,
        "win_rate": round(win_rate, 4),
        "min_sample": min_sample,
        "min_win_rate": min_win_rate,
        "recovery_confidence": recovery_confidence,
        "allow": True,
        "reason": "learning",
    }

    if total_trades < min_sample:
        return result

    if win_rate < min_win_rate and float(confidence or 0.0) < recovery_confidence:
        result["allow"] = False
        result["reason"] = "weak_symbol_history"
        return result

    result["reason"] = "history_ok"
    return result


def _exposure_risk(symbol: str, open_positions: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    symbol_key = canonical_symbol(symbol)
    asset_class = infer_asset_class(symbol_key)
    positions = list(open_positions or [])
    if not positions:
        return {"risk": 0.0, "conflicts": 0, "reason": "no_positions"}

    if asset_class == "forex" and len(symbol_key) >= 6:
        base = symbol_key[:3]
        quote = symbol_key[3:6]
    elif symbol_key.endswith("USD"):
        base = symbol_key[:-3]
        quote = "USD"
    else:
        base = symbol_key[:3]
        quote = symbol_key[3:6] if len(symbol_key) >= 6 else ""

    conflicts = 0.0
    for position in positions:
        pos_symbol = canonical_symbol(position.get("symbol") or "")
        if not pos_symbol:
            continue
        if pos_symbol == symbol_key:
            conflicts += 1.0
        elif base and base in pos_symbol:
            conflicts += 0.75
        elif quote and quote in pos_symbol:
            conflicts += 0.5

    risk = min(1.0, conflicts * 0.2)
    return {"risk": round(risk, 3), "conflicts": round(conflicts, 2), "reason": "exposure_checked"}


def evaluate_profitability_guard(
    symbol: str,
    direction: str,
    entry: float,
    sl: float,
    tp: float,
    confidence: float,
    execution_route: str,
    open_positions=None,
) -> Dict[str, Any]:
    if not _enabled():
        return {"allow": True, "reason": "disabled"}

    asset_class = infer_asset_class(symbol)
    rr_value, rr_reason = _rr(direction, entry, sl, tp)
    min_rr = _float_env("MIN_RR_RATIO", 2.0)
    risk_distance = abs(_safe_float(entry) - _safe_float(sl))
    risk_pct = risk_distance / max(abs(_safe_float(entry)), 1e-12)
    max_sl_pct = _asset_float_env(
        "PROFITABILITY_GUARD_MAX_SL_DISTANCE_PCT",
        asset_class,
        {"forex": 0.025, "metals": 0.06, "crypto": 0.16}.get(asset_class, 0.08),
    )

    guard = {
        "allow": True,
        "reason": "passed",
        "symbol": canonical_symbol(symbol),
        "asset_class": asset_class,
        "direction": direction,
        "execution_route": execution_route,
        "confidence": round(float(confidence or 0.0), 2),
        "rr": round(rr_value, 3),
        "min_rr": min_rr,
        "risk_pct": round(risk_pct, 5),
        "max_sl_distance_pct": max_sl_pct,
    }

    if rr_reason != "ok":
        return {**guard, "allow": False, "reason": rr_reason}
    if rr_value < min_rr:
        return {**guard, "allow": False, "reason": "rr_below_minimum"}
    if risk_pct > max_sl_pct:
        return {**guard, "allow": False, "reason": "sl_too_wide"}

    history = _symbol_history_guard(symbol, confidence)
    guard["symbol_history"] = history
    if not history.get("allow", True):
        return {**guard, "allow": False, "reason": history.get("reason", "weak_symbol_history")}

    exposure = _exposure_risk(symbol, open_positions)
    guard["exposure"] = exposure
    max_exposure = _float_env("PROFITABILITY_GUARD_MAX_EXPOSURE_RISK", 0.65)
    if exposure["risk"] > max_exposure:
        return {**guard, "allow": False, "reason": "exposure_too_correlated"}

    return guard
