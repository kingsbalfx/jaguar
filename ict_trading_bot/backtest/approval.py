import json
import os
import time
from pathlib import Path
from typing import Dict, Tuple

from backtest.setup_occurrence import (
    generate_setup_occurrence_report,
    setup_signature_hash,
)
from backtest.strategy_runner import generate_latest_approval
from utils.symbol_profile import build_symbol_profile_snapshot, get_backtest_thresholds


def build_strategy_profile() -> Dict[str, object]:
    profile = {
        "htf_timeframe": os.getenv("HTF_TIMEFRAME", "H4"),
        "mtf_timeframe": os.getenv("MTF_TIMEFRAME", "H1"),
        "ltf_timeframe": os.getenv("LTF_TIMEFRAME", "M15"),
        "min_extra_confirmations": max(3, int(os.getenv("MIN_EXTRA_CONFIRMATIONS", "3"))),
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
    profile.update(build_symbol_profile_snapshot())
    return profile


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


def evaluate_backtest_approval(report_path: str = None, force_required: bool = False) -> Tuple[bool, Dict[str, object]]:
    required = force_required or os.getenv("BACKTEST_APPROVAL_REQUIRED", "true").lower() in ("1", "true", "yes")
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

    symbol = report.get("symbol") or details.get("symbol")
    thresholds = get_backtest_thresholds(symbol)
    min_win_rate = float(thresholds["min_win_rate"])
    min_profit_factor = float(thresholds["min_profit_factor"])
    min_expectancy = float(thresholds["min_expectancy"])
    max_drawdown = float(thresholds["max_drawdown"])
    min_occurrences = int(thresholds["min_occurrences"])

    win_rate = float(metrics.get("win_rate", 0.0))
    profit_factor = float(metrics.get("profit_factor", 0.0))
    expectancy = float(metrics.get("expectancy", 0.0))
    drawdown = float(metrics.get("max_drawdown", 0.0))
    occurrences = int(report.get("occurrences", metrics.get("trades", 0)))

    approved = (
        occurrences >= min_occurrences
        and
        win_rate >= min_win_rate
        and profit_factor >= min_profit_factor
        and expectancy >= min_expectancy
        and abs(drawdown) <= max_drawdown
    )

    failed_checks = []
    if occurrences < min_occurrences:
        failed_checks.append(
            f"occurrences {occurrences} < required {min_occurrences}"
        )
    if win_rate < min_win_rate:
        failed_checks.append(
            f"win_rate {win_rate * 100:.1f}% < required {min_win_rate * 100:.1f}%"
        )
    if profit_factor < min_profit_factor:
        failed_checks.append(
            f"profit_factor {profit_factor:.2f} < required {min_profit_factor:.2f}"
        )
    if expectancy < min_expectancy:
        failed_checks.append(
            f"expectancy {expectancy:.3f} < required {min_expectancy:.3f}"
        )
    if abs(drawdown) > max_drawdown:
        failed_checks.append(
            f"drawdown {abs(drawdown):.2f} > allowed {max_drawdown:.2f}"
        )

    details.update(
        {
            "reason": "approved" if approved else "threshold_failed",
            "metrics": metrics,
            "occurrences": occurrences,
            "failed_checks": failed_checks,
            "win_rate": win_rate,
            "profit_factor": profit_factor,
            "expectancy": expectancy,
            "max_drawdown": drawdown,
            "thresholds": {
                "asset_class": thresholds["asset_class"],
                "min_occurrences": min_occurrences,
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

    approved, details = evaluate_backtest_approval(report_path=report_path)
    if auto_generate and details.get("reason") == "profile_mismatch":
        generate_latest_approval(symbols=symbols, report_path=report_path)
        approved, details = evaluate_backtest_approval(report_path=report_path)
    return approved, details


def ensure_symbol_backtest_approval(symbol: str, report_key: str = None) -> Tuple[bool, Dict[str, object]]:
    report_path = _resolve_report_path(report_key=report_key or symbol)
    approved, details = ensure_backtest_approval(symbols=[symbol], report_path=report_path)
    details["symbol"] = symbol
    details["report_key"] = report_key or symbol
    return approved, details


def ensure_setup_backtest_approval(
    symbol: str,
    setup_signature: Dict[str, object],
    report_key: str = None,
) -> Tuple[bool, Dict[str, object]]:
    setup_hash = setup_signature_hash(setup_signature)
    resolved_report_key = f"{report_key or symbol}_{setup_hash}"
    report_path = _resolve_report_path(report_key=resolved_report_key)
    auto_generate = os.getenv("AUTO_GENERATE_BACKTEST_APPROVAL", "true").lower() in ("1", "true", "yes")
    refresh_minutes = int(os.getenv("BACKTEST_REFRESH_MINUTES", "240"))

    if auto_generate:
        should_generate = not os.path.exists(report_path)
        if not should_generate:
            age_seconds = max(0.0, time.time() - os.path.getmtime(report_path))
            should_generate = age_seconds >= (refresh_minutes * 60)
        if should_generate or not os.path.exists(report_path):
            print(
                f"[BACKTEST] Running setup-occurrence approval for {symbol} "
                f"({setup_hash}) before live execution."
            )
            generate_setup_occurrence_report(
                symbol=symbol,
                setup_signature=setup_signature,
                report_path=report_path,
            )
            print(
                f"[BACKTEST] Setup-occurrence approval ready for {symbol} "
                f"({setup_hash})."
            )

    approved, details = evaluate_backtest_approval(report_path=report_path, force_required=True)
    if auto_generate and details.get("reason") == "profile_mismatch":
        print(
            f"[BACKTEST] Strategy profile changed for {symbol} ({setup_hash}); "
            f"regenerating setup-occurrence approval."
        )
        generate_setup_occurrence_report(
            symbol=symbol,
            setup_signature=setup_signature,
            report_path=report_path,
        )
        approved, details = evaluate_backtest_approval(report_path=report_path, force_required=True)
    details["symbol"] = symbol
    details["report_key"] = resolved_report_key
    details["setup_signature"] = setup_signature
    details["setup_signature_hash"] = setup_hash

    if os.path.exists(report_path):
        try:
            report = _load_report(report_path)
            details["occurrences"] = int(report.get("occurrences", 0))
            details["occurrence_rate"] = float(report.get("occurrence_rate", 0.0))
            details["match_level"] = report.get("match_level")
            details["matched_symbols"] = report.get("matched_symbols") or []
            details["candidate_symbols"] = report.get("candidate_symbols") or []
        except Exception:
            pass

    metrics = details.get("metrics") or {}
    win_rate = float(details.get("win_rate", metrics.get("win_rate", 0.0)))
    profit_factor = float(details.get("profit_factor", metrics.get("profit_factor", 0.0)))
    expectancy = float(details.get("expectancy", metrics.get("expectancy", 0.0)))
    drawdown = float(details.get("max_drawdown", metrics.get("max_drawdown", 0.0)))
    occurrences = int(details.get("occurrences", 0))
    occurrence_rate = float(details.get("occurrence_rate", 0.0))
    match_level = details.get("match_level") or "none"
    matched_symbols = details.get("matched_symbols") or []
    decision = "APPROVED" if approved else "REJECTED"
    print(
        f"[BACKTEST] {symbol} {decision} | occurrences={occurrences} "
        f"| win_rate={win_rate * 100:.1f}% | occurrence_rate={occurrence_rate * 100:.1f}% "
        f"| profit_factor={profit_factor:.2f} | expectancy={expectancy:.3f} "
        f"| match_level={match_level} | matched_symbols={len(matched_symbols)} "
        f"| drawdown={drawdown:.2f}"
    )
    if not approved:
        failed_checks = details.get("failed_checks") or []
        if failed_checks:
            print(f"[BACKTEST] {symbol} rejection reasons: {', '.join(failed_checks)}")

    return approved, details
