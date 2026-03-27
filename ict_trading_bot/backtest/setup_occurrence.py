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
from strategy.setup_confirmations import (
    bos_setup,
    evaluate_confirmation_quality,
    liquidity_sweep_or_swing,
    price_action_setup,
)
from utils.symbol_profile import get_backtest_thresholds, infer_asset_class, related_symbols


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
    price_action = setup_context.get("price_action") or {}
    confirmation_summary = signal.get("confirmation_summary") or {}

    confirmations_met = sorted(
        name for name, passed in (confirmation_flags or {}).items() if passed and name != "fundamentals"
    )
    asset_class = signal.get("asset_class") or infer_asset_class(signal.get("symbol"))
    setup_family = "|".join(
        [
            str(signal.get("direction")),
            str(trend),
            str(signal.get("fib_zone")),
            str(asset_class),
            "liq" if liquidity.get("confirmed") else "no-liq",
            "bos" if bos.get("confirmed") else "no-bos",
            "pa" if price_action.get("confirmed") else "no-pa",
            "ob" if isinstance(htf_ob, dict) and htf_ob.get("low") is not None and htf_ob.get("high") is not None else "no-ob",
        ]
    )

    return {
        "symbol": signal.get("symbol"),
        "asset_class": asset_class,
        "setup_family": setup_family,
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
        "price_action_confirmed": bool(price_action.get("confirmed")),
        "mtf_price_action_confirmed": bool(price_action.get("mtf_confirmed")),
        "ltf_price_action_confirmed": bool(price_action.get("ltf_confirmed")),
        "mtf_price_action_patterns": sorted(price_action.get("mtf_patterns") or []),
        "ltf_price_action_patterns": sorted(price_action.get("ltf_patterns") or []),
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
        "confirmation_score": round(float(confirmation_summary.get("score", 0.0)), 3),
        "min_confirmation_score": round(float(confirmation_summary.get("min_score", 0.0)), 3),
        "weighted_confirmations": confirmation_summary.get("weighted_flags") or {},
    }


def setup_signature_hash(setup_signature: Dict[str, object]) -> str:
    payload = json.dumps(setup_signature, sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:12].upper()


def _report_path(report_path):
    path = Path(report_path)
    if not path.is_absolute():
        path = Path(__file__).resolve().parent.parent / path
    return path


def _soft_match_score(candidate_signature, target_signature):
    score = 0
    weighted_checks = (
        ("htf_trend", 2),
        ("mtf_trend", 2),
        ("ltf_trend", 1),
        ("smt_confirmed", 1),
        ("rule_quality", 1),
        ("ml_quality", 1),
        ("has_fvg", 1),
        ("has_order_block", 1),
        ("mtf_bos", 1),
        ("ltf_bos", 1),
    )
    for key, weight in weighted_checks:
        if candidate_signature.get(key) == target_signature.get(key):
            score += weight

    if abs(
        int(candidate_signature.get("confirmation_count", 0))
        - int(target_signature.get("confirmation_count", 0))
    ) <= 1:
        score += 2

    if abs(
        float(candidate_signature.get("confirmation_score", 0.0))
        - float(target_signature.get("confirmation_score", 0.0))
    ) <= 1.0:
        score += 2

    candidate_patterns = set(candidate_signature.get("mtf_price_action_patterns") or [])
    candidate_patterns.update(candidate_signature.get("ltf_price_action_patterns") or [])
    target_patterns = set(target_signature.get("mtf_price_action_patterns") or [])
    target_patterns.update(target_signature.get("ltf_price_action_patterns") or [])
    if candidate_patterns and target_patterns and candidate_patterns.intersection(target_patterns):
        score += 2
    elif not candidate_patterns and not target_patterns:
        score += 1

    return score


def _match_signature(candidate_symbol, target_symbol, candidate_signature, target_signature):
    if candidate_symbol == target_symbol and candidate_signature == target_signature:
        return "exact"

    if candidate_signature.get("setup_family") != target_signature.get("setup_family"):
        return None

    score = _soft_match_score(candidate_signature, target_signature)
    same_symbol_min_score = int(os.getenv("SETUP_BACKTEST_SAME_SYMBOL_MIN_SCORE", "6"))
    asset_class_min_score = int(os.getenv("SETUP_BACKTEST_ASSET_CLASS_MIN_SCORE", "5"))
    candidate_count = int(candidate_signature.get("confirmation_count", 0))
    target_count = int(target_signature.get("confirmation_count", 0))

    if candidate_symbol == target_symbol and abs(candidate_count - target_count) <= 1 and score >= same_symbol_min_score:
        return "same_symbol"

    asset_class_fallback = os.getenv("SETUP_BACKTEST_ASSET_CLASS_FALLBACK", "true").lower() in ("1", "true", "yes")
    if (
        asset_class_fallback
        and candidate_signature.get("asset_class") == target_signature.get("asset_class")
        and abs(candidate_count - target_count) <= 2
        and score >= asset_class_min_score
    ):
        return "asset_class"

    return None


def _empty_bucket():
    return {
        "trades": [],
        "candidate_setups": 0,
        "matched_symbols": set(),
    }


def _finalize_bucket(bucket):
    trades = sorted(bucket["trades"], key=lambda trade: trade["opened_at"])
    equity = 10000.0
    equity_curve = [equity]
    for trade in trades:
        equity += float(trade["result"]) * 100.0
        equity_curve.append(equity)
    metrics = calculate_metrics(trades, equity_curve)
    occurrences = len(trades)
    candidate_setups = int(bucket["candidate_setups"])
    return {
        "occurrences": occurrences,
        "candidate_setups": candidate_setups,
        "occurrence_rate": (occurrences / candidate_setups) if candidate_setups else 0.0,
        "matched_symbols": sorted(bucket["matched_symbols"]),
        "metrics": metrics,
        "trades": trades,
    }


def _select_match_level(level_stats, min_occurrences):
    ordered_levels = ("exact", "same_symbol", "asset_class")
    for level in ordered_levels:
        if level_stats[level]["occurrences"] >= min_occurrences:
            return level

    populated_levels = [
        (level, level_stats[level]["occurrences"])
        for level in ordered_levels
        if level_stats[level]["occurrences"] > 0
    ]
    if populated_levels:
        populated_levels.sort(key=lambda item: (-item[1], ordered_levels.index(item[0])))
        return populated_levels[0][0]
    return "exact"


def run_setup_occurrence_backtest(symbol: str, target_signature: Dict[str, object]) -> Dict[str, object]:
    _require_mt5()

    profile = _profile_snapshot()
    thresholds = get_backtest_thresholds(symbol)
    history_bars = int(os.getenv("BACKTEST_HISTORY_BARS", "2400"))
    lookahead_bars = int(os.getenv("BACKTEST_LOOKAHEAD_BARS", "24"))
    step_bars = max(1, int(os.getenv("BACKTEST_STEP_BARS", "24")))
    warmup_bars = max(200, int(os.getenv("BACKTEST_WARMUP_BARS", "300")))
    progress_logs = os.getenv("BACKTEST_PROGRESS_LOGS", "false").lower() in ("1", "true", "yes")

    htf = profile["htf_timeframe"]
    mtf = profile["mtf_timeframe"]
    ltf = profile["ltf_timeframe"]
    target_symbol = str(symbol).upper()
    candidate_symbols = related_symbols(target_symbol)
    match_buckets = {
        "exact": _empty_bucket(),
        "same_symbol": _empty_bucket(),
        "asset_class": _empty_bucket(),
    }

    for candidate_symbol in candidate_symbols:
        frames_full = {
            htf: _fetch_rates(candidate_symbol, htf, history_bars),
            mtf: _fetch_rates(candidate_symbol, mtf, history_bars),
            ltf: _fetch_rates(candidate_symbol, ltf, history_bars),
            "D1": _fetch_rates(candidate_symbol, "D1", max(400, history_bars // 4)),
        }

        ltf_df = frames_full[ltf]
        if ltf_df.empty or len(ltf_df) <= warmup_bars + lookahead_bars:
            continue

        i = warmup_bars
        while i < len(ltf_df) - lookahead_bars:
            current_time = ltf_df.iloc[i]["time"]
            price = float(ltf_df.iloc[i]["close"])
            sliced = {
                timeframe: df[df["time"] <= current_time].tail(warmup_bars).reset_index(drop=True)
                for timeframe, df in frames_full.items()
            }

            analysis = _analysis_from_frames(candidate_symbol, price, sliced, profile)
            if not analysis:
                i += step_bars
                continue

            if candidate_symbol == target_symbol:
                match_buckets["exact"]["candidate_setups"] += 1
                match_buckets["same_symbol"]["candidate_setups"] += 1
            match_buckets["asset_class"]["candidate_setups"] += 1

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
                symbol=candidate_symbol,
                atr=analysis["MTF"].get("atr"),
            )
            if not isinstance(signal, dict) or not signal:
                i += step_bars
                continue

            direction = "buy" if trend == "bullish" else "sell"
            signal["symbol"] = candidate_symbol
            signal["direction"] = direction
            signal["trend"] = trend

            liquidity_state = liquidity_sweep_or_swing(price, analysis, direction)
            bos_state = bos_setup(analysis, trend)
            price_action_state = price_action_setup(analysis, trend)
            smt_ok = True
            daily_trend = analysis["D1"].get("trend")
            rule_ok = _rule_quality_from_context(signal, daily_trend)
            ml_ok = True
            signal["setup_context"] = {
                "liquidity": liquidity_state,
                "bos": bos_state,
                "price_action": price_action_state,
            }

            confirmation_flags = {
                "liquidity_setup": liquidity_state["confirmed"],
                "bos": bos_state["confirmed"],
                "price_action": price_action_state["confirmed"],
                "smt": smt_ok,
                "rule_quality": rule_ok,
                "ml": ml_ok,
            }
            extra_confirmations = sum(1 for passed in confirmation_flags.values() if passed)
            if extra_confirmations < int(profile.get("min_extra_confirmations", 3)):
                i += step_bars
                continue
            confirmation_summary = evaluate_confirmation_quality(
                confirmation_flags,
                symbol=candidate_symbol,
            )
            if not confirmation_summary["passed"]:
                i += step_bars
                continue
            signal["confirmation_summary"] = confirmation_summary
            candidate_signature = build_setup_signature(signal, analysis, confirmation_flags)
            match_level = _match_signature(
                candidate_symbol,
                target_symbol,
                candidate_signature,
                target_signature,
            )
            if not match_level:
                i += step_bars
                continue

            htf_ob = signal.get("htf_ob") or {}
            if htf_ob.get("low") is None or htf_ob.get("high") is None:
                i += step_bars
                continue

            if progress_logs:
                print(
                    f"[SETUP-BACKTEST] {candidate_symbol} matched {match_level} at {current_time.isoformat()} "
                    f"| confirmations={candidate_signature['confirmations_met']}"
                )

            sl, tp = calculate_sl_tp(direction=direction, entry_price=price, htf_ob=htf_ob)
            future_df = ltf_df.iloc[i + 1 : i + 1 + lookahead_bars]
            result, bars_held = _simulate_outcome(direction, price, sl, tp, future_df)

            trade = {
                "symbol": candidate_symbol,
                "target_symbol": target_symbol,
                "match_level": match_level,
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
            match_buckets[match_level]["trades"].append(trade)
            match_buckets[match_level]["matched_symbols"].add(candidate_symbol)
            i += max(bars_held, step_bars)

    level_stats = {
        level: _finalize_bucket(bucket)
        for level, bucket in match_buckets.items()
    }
    selected_level = _select_match_level(level_stats, thresholds["min_occurrences"])
    selected_bucket = level_stats[selected_level]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "profile": profile,
        "symbol": target_symbol,
        "asset_class": target_signature.get("asset_class") or infer_asset_class(target_symbol),
        "candidate_symbols": candidate_symbols,
        "match_level": selected_level,
        "match_level_stats": {
            level: {
                "occurrences": stats["occurrences"],
                "candidate_setups": stats["candidate_setups"],
                "occurrence_rate": stats["occurrence_rate"],
                "matched_symbols": stats["matched_symbols"],
            }
            for level, stats in level_stats.items()
        },
        "setup_signature": target_signature,
        "setup_signature_hash": setup_signature_hash(target_signature),
        "occurrences": selected_bucket["occurrences"],
        "candidate_setups": selected_bucket["candidate_setups"],
        "occurrence_rate": selected_bucket["occurrence_rate"],
        "matched_symbols": selected_bucket["matched_symbols"],
        "metrics": selected_bucket["metrics"],
        "trades_sample": selected_bucket["trades"][:25],
    }


def generate_setup_occurrence_report(symbol: str, setup_signature: Dict[str, object], report_path: str):
    report = run_setup_occurrence_backtest(symbol=symbol, target_signature=setup_signature)
    path = _report_path(report_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    return report
