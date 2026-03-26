import json
import os
import time
from pathlib import Path
from typing import Dict, Tuple

from backtest.strategy_runner import generate_latest_approval


def build_strategy_profile() -> Dict[str, object]:
    return {
        "htf_timeframe": os.getenv("HTF_TIMEFRAME", "H4"),
        "mtf_timeframe": os.getenv("MTF_TIMEFRAME", "H1"),
        "ltf_timeframe": os.getenv("LTF_TIMEFRAME", "M15"),
        "min_extra_confirmations": int(os.getenv("MIN_EXTRA_CONFIRMATIONS", "2")),
        "count_fundamentals_as_confirmation": os.getenv("COUNT_FUNDAMENTALS_AS_CONFIRMATION", "false").lower() in ("1", "true", "yes"),
        "default_rr_ratio": float(os.getenv("DEFAULT_RR_RATIO", "3.0")),
        "min_rr_ratio": float(os.getenv("MIN_RR_RATIO", "2.0")),
        "relax_liquidity_rule": os.getenv("RELAX_LIQUIDITY_RULE", "false").lower() in ("1", "true", "yes"),
        "liquidity_tolerance_ratio": float(os.getenv("LIQUIDITY_TOLERANCE_RATIO", "0.0015")),
        "relax_fvg_requirement": os.getenv("RELAX_FVG_REQUIREMENT", "false").lower() in ("1", "true", "yes"),
        "entry_fib_buffer_ratio": float(os.getenv("ENTRY_FIB_BUFFER_RATIO", "0.08")),
        "allow_ltf_trend_fallback": os.getenv("ALLOW_LTF_TREND_FALLBACK", "false").lower() in ("1", "true", "yes"),
        "news_filter_strict": os.getenv("NEWS_FILTER_STRICT", "false").lower() in ("1", "true", "yes"),
        "rule_quality_required": os.getenv("RULE_QUALITY_REQUIRED", "false").lower() in ("1", "true", "yes"),
    }


def _load_report(report_path: str) -> Dict[str, object]:
    with open(report_path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _resolve_report_path(report_path: str = None, report_key: str = None) -> str:
    base = Path(report_path or os.getenv("BACKTEST_REPORT_PATH", "backtest/latest_approval.json"))
    if not base.is_absolute():
        base = Path(__file__).resolve().parent.parent / base

    if report_key:
        safe_key = str(report_key).replace("/", "_").replace("\\", "_").replace(":", "_").upper()
        base = base.with_name(f"{base.stem}_{safe_key}{base.suffix}")

    return str(base)


def evaluate_backtest_approval(report_path: str = None) -> Tuple[bool, Dict[str, object]]:
    required = os.getenv("BACKTEST_APPROVAL_REQUIRED", "false").lower() in ("1", "true", "yes")
    report_path = _resolve_report_path(report_path)
    profile = build_strategy_profile()

    details: Dict[str, object] = {
        "required": required,
        "report_path": report_path,
        "profile": profile,
    }

    if not required:
        details["reason"] = "approval_not_required"
        return True, details

    if not os.path.exists(report_path):
        details["reason"] = "report_missing"
        return False, details

    try:
        report = _load_report(report_path)
    except Exception as exc:
        details["reason"] = "report_invalid"
        details["error"] = str(exc)
        return False, details

    report_profile = report.get("profile") or {}
    metrics = report.get("metrics") or {}

    if report_profile != profile:
        details["reason"] = "profile_mismatch"
        details["report_profile"] = report_profile
        return False, details

    min_win_rate = float(os.getenv("BACKTEST_MIN_WIN_RATE", "0.45"))
    min_profit_factor = float(os.getenv("BACKTEST_MIN_PROFIT_FACTOR", "1.2"))
    min_expectancy = float(os.getenv("BACKTEST_MIN_EXPECTANCY", "0.0"))
    max_drawdown = float(os.getenv("BACKTEST_MAX_DRAWDOWN", "1500"))

    win_rate = float(metrics.get("win_rate", 0.0))
    profit_factor = float(metrics.get("profit_factor", 0.0))
    expectancy = float(metrics.get("expectancy", 0.0))
    drawdown = float(metrics.get("max_drawdown", 0.0))

    approved = (
        win_rate >= min_win_rate
        and profit_factor >= min_profit_factor
        and expectancy >= min_expectancy
        and abs(drawdown) <= max_drawdown
    )

    details.update(
        {
            "reason": "approved" if approved else "threshold_failed",
            "metrics": metrics,
            "thresholds": {
                "min_win_rate": min_win_rate,
                "min_profit_factor": min_profit_factor,
                "min_expectancy": min_expectancy,
                "max_drawdown": max_drawdown,
            },
        }
    )
    return approved, details


def ensure_backtest_approval(symbols=None, report_path: str = None) -> Tuple[bool, Dict[str, object]]:
    auto_generate = os.getenv("AUTO_GENERATE_BACKTEST_APPROVAL", "true").lower() in ("1", "true", "yes")
    report_path = _resolve_report_path(report_path)
    refresh_minutes = int(os.getenv("BACKTEST_REFRESH_MINUTES", "240"))

    if auto_generate:
        should_generate = not os.path.exists(report_path)
        if not should_generate:
            age_seconds = max(0.0, time.time() - os.path.getmtime(report_path))
            should_generate = age_seconds >= (refresh_minutes * 60)
        if should_generate or not os.path.exists(report_path):
            generate_latest_approval(symbols=symbols, report_path=report_path)

    return evaluate_backtest_approval(report_path=report_path)


def ensure_symbol_backtest_approval(symbol: str, report_key: str = None) -> Tuple[bool, Dict[str, object]]:
    report_path = _resolve_report_path(report_key=report_key or symbol)
    approved, details = ensure_backtest_approval(symbols=[symbol], report_path=report_path)
    details["symbol"] = symbol
    details["report_key"] = report_key or symbol
    return approved, details
