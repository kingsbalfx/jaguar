import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

from backtest.metrics import calculate_metrics
from backtest.strategy_runner import (
    _analysis_from_frames,
    _fetch_rates,
    _profile_snapshot,
    _require_mt5,
    _rule_quality_from_context,
    _simulate_outcome,
)
from risk.sl_tp_engine import calculate_sl_tp
from strategy.entry_model import check_entry
from strategy.setup_confirmations import bos_setup, liquidity_sweep_or_swing


def build_setup_signature(signal, analysis, confirmation_flags):
    trend = signal.get("trend") or analysis.get("overall_trend")
    htf = analysis.get("HTF", {})
    mtf = analysis.get("MTF", {})
    ltf = analysis.get("LTF", {})
    fvg = signal.get("fvg") or {}
    htf_ob = signal.get("htf_ob") or {}
    setup_context = signal.get("setup_context") or {}
    bos = setup_context.get("bos") or {}
    liquidity = setup_context.get("liquidity") or {}

    confirmations_met = sorted(
        name for name, passed in (confirmation_flags or {}).items() if passed and name != "fundamentals"
    )

    return {
        "direction": signal.get("direction"),
        "trend": trend,
        "timeframes": analysis.get("timeframes", {}),
        "htf_trend": htf.get("trend"),
        "mtf_trend": mtf.get("trend"),
        "ltf_trend": ltf.get("trend"),
        "fib_zone": signal.get("fib_zone"),
        "liquidity_event_confirmed": bool(liquidity.get("confirmed")),
        "liquidity_sweep": bool(liquidity.get("liquidity_sweep")),
        "mtf_swing": bool(liquidity.get("mtf_swing")),
        "ltf_swing": bool(liquidity.get("ltf_swing")),
        "bos_confirmed": bool(bos.get("confirmed")),
        "smt_confirmed": bool((confirmation_flags or {}).get("smt")),
        "rule_quality": bool((confirmation_flags or {}).get("rule_quality")),
        "ml_quality": bool((confirmation_flags or {}).get("ml")),
        "has_fvg": isinstance(fvg, dict) and fvg.get("low") is not None and fvg.get("high") is not None,
        "fvg_timeframe": fvg.get("timeframe"),
        "has_order_block": isinstance(htf_ob, dict) and htf_ob.get("low") is not None and htf_ob.get("high") is not None,
        "order_block_timeframe": htf_ob.get("timeframe"),
        "mtf_bos": bool(bos.get("mtf_bos")),
        "ltf_bos": bool(bos.get("ltf_bos")),
        "confirmations_met": confirmations_met,
        "confirmation_count": len(confirmations_met),
    }


def setup_signature_hash(setup_signature: Dict[str, object]) -> str:
    payload = json.dumps(setup_signature, sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12].upper()


def _report_path(report_path):
    path = Path(report_path)
    if not path.is_absolute():
        path = Path(__file__).resolve().parent.parent / path
    return path


def _match_signature(candidate_signature, target_signature):
    return candidate_signature == target_signature


def run_setup_occurrence_backtest(symbol: str, target_signature: Dict[str, object]) -> Dict[str, object]:
    _require_mt5()

    profile = _profile_snapshot()
    history_bars = int(os.getenv("BACKTEST_HISTORY_BARS", "600"))
    lookahead_bars = int(os.getenv("BACKTEST_LOOKAHEAD_BARS", "24"))
    step_bars = max(1, int(os.getenv("BACKTEST_STEP_BARS", "12")))
    warmup_bars = max(150, int(os.getenv("BACKTEST_WARMUP_BARS", "200")))
    progress_logs = os.getenv("BACKTEST_PROGRESS_LOGS", "true").lower() in ("1", "true", "yes")

    htf = profile["htf_timeframe"]
    mtf = profile["mtf_timeframe"]
    ltf = profile["ltf_timeframe"]
    frames_full = {
        htf: _fetch_rates(symbol, htf, history_bars),
        mtf: _fetch_rates(symbol, mtf, history_bars),
        ltf: _fetch_rates(symbol, ltf, history_bars),
        "D1": _fetch_rates(symbol, "D1", max(400, history_bars // 4)),
    }

    ltf_df = frames_full[ltf]
    if ltf_df.empty or len(ltf_df) <= warmup_bars + lookahead_bars:
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "profile": profile,
            "symbol": symbol,
            "setup_signature": target_signature,
            "occurrences": 0,
            "candidate_setups": 0,
            "occurrence_rate": 0.0,
            "metrics": calculate_metrics([], [10000.0]),
            "trades_sample": [],
        }

    trades: List[Dict[str, object]] = []
    candidate_setups = 0
    equity = 10000.0
    equity_curve = [equity]
    i = warmup_bars

    while i < len(ltf_df) - lookahead_bars:
        current_time = ltf_df.iloc[i]["time"]
        price = float(ltf_df.iloc[i]["close"])
        sliced = {
            timeframe: df[df["time"] <= current_time].tail(warmup_bars).reset_index(drop=True)
            for timeframe, df in frames_full.items()
        }

        analysis = _analysis_from_frames(symbol, price, sliced, profile)
        if not analysis:
            i += step_bars
            continue

        trend = analysis["overall_trend"]
        if trend not in ("bullish", "bearish"):
            i += step_bars
            continue

        signal = check_entry(
            trend=trend,
            price=price,
            fib_levels=analysis["MTF"]["fib"],
            fvgs=analysis["LTF"]["fvgs"],
            htf_order_blocks=analysis["MTF"]["order_blocks"],
        )
        if not isinstance(signal, dict) or not signal:
            i += step_bars
            continue

        direction = "buy" if trend == "bullish" else "sell"
        signal["symbol"] = symbol
        signal["direction"] = direction
        signal["trend"] = trend

        liquidity_state = liquidity_sweep_or_swing(price, analysis, direction)
        bos_state = bos_setup(analysis, trend)
        smt_ok = True
        daily_trend = analysis["D1"].get("trend")
        rule_ok = _rule_quality_from_context(signal, daily_trend)
        ml_ok = True
        signal["setup_context"] = {
            "liquidity": liquidity_state,
            "bos": bos_state,
        }

        confirmation_flags = {
            "liquidity_setup": liquidity_state["confirmed"],
            "bos": bos_state["confirmed"],
            "smt": smt_ok,
            "rule_quality": rule_ok,
            "ml": ml_ok,
        }
        candidate_signature = build_setup_signature(signal, analysis, confirmation_flags)
        candidate_setups += 1

        if not _match_signature(candidate_signature, target_signature):
            i += step_bars
            continue

        htf_ob = signal.get("htf_ob") or {}
        if htf_ob.get("low") is None or htf_ob.get("high") is None:
            i += step_bars
            continue

        if progress_logs:
            print(
                f"[SETUP-BACKTEST] {symbol} matched at {current_time.isoformat()} "
                f"| confirmations={candidate_signature['confirmations_met']}"
            )

        sl, tp = calculate_sl_tp(direction=direction, entry_price=price, htf_ob=htf_ob)
        future_df = ltf_df.iloc[i + 1 : i + 1 + lookahead_bars]
        result, bars_held = _simulate_outcome(direction, price, sl, tp, future_df)

        trade = {
            "symbol": symbol,
            "direction": direction,
            "entry": price,
            "sl": sl,
            "tp": tp,
            "result": result,
            "opened_at": current_time.isoformat(),
            "bars_held": bars_held,
            "confirmations": candidate_signature["confirmations_met"],
            "setup_signature": candidate_signature,
        }
        trades.append(trade)
        equity += result * 100.0
        equity_curve.append(equity)
        i += max(bars_held, step_bars)

    metrics = calculate_metrics(trades, equity_curve)
    occurrences = len(trades)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "profile": profile,
        "symbol": symbol,
        "setup_signature": target_signature,
        "setup_signature_hash": setup_signature_hash(target_signature),
        "occurrences": occurrences,
        "candidate_setups": candidate_setups,
        "occurrence_rate": (occurrences / candidate_setups) if candidate_setups else 0.0,
        "metrics": metrics,
        "trades_sample": trades[:25],
    }


def generate_setup_occurrence_report(symbol: str, setup_signature: Dict[str, object], report_path: str):
    report = run_setup_occurrence_backtest(symbol=symbol, target_signature=setup_signature)
    path = _report_path(report_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    return report
