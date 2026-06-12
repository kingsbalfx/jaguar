"""Setup occurrence reports produced by the same strict strategy backtest."""

import hashlib
import json
from pathlib import Path
from typing import Dict

from backtest.strategy_runner import run_strategy_backtest


def build_setup_signature(signal, analysis, confirmation_flags=None):
    """Build a deterministic identity from already-confirmed state-machine data."""
    setup = signal.get("setup") or {}
    return {
        "symbol": signal.get("symbol"),
        "direction": signal.get("direction") or setup.get("direction"),
        "trend": signal.get("trend") or setup.get("trend") or analysis.get("overall_trend"),
        "states": tuple(state.get("name") for state in setup.get("states", []) if state.get("confirmed")),
        "retracement_kind": (setup.get("retracement") or {}).get("kind"),
    }


def setup_signature_hash(setup_signature: Dict[str, object]) -> str:
    payload = json.dumps(setup_signature or {}, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:12].upper()


def run_setup_occurrence_backtest(symbol: str, target_signature: Dict[str, object]) -> Dict[str, object]:
    report = run_strategy_backtest([symbol])
    metrics = report.get("metrics") or {}
    return {
        **report,
        "symbol": symbol,
        "setup_signature": target_signature,
        "setup_signature_hash": setup_signature_hash(target_signature),
        "occurrences": int(metrics.get("trades", 0)),
        "occurrence_rate": 0.0,
        "match_level": "identical_strategy",
        "matched_symbols": [symbol] if metrics.get("trades", 0) else [],
        "candidate_symbols": [symbol],
    }


def generate_setup_occurrence_report(symbol: str, setup_signature: Dict[str, object], report_path: str):
    report = run_setup_occurrence_backtest(symbol, setup_signature)
    path = Path(report_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, default=str)
    return report
