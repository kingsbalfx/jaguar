"""Binary trade geometry, minimum-RR, and exposure guards."""

import os
from typing import Any, Dict, Iterable, Tuple

from utils.symbol_profile import canonical_symbol


def _rr(direction: str, entry: float, sl: float, tp: float) -> Tuple[float, str]:
    side = str(direction or "").lower()
    entry, sl, tp = float(entry), float(sl), float(tp)
    if side == "buy" and sl < entry < tp:
        return (tp - entry) / (entry - sl), "ok"
    if side == "sell" and tp < entry < sl:
        return (entry - tp) / (sl - entry), "ok"
    return 0.0, "invalid_geometry"


def normalize_rr_after_sl_adjustment(direction: str, entry: float, sl: float, tp: float, min_rr: float = None):
    minimum = float(min_rr or os.getenv("MIN_RR_RATIO", "2.0"))
    rr, reason = _rr(direction, entry, sl, tp)
    return sl, tp, {
        "rr": rr,
        "minimum_rr": minimum,
        "valid": reason == "ok" and rr >= minimum,
        "reason": reason if reason != "ok" else "minimum_rr_not_met" if rr < minimum else "ok",
    }


def evaluate_profitability_guard(
    symbol: str,
    direction: str,
    entry: float,
    sl: float,
    tp: float,
    open_positions: Iterable[Dict[str, Any]] = None,
    **_ignored,
) -> Dict[str, Any]:
    rr, reason = _rr(direction, entry, sl, tp)
    minimum = float(os.getenv("MIN_RR_RATIO", "2.0"))
    duplicate = any(canonical_symbol(position.get("symbol")) == canonical_symbol(symbol) for position in (open_positions or []))
    allow = reason == "ok" and rr >= minimum and not duplicate
    return {
        "allow": allow,
        "reason": "passed" if allow else "duplicate_exposure" if duplicate else "rr_or_geometry_invalid",
        "rr": rr,
        "minimum_rr": minimum,
    }
