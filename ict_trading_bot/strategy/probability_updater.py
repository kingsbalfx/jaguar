"""Legacy outcome recorder for completed ICT setups.

This module is kept only for backward compatibility with older imports. It does
not feed live trade decisions, does not produce probabilities, and does not
change the strict ICT/Kingsbalfx state machines. It records transparent win/loss
counts by rule signature for audit only.
"""

import json
from pathlib import Path
from typing import Any, Dict

OUTCOME_FILE = Path(__file__).resolve().parents[1] / "data" / "rule_outcomes.json"
PROBABILITY_FILE = OUTCOME_FILE


def _confirmed(value: Any) -> bool:
    if isinstance(value, dict):
        return bool(value.get("confirmed") or value.get("passed") or value.get("executable"))
    return bool(value)


def _default_table() -> Dict[str, Any]:
    return {"version": 2, "purpose": "audit_only_rule_outcomes", "regimes": {}}


def _load_table(path: Path = OUTCOME_FILE) -> Dict[str, Any]:
    if not path.exists():
        return _default_table()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _default_table()
    if not isinstance(data, dict):
        return _default_table()
    data.setdefault("version", 2)
    data.setdefault("purpose", "audit_only_rule_outcomes")
    data.setdefault("regimes", {})
    return data


def _signature(features: Dict[str, Any]) -> str:
    ordered = (
        "sweep",
        "displacement",
        "bos",
        "fvg_exists",
        "ob_exists",
        "premium_discount",
        "target_liquidity",
        "retracement",
        "lower_timeframe_confirmation",
    )
    parts = [f"{name}:{'yes' if _confirmed(features.get(name)) else 'no'}" for name in ordered]
    return "|".join(parts)


def update_probability_table(regime, features, win):
    """Backward-compatible name that records outcomes for audit only.

    The returned table is never used by the live strategy. The function name is
    retained so old scripts importing it keep working.
    """
    features = features or {}
    regime_key = str(regime or "unknown")
    table = _load_table()
    regimes = table.setdefault("regimes", {})
    regime_table = regimes.setdefault(regime_key, {"total": 0, "wins": 0, "signatures": {}})

    regime_table["total"] = int(regime_table.get("total", 0)) + 1
    if bool(win):
        regime_table["wins"] = int(regime_table.get("wins", 0)) + 1

    key = _signature(features)
    signatures = regime_table.setdefault("signatures", {})
    record = signatures.setdefault(key, {"total": 0, "wins": 0, "features": {}})
    record["total"] = int(record.get("total", 0)) + 1
    if bool(win):
        record["wins"] = int(record.get("wins", 0)) + 1
    record["features"] = {name: _confirmed(value) for name, value in features.items()}

    OUTCOME_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTCOME_FILE.write_text(json.dumps(table, indent=2, sort_keys=True), encoding="utf-8")

    try:
        from strategy.probability_sync import sync_probability_table_to_supabase
    except ImportError:
        return table
    sync_probability_table_to_supabase(table)
    return table
