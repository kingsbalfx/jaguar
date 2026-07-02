"""Live ICT state-machine orchestrator."""

import datetime
import logging
import os
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from dotenv import load_dotenv

from bot_api import start_in_thread
from bot_state import consume_restart_request, is_running, set_connection, update_metrics
from config.symbol_mappings import candidates_for
from config.smt_correlations import correlated_markets
from config.trading_pairs import TradingPairs
from dashboard.bridge import persist_account_snapshot_to_supabase, persist_signal_to_supabase, push_trade
import execution.mt5_connector as mt5_connector
from execution.mt5_connector import (
    calculate_volume_for_risk,
    connect,
    get_broker_symbols,
    get_account_snapshot,
    get_open_positions,
    get_tick_snapshot,
    reconnect,
)
from execution.pre_trade_validator import validate_execution_safety
from execution.trade_executor import close_position, execute_trade, modify_position
from fundamentals.news_filter import news_allows_trade
from multi_account_runner import load_accounts
from risk.protection import can_trade, register_trade, setup_identity
from risk.trade_management import manage_trade
from kingsbalfx_concept import evaluate as evaluate_kingsbalfx
from strategy.pre_trade_analysis import analyze_market_top_down
from strategy.unified_strategy import SEQUENCE, evaluate_strategy
from utils.logger import bot_log
from utils.sessions import asset_trading_open, friday_entry_allowed, in_london_session, in_newyork_session
from utils.symbol_profile import infer_asset_class
from utils.user_profiles import get_profile_max_trades, get_user_profile


load_dotenv()
LOGGER = logging.getLogger("ict_state_machine")
if not LOGGER.handlers:
    stream = logging.StreamHandler()
    stream.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    LOGGER.addHandler(stream)
LOGGER.setLevel(getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO))


def _truthy(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).lower() in ("1", "true", "yes", "on")


def _int_env(name: str, default: int, minimum: int = None, maximum: int = None) -> int:
    try:
        value = int(str(os.getenv(name, str(default))).strip())
    except (TypeError, ValueError):
        value = default
    if minimum is not None:
        value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value


def _float_env(name: str, default: float, minimum: float = None, maximum: float = None) -> float:
    try:
        value = float(str(os.getenv(name, str(default))).strip())
    except (TypeError, ValueError):
        value = default
    if minimum is not None:
        value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value


def _chunks(items, size: int):
    size = max(1, int(size))
    for start in range(0, len(items), size):
        yield start // size + 1, items[start:start + size]


def _yes_no(value) -> str:
    return "yes" if bool(value) else "no"


def _sources(zones) -> str:
    sources = sorted(
        {
            str(zone.get("source") or "major_swing")
            for zone in zones or []
            if isinstance(zone, dict)
        }
    )
    return ",".join(sources) if sources else "none"


def _state_reasoning(state: dict) -> str:
    name = state.get("name")
    evidence = state.get("evidence") or {}
    confirmed = bool(state.get("confirmed"))
    if name == "higher_timeframe_narrative":
        if "H1" in evidence or "M15" in evidence:
            return (
                f"H1={evidence.get('H1', 'unknown')} M15={evidence.get('M15', 'unknown')} "
                f"h1_bias={evidence.get('h1_bias', 'unknown')} "
                f"m15_current_h1_bias={evidence.get('m15_current_h1_bias', 'unknown')} "
                f"structural={_yes_no(evidence.get('structural_alignment'))} "
                f"conflict={_yes_no(evidence.get('structural_opposition'))} "
                f"mode={evidence.get('alignment_mode', 'unknown')} "
                f"reason={evidence.get('alignment_reason', 'none')} "
                f"agreement={_yes_no(confirmed)}"
            )
        return (
            f"H1={evidence.get('H1', 'unknown')} M15={evidence.get('M15', 'unknown')} "
            f"previous_day_background={_yes_no(evidence.get('previous_day_context'))} "
            f"agreement={_yes_no(confirmed)}"
        )
    if name == "external_liquidity":
        zones = evidence.get("entry_side") or []
        return f"external_liquidity_found={_yes_no(zones)} count={len(zones)} sources={_sources(zones)}"
    if name == "liquidity_sweep":
        return (
            f"sweep_confirmed={_yes_no(evidence.get('confirmed'))} "
            f"source={evidence.get('swept_source', 'none')} reclaimed_inside={_yes_no(evidence.get('confirmed'))}"
        )
    if name == "strong_displacement":
        return (
            f"displacement={_yes_no(evidence.get('displacement'))} "
            f"body_at_least_60_percent={_yes_no(float(evidence.get('displacement_body_ratio', 0.0) or 0.0) >= 0.60)} "
            f"atr_normalized={_yes_no(confirmed)}"
        )
    if name == "market_structure_shift":
        return f"MSS_BOS={_yes_no(evidence.get('confirmed'))} detail={evidence.get('reason', 'opposing swing broken')}"
    if name in ("displacement_fvg", "displacement_fvg_or_order_block"):
        fvg = evidence.get("fvg") or {}
        block = evidence.get("order_block") or {}
        return (
            f"FVG_created_by_displacement={_yes_no(fvg)} type={fvg.get('type', 'none')} "
            f"timeframe={fvg.get('timeframe', 'none')} fresh={_yes_no(fvg.get('fresh'))} active={_yes_no(fvg.get('active'))} "
            f"OB_available={_yes_no(block)} accepted={','.join(evidence.get('accepted_models') or []) or 'none'}"
        )
    if name in ("true_order_block", "true_fvg_or_order_block"):
        block = evidence.get("order_block") or {}
        fvg = evidence.get("fvg") or {}
        return (
            f"true_FVG_or_OB_found={_yes_no(fvg or block)} "
            f"fvg={_yes_no(fvg)} ob={_yes_no(block)} "
            f"ob_type={block.get('type', 'none')} timeframe={block.get('timeframe', fvg.get('timeframe', 'none'))} "
            f"final_opposing_candle={_yes_no(block.get('final_opposing_candle'))} fresh={_yes_no(block.get('fresh') or fvg.get('fresh'))}"
        )
    if name == "premium_discount":
        return f"correct_premium_discount_zone={_yes_no(confirmed)}"
    if name == "opposing_liquidity_target":
        target = evidence.get("target") or {}
        return f"opposing_target_found={_yes_no(target)} source={target.get('source', 'none')} minimum_1_5R={_yes_no(confirmed)}"
    if name == "fvg_or_order_block_retracement":
        zone = evidence.get("zone") or {}
        return (
            f"retracement_type={zone.get('kind', 'none')} "
            f"nearest_25_50_75_level={zone.get('nearest_reference_level', 'none')} "
            f"retracement_touched={_yes_no(confirmed)} OTE_informational_only=yes"
        )
    if name == "lower_timeframe_confirmation":
        patterns = evidence.get("execution_patterns") or []
        return (
            f"M1_M5_confirmation={_yes_no(evidence.get('execution_confirmed'))} "
            f"patterns={','.join(patterns) if patterns else 'none'}"
        )
    if name == "market_order_execution":
        return f"market_order_ready={_yes_no(confirmed)}"
    return state.get("reason") or "no reasoning available"


def _advisory_reasoning(advisories: dict) -> str:
    smt = advisories.get("smt") or {}
    news = advisories.get("news") or {}
    return (
        f"SMT_pair={smt.get('pair') or 'none'} SMT_confirmed={_yes_no(smt.get('confirmed'))} SMT_direction={smt.get('direction') or 'none'} "
        f"SMT_reason={smt.get('reason') or 'no divergence'} | "
        f"news_allows_trade={_yes_no(news.get('allowed'))} news_status={news.get('status', 'unknown')}"
    )


def _trend_reasoning(advisories: dict) -> str:
    trend = advisories.get("trend") or {}
    return " ".join(
        f"{timeframe}={trend.get(timeframe, 'unknown')}"
        for timeframe in ("D1_context", "H1", "M15", "M5", "session")
    )


def _event_label(event: dict) -> str:
    if not isinstance(event, dict) or not event:
        return "none"
    name = event.get("event") or event.get("type") or "event"
    direction = event.get("direction") or "none"
    return f"{name}:{direction}"


def _liquidity_counts(liquidity: dict) -> dict:
    liquidity = liquidity if isinstance(liquidity, dict) else {}
    return {
        "EQH": len(liquidity.get("EQH") or []),
        "EQL": len(liquidity.get("EQL") or []),
    }


def _timeframe_validation(analysis: dict, key: str) -> dict:
    state = analysis.get(key) or {}
    structure = state.get("market_structure") or {}
    return {
        "timeframe": state.get("timeframe") or (analysis.get("timeframes") or {}).get(key) or key,
        "candles": len(state.get("recent_candles") or []),
        "swings": len(state.get("swings") or []),
        "fvgs": len(state.get("fvgs") or []),
        "order_blocks": len(state.get("order_blocks") or []),
        "liquidity": _liquidity_counts(state.get("liquidity") or state.get("external_liquidity") or {}),
        "trend": structure.get("trend") or state.get("trend") or "unknown",
        "bos": bool(structure.get("bos")),
        "mss": bool(structure.get("mss")),
        "choch": bool(structure.get("choch") or structure.get("choc") or structure.get("change_of_character")),
        "last_event": _event_label(structure.get("last_event") or {}),
        "windows": state.get("candle_window_lengths") or {},
    }


def _build_validation_snapshot(symbol: str, analysis: dict, setup: dict) -> dict:
    states = setup.get("states") or []
    failed = next((state for state in states if not state.get("confirmed")), None)
    failed_step = setup.get("failed_step") or (failed or {}).get("name")
    blocked = []
    if setup.get("strategy") != "kingsbalfx":
        observed = [state.get("name") for state in states]
        blocked = [name for name in SEQUENCE if name not in observed]
    liquidity = analysis.get("external_liquidity") or (analysis.get("HTF") or {}).get("external_liquidity") or {}
    return {
        "symbol": symbol,
        "strategy": setup.get("strategy") or "ict_state_machine",
        "price": analysis.get("price"),
        "timeframes": analysis.get("timeframes") or {},
        "candle_windows": analysis.get("candle_window_usage") or analysis.get("candle_windows") or {},
        "timeframe_data": {
            key: _timeframe_validation(analysis, key)
            for key in ("WEEKLY", "DAILY", "DAILY_CONTEXT", "HTF", "MTF", "LTF", "EXECUTION")
            if analysis.get(key)
        },
        "alignment": analysis.get("h1_m15_alignment") or (analysis.get("topdown") or {}).get("h1_m15_alignment") or {},
        "external_liquidity": _liquidity_counts(liquidity),
        "opening_gaps": analysis.get("opening_gaps") or (analysis.get("topdown") or {}).get("opening_gaps") or {},
        "visual_concepts": analysis.get("visual_concepts") or (analysis.get("topdown") or {}).get("visual_concepts") or {},
        "first_failed_step": failed_step,
        "first_failed_reason": setup.get("reason") or (failed or {}).get("reason"),
        "first_failed_evidence": (failed or {}).get("evidence") or {},
        "blocked_steps": blocked,
        "rules_reached": [state.get("name") for state in states],
        "rules_passed": sum(1 for state in states if state.get("confirmed")),
        "rules_total": int(setup.get("total_steps") or len(SEQUENCE)),
        "validation_rule": "Bot validates MT5 OHLC data and stops trading sequence at first failed mandatory gate; blocked later rules are not trade-valid until earlier gates pass.",
    }


def _gap_summary(gap: dict) -> str:
    if not isinstance(gap, dict) or not gap:
        return "missing"
    if not gap.get("available"):
        return f"unavailable:{gap.get('reason', 'no_data')}"
    return (
        f"{gap.get('direction', 'none')}"
        f"/active={_yes_no(gap.get('active'))}"
        f"/in_gap={_yes_no(gap.get('price_in_gap'))}"
        f"/filled={_yes_no(gap.get('filled'))}"
    )


def _console_validation_report(symbol: str, setup: dict) -> None:
    validation = setup.get("validation") or {}
    if not validation:
        return

    primary = setup.get("primary_ict_validation") or validation.get("primary_ict")
    if isinstance(primary, dict) and primary:
        primary_alignment = primary.get("alignment") or {}
        primary_liquidity = primary.get("external_liquidity") or {}
        primary_gaps = primary.get("opening_gaps") or {}
        LOGGER.info(
            "[%s] PRIMARY ICT VALIDATION | align_confirmed=%s mode=%s reason=%s | liq_EQH=%s liq_EQL=%s | NDOG=%s NWOG=%s | stopped_at=%s | reason=%s | blocked=%s",
            symbol,
            _yes_no(primary_alignment.get("confirmed")),
            primary_alignment.get("alignment_mode", "none"),
            primary_alignment.get("alignment_reason", "none"),
            primary_liquidity.get("EQH", 0),
            primary_liquidity.get("EQL", 0),
            _gap_summary(primary_gaps.get("NDOG") or {}),
            _gap_summary(primary_gaps.get("NWOG") or {}),
            primary.get("first_failed_step") or "none",
            primary.get("first_failed_reason") or "none",
            ",".join((primary.get("blocked_steps") or [])[:7]) if primary.get("blocked_steps") else "none",
        )

    alignment = validation.get("alignment") or {}
    gaps = validation.get("opening_gaps") or {}
    timeframe_data = validation.get("timeframe_data") or {}
    tf_parts = []
    for key in ("HTF", "MTF", "LTF", "EXECUTION"):
        item = timeframe_data.get(key) or {}
        if not item:
            continue
        tf_parts.append(
            f"{key}:{item.get('timeframe')} c={item.get('candles')} sw={item.get('swings')} "
            f"fvg={item.get('fvgs')} ob={item.get('order_blocks')} "
            f"trend={item.get('trend')} bos={_yes_no(item.get('bos'))} mss={_yes_no(item.get('mss'))} choch={_yes_no(item.get('choch'))} "
            f"event={item.get('last_event')}"
        )
    liquidity = validation.get("external_liquidity") or {}
    blocked = validation.get("blocked_steps") or []
    LOGGER.info(
        "[%s] VALIDATION PROOF | strategy=%s | data=%s | align_confirmed=%s mode=%s reason=%s | liq_EQH=%s liq_EQL=%s | NDOG=%s NWOG=%s | stopped_at=%s | reason=%s | blocked=%s",
        symbol,
        validation.get("strategy", "unknown"),
        " ; ".join(tf_parts) if tf_parts else "no_timeframe_data",
        _yes_no(alignment.get("confirmed")),
        alignment.get("alignment_mode", "none"),
        alignment.get("alignment_reason", "none"),
        liquidity.get("EQH", 0),
        liquidity.get("EQL", 0),
        _gap_summary(gaps.get("NDOG") or {}),
        _gap_summary(gaps.get("NWOG") or {}),
        validation.get("first_failed_step") or "none",
        validation.get("first_failed_reason") or "none",
        ",".join(blocked[:7]) if blocked else "none",
    )


def _console_state_report(symbol: str, setup: dict, safety: dict = None, request: dict = None) -> None:
    states = setup.get("states") or []
    passed = sum(1 for state in states if state.get("confirmed"))
    failed = sum(1 for state in states if not state.get("confirmed"))
    blocked = len(SEQUENCE) - len(states)
    LOGGER.info(
        "[%s] STATE MACHINE | direction=%s | PASSED=%s/%s FAILED=%s BLOCKED_NOT_CHECKED=%s",
        symbol,
        setup.get("direction") or "none",
        passed,
        len(SEQUENCE),
        failed,
        blocked,
    )
    LOGGER.info("[%s] TREND CONTEXT | %s", symbol, _trend_reasoning(setup.get("advisories") or {}))
    reached = {state.get("name"): state for state in states}
    for index, name in enumerate(SEQUENCE, start=1):
        state = reached.get(name)
        if state is None:
            LOGGER.info("[%s] STEP %02d/%02d BLOCKED | %s | NOT PASSED: earlier mandatory step failed", symbol, index, len(SEQUENCE), name)
            continue
        status = "PASS" if state.get("confirmed") else "FAIL"
        LOGGER.info(
            "[%s] STEP %02d/%02d %-4s | %s | %s",
            symbol,
            index,
            len(SEQUENCE),
            status,
            name,
            _state_reasoning(state),
        )
    LOGGER.info("[%s] ADVISORY | %s", symbol, _advisory_reasoning(setup.get("advisories") or {}))
    if setup.get("executable") and request:
        LOGGER.info("[%s] MANDATORY RESULT: 12/12 PASS | FINAL DECISION: SEND MARKET ORDER", symbol)
    elif setup.get("executable"):
        operational_reason = (safety or {}).get("reason") or ",".join((safety or {}).get("reasons") or []) or "operational validation rejected"
        LOGGER.info("[%s] MANDATORY RESULT: 12/12 PASS | FINAL DECISION: SKIP | operational_reason=%s", symbol, operational_reason)
    else:
        LOGGER.info(
            "[%s] MANDATORY RESULT: %s/12 PASS | FINAL DECISION: SKIP | failed_step=%s | reason=%s",
            symbol,
            passed,
            setup.get("failed_step"),
            setup.get("reason"),
        )
    if safety and (setup.get("executable") or not safety.get("approved", True)):
        checks = safety.get("checks") or {}
        failed_checks = ",".join(name for name, passed in checks.items() if not passed) or safety.get("reason") or "none"
        LOGGER.info("[%s] OPERATIONAL SKIP | failed_checks=%s", symbol, failed_checks)


def _console_compact_report(symbol: str, setup: dict, safety: dict = None, request: dict = None) -> None:
    states = setup.get("states") or []
    passed = sum(1 for state in states if state.get("confirmed"))
    total_steps = int(setup.get("total_steps") or len(SEQUENCE))
    failed_step = setup.get("failed_step") or "none"
    reason = (safety or {}).get("reason") or setup.get("reason") or "none"
    if setup.get("executable") and request:
        decision = "SEND_MARKET_ORDER"
    elif setup.get("executable"):
        decision = "OPERATIONAL_SKIP"
    else:
        decision = "SKIP"
    LOGGER.info(
        "[%s] RESULT | decision=%s | direction=%s | passed=%s/%s | failed_step=%s | reason=%s",
        symbol,
        decision,
        setup.get("direction") or "none",
        passed,
        total_steps,
        failed_step,
        reason,
    )


def _report_setup(symbol: str, setup: dict, safety: dict = None, request: dict = None) -> None:
    if _truthy("VALIDATION_LOGS", "true"):
        _console_validation_report(symbol, setup)
    if setup.get("strategy") == "kingsbalfx":
        _console_compact_report(symbol, setup, safety, request)
        return
    mode = os.getenv("STATE_LOG_MODE", "compact").strip().lower()
    if mode == "full":
        _console_state_report(symbol, setup, safety, request)
    elif mode == "none":
        if request:
            _console_compact_report(symbol, setup, safety, request)
    else:
        _console_compact_report(symbol, setup, safety, request)


def _console_skip(symbol: str, reason: str, evidence: dict = None) -> None:
    context = " ".join(f"{key}={value}" for key, value in (evidence or {}).items() if not isinstance(value, (dict, list, tuple)))
    LOGGER.info("[%s] SKIP | %s%s", symbol, reason, f" | {context}" if context else "")


def _launch_multi_account_children() -> bool:
    if not _truthy("MULTI_ACCOUNT_ENABLED") or _truthy("MULTI_ACCOUNT_CHILD"):
        return False
    import subprocess

    processes = []
    for index, account in enumerate(load_accounts()):
        env = os.environ.copy()
        env.update(
            {
                "MULTI_ACCOUNT_CHILD": "true",
                "BOT_ACCOUNT_INDEX": str(index),
                "BOT_ACCOUNT_ID": str(account.get("bot_id") or f"bot_acc_{index + 1}"),
                "MT5_ACCOUNT_LOGIN": str(account.get("login") or ""),
                "MT5_ACCOUNT_PASSWORD": str(account.get("password") or ""),
                "MT5_ACCOUNT_SERVER": str(account.get("server") or ""),
            }
        )
        if account.get("mt5_path"):
            env["MT5_PATH"] = str(account["mt5_path"])
            env["MT5_PORTABLE"] = "1"
        processes.append(
            subprocess.Popen(
                [sys.executable, str(Path(__file__).resolve())],
                cwd=str(Path(__file__).parent),
                env=env,
            )
        )
        time.sleep(max(2, int(os.getenv("MULTI_ACCOUNT_START_DELAY_SECONDS", "35"))))
    for process in processes:
        process.wait()
    return True


def _resolve_symbol(symbol: str):
    try:
        import MetaTrader5 as mt5
    except ImportError:
        return None
    for candidate in candidates_for(symbol):
        try:
            if mt5.symbol_select(candidate, True):
                tick = mt5.symbol_info_tick(candidate)
                if tick and float(tick.bid or 0.0) > 0:
                    return candidate
        except (AttributeError, RuntimeError, TypeError, ValueError):
            continue
    return None


def _csv_items(name: str):
    return [
        item.strip()
        for item in os.getenv(name, "").split(",")
        if item.strip()
    ]


def _symbol_matches(symbol: str, filters) -> bool:
    if not filters:
        return True
    normalized = _canonical_symbol(symbol)
    raw = str(symbol or "").upper()
    return any(item.upper() in (raw, normalized) or raw.startswith(item.upper()) for item in filters)


def _build_symbol_universe():
    stats = {
        "raw": 0,
        "accepted": 0,
        "unresolved": 0,
        "asset_filtered": 0,
        "allowlist_filtered": 0,
        "blocklist_filtered": 0,
        "duplicate_filtered": 0,
    }
    if _truthy("AUTO_EXTRACT_MT5_SYMBOLS"):
        groups = _csv_items("MT5_SYMBOL_GROUPS")
        limit_raw = os.getenv("MT5_SYMBOL_LIMIT", "").strip()
        raw_symbols = get_broker_symbols(
            include_hidden=_truthy("MT5_SYMBOL_INCLUDE_HIDDEN"),
            require_trade=_truthy("MT5_SYMBOL_REQUIRE_TRADE", "true"),
            require_tick=_truthy("MT5_SYMBOL_REQUIRE_TICK", "false"),
            group_masks=groups,
            limit=int(limit_raw) if limit_raw else None,
        )
        source = "mt5"
    else:
        env_symbols = _csv_items("SYMBOLS")
        raw_symbols = env_symbols or [
            str(item.get("symbol") if isinstance(item, dict) else item).strip()
            for item in TradingPairs.get_trading_pairs()
        ]
        source = "configured"

    stats["raw"] = len(raw_symbols)
    configured_assets = {item.lower() for item in _csv_items("MT5_SYMBOL_ASSET_CLASSES")}
    allowed_assets = set() if "all" in configured_assets else configured_assets
    allowlist = _csv_items("MT5_SYMBOL_ALLOWLIST")
    blocklist = _csv_items("MT5_SYMBOL_BLOCKLIST")
    resolved_symbols = []
    seen = set()
    for item in raw_symbols:
        symbol = item if source == "mt5" else _resolve_symbol(item)
        if not symbol:
            stats["unresolved"] += 1
            continue
        asset_class = infer_asset_class(symbol)
        if allowed_assets and asset_class not in allowed_assets:
            stats["asset_filtered"] += 1
            continue
        if allowlist and not _symbol_matches(symbol, allowlist):
            stats["allowlist_filtered"] += 1
            continue
        if blocklist and _symbol_matches(symbol, blocklist):
            stats["blocklist_filtered"] += 1
            continue
        if symbol in seen:
            stats["duplicate_filtered"] += 1
            continue
        seen.add(symbol)
        resolved_symbols.append(symbol)
    stats["accepted"] = len(resolved_symbols)
    stats["allowed_assets"] = ",".join(sorted(allowed_assets)) if allowed_assets else "all"
    stats["groups"] = ",".join(_csv_items("MT5_SYMBOL_GROUPS")) or "all"
    return resolved_symbols, source, stats


def _canonical_symbol(symbol: str) -> str:
    raw = str(symbol or "").upper().replace("/", "").replace("-", "").replace("_", "")
    known = (
        "XAUUSD", "XAGUSD", "EURUSD", "GBPUSD", "AUDUSD", "NZDUSD",
        "AUDCAD", "NZDCAD", "EURCAD", "GBPCAD", "USDJPY", "USDCHF",
        "EURAUD", "GBPAUD", "EURNZD", "GBPNZD", "EURCHF", "GBPCHF",
        "EURJPY", "GBPJPY", "AUDJPY", "NZDJPY", "AUDCHF", "NZDCHF",
        "BTCUSD", "ETHUSD", "NAS100", "US500", "DXY",
    )
    return next((name for name in known if raw.startswith(name)), raw)


def _correlated_symbols(symbol: str):
    return [item["symbol"] for item in correlated_markets(_canonical_symbol(symbol))]


def _smt_direction_from_analysis(analysis: dict) -> str:
    alignment = analysis.get("h1_m15_alignment") or (analysis.get("topdown") or {}).get("h1_m15_alignment") or {}
    direction = str(alignment.get("direction") or "").lower()
    if direction in ("buy", "sell", "bullish", "bearish"):
        return direction

    for value in (
        analysis.get("overall_trend"),
        (analysis.get("HTF") or {}).get("trend"),
        (analysis.get("topdown") or {}).get("h1_trend"),
    ):
        normalized = str(value or "").lower()
        if normalized in ("buy", "bullish", "long"):
            return "buy"
        if normalized in ("sell", "bearish", "short"):
            return "sell"
    return ""


def _killzone_active_from_analysis(analysis: dict) -> bool:
    session = analysis.get("session_analysis") or {}
    return bool(
        session.get("killzone_active")
        or session.get("london_killzone")
        or session.get("newyork_killzone")
    )


def _smt_snapshot(symbol: str, analysis: dict, trend: str) -> dict:
    from ict_concepts.smt import detect_smt

    related = correlated_markets(_canonical_symbol(symbol))
    if not related:
        return {"confirmed": False, "direction": None, "pair": None, "reason": "no configured SMT correlation"}

    def summary(candles):
        smt_window = _int_env("SMT_CANDLES", 20, minimum=10, maximum=50)
        recent = list(candles or [])[-smt_window:]
        if len(recent) < 10:
            raise ValueError("insufficient SMT candle window")
        midpoint = max(5, len(recent) // 2)
        previous = recent[:midpoint]
        current = recent[midpoint:]
        return {
            "high": max(float(candle["high"]) for candle in current),
            "low": min(float(candle["low"]) for candle in current),
            "prev_high": max(float(candle["high"]) for candle in previous),
            "prev_low": min(float(candle["low"]) for candle in previous),
            "timeframe": "M5",
            "candles_used": len(recent),
        }

    main_candles = analysis.get("m5_candles") or []
    smt_window = _int_env("SMT_CANDLES", 20, minimum=10, maximum=50)
    if len(main_candles) < 10:
        return {"confirmed": False, "direction": None, "pair": None, "reason": "insufficient primary M5 data"}

    checked = []
    for relationship in related:
        requested = relationship["symbol"]
        mode = relationship["mode"]
        correlated = _resolve_symbol(requested)
        pair_name = f"{_canonical_symbol(symbol)}/{requested}"
        if not correlated:
            checked.append(f"{pair_name}:unavailable")
            continue
        try:
            tick = get_tick_snapshot(correlated)
            other = analyze_market_top_down(correlated, (tick["bid"] + tick["ask"]) / 2.0)
            other_candles = other.get("m5_candles") or []
            if len(other_candles) < 10:
                checked.append(f"{pair_name}:insufficient_data")
                continue
            result = detect_smt(summary(main_candles), summary(other_candles), expected_direction=trend, correlation_mode=mode)
            result["pair"] = pair_name
            result["correlated_symbol"] = correlated
            result["candles_used"] = min(smt_window, len(main_candles), len(other_candles))
            result["reason"] = (
                f"{result.get('reason')} ({mode} correlation)"
                if result.get("confirmed")
                else f"{result.get('reason')} or direction not aligned ({mode} correlation)"
            )
            if result.get("confirmed"):
                return result
            checked.append(f"{pair_name}:no_divergence")
        except (KeyError, RuntimeError, TypeError, ValueError) as exc:
            checked.append(f"{pair_name}:error:{exc}")
    return {
        "confirmed": False,
        "direction": None,
        "pair": ",".join(item["symbol"] for item in related),
        "reason": "; ".join(checked) if checked else "correlated markets unavailable",
    }


def _risk_percent() -> float:
    return max(0.05, min(float(os.getenv("RISK_PER_TRADE", "1.0")), 2.0))


def _correlation_conflict(symbol: str, direction: str, positions: list) -> bool:
    correlated = _correlated_symbols(symbol)
    if not correlated:
        return False
    canonical_correlated = {_canonical_symbol(item) for item in correlated}
    return any(
        _canonical_symbol(position.get("symbol")) in canonical_correlated
        and str(position.get("direction") or "").lower() == direction
        for position in positions
    )


def _manage_open_positions() -> None:
    for position in get_open_positions() or []:
        ticket = position.get("ticket")
        if not ticket:
            continue
        try:
            symbol = position["symbol"]
            tick = get_tick_snapshot(symbol)
            current = tick["bid"] if position.get("direction") == "buy" else tick["ask"]
            analysis = analyze_market_top_down(symbol, current)
            action = manage_trade(
                {
                    "symbol": symbol,
                    "direction": position.get("direction"),
                    "entry": position.get("price"),
                    "sl": position.get("sl"),
                    "tp": position.get("tp"),
                    "lot": position.get("volume"),
                    "stage": position.get("stage", 0),
                },
                current,
                swings=(analysis.get("MTF") or {}).get("swings"),
                order_blocks=(analysis.get("MTF") or {}).get("order_blocks"),
                fvgs=(analysis.get("LTF") or {}).get("fvgs"),
                atr=float((analysis.get("HTF") or {}).get("atr", 0.0) or 0.0),
            )
            if not action:
                continue
            if action["action"] in ("move_sl", "trail"):
                modify_position(ticket, sl=action["sl"], tp=position.get("tp"))
            elif action["action"] == "partial_close":
                volume = float(position.get("volume", 0.0)) * float(action.get("percent", 0.5))
                if close_position(ticket, symbol, position.get("direction"), volume):
                    modify_position(ticket, sl=position.get("price"), tp=position.get("tp"))
        except (KeyError, RuntimeError, TypeError, ValueError) as exc:
            bot_log("management_error", f"[{position.get('symbol')}] {exc}", {"ticket": ticket})


def _friday_close() -> None:
    now = datetime.datetime.now(datetime.timezone.utc)
    close_hour = int(os.getenv("FRIDAY_CLOSE_HOUR_UTC", "16"))
    if now.weekday() != 4 or now.hour < close_hour:
        return
    for position in get_open_positions() or []:
        if infer_asset_class(position.get("symbol")) == "crypto" or not position.get("ticket"):
            continue
        close_position(position["ticket"], position["symbol"], position.get("direction"), position.get("volume", 0.0))


def _kingsbalfx_setup(result: dict) -> dict:
    raw_setup = result.get("setup") or {}
    evidence = raw_setup.get("evidence") or {}
    states = evidence.get("states") or []
    failed = next((state for state in states if not state.get("confirmed")), None)
    request = result.get("request") or {}
    return {
        "strategy": "kingsbalfx",
        "executable": bool(result.get("valid")),
        "direction": raw_setup.get("direction") or request.get("direction"),
        "mode": raw_setup.get("mode"),
        "reason": result.get("reason") or raw_setup.get("reason"),
        "failed_step": failed.get("name") if failed else None,
        "states": states,
        "total_steps": 6,
        "plan": {
            "entry": raw_setup.get("entry") or request.get("entry"),
            "sl": raw_setup.get("sl") or request.get("sl"),
            "tp": raw_setup.get("tp") or request.get("tp"),
            "rr": raw_setup.get("rr"),
        },
        "target": raw_setup.get("target"),
        "entry_zone": raw_setup.get("entry_zone"),
        "evidence": evidence,
        "raw": raw_setup,
    }


def _evaluate_kingsbalfx_fallback(symbol: str, direction: str, analysis: dict, tick: dict, account: dict, positions: list, ict_setup: dict = None):
    result = evaluate_kingsbalfx(
        symbol,
        direction,
        mt5_connector,
        analysis=analysis,
        tick=tick,
        account=account,
        risk_percent=_risk_percent(),
        minimum_rr=1.5,
    )
    fallback_setup = _kingsbalfx_setup(result)
    fallback_setup["primary_ict_skip"] = {
        "failed_step": (ict_setup or {}).get("failed_step"),
        "reason": (ict_setup or {}).get("reason"),
        "direction": (ict_setup or {}).get("direction"),
        "passed_steps": sum(1 for state in (ict_setup or {}).get("states", []) if state.get("confirmed")),
        "total_steps": len(SEQUENCE),
    }
    fallback_setup.setdefault("evidence", {})["primary_ict_skip"] = fallback_setup["primary_ict_skip"]
    if (ict_setup or {}).get("validation"):
        fallback_setup["primary_ict_validation"] = ict_setup["validation"]
        fallback_setup.setdefault("evidence", {})["primary_ict_validation"] = ict_setup["validation"]
    fallback_setup["validation"] = _build_validation_snapshot(symbol, analysis, fallback_setup)
    if fallback_setup.get("primary_ict_validation"):
        fallback_setup["validation"]["primary_ict"] = fallback_setup["primary_ict_validation"]
    request = result.get("request")
    if not request:
        return None, fallback_setup, {"reason": result.get("reason") or "kingsbalfx_rejected"}

    identity = setup_identity(symbol, request["direction"], request.get("identity_context"))
    if not can_trade(symbol, identity, cooldown=int(os.getenv("SETUP_COOLDOWN_SECONDS", "1800"))):
        fallback_setup["executable"] = True
        return None, fallback_setup, {"reason": "duplicate_setup"}

    safe, safety = validate_execution_safety(
        symbol,
        request["direction"],
        request["entry"],
        request["sl"],
        request["tp"],
        request["lot"],
        account,
        positions,
    )
    if not safe:
        fallback_setup["executable"] = True
        return None, fallback_setup, safety

    request["identity"] = identity
    request["strategy"] = "kingsbalfx"
    return request, fallback_setup, safety


def _evaluate_symbol(symbol: str, account: dict, positions: list):
    tick = get_tick_snapshot(symbol)
    price = (tick["bid"] + tick["ask"]) / 2.0
    analysis = analyze_market_top_down(symbol, price)
    smt_direction = _smt_direction_from_analysis(analysis)
    try:
        smt = _smt_snapshot(symbol, analysis, smt_direction or analysis.get("overall_trend"))
    except Exception as exc:
        smt = {"confirmed": False, "direction": None, "reason": f"SMT unavailable: {exc}"}
    killzone_active = _killzone_active_from_analysis(analysis)
    setup = evaluate_strategy(symbol, price, analysis, smt=smt, killzone_active=killzone_active)
    try:
        news_allowed = news_allows_trade(symbol)
        news = {"allowed": news_allowed, "status": "clear" if news_allowed else "high-impact or manual news block"}
    except Exception as exc:
        news = {"allowed": False, "status": f"news check unavailable: {exc}"}
    topdown = analysis.get("topdown") or {}
    setup["advisories"] = {
        "smt": smt,
        "news": news,
        "trend": {
            "D1_context": (topdown.get("previous_day_context") or {}).get("previous_day_direction", "unknown"),
            "H1": topdown.get("h1_trend", "unknown"),
            "M15": topdown.get("m15_trend") or topdown.get("m30_trend", "unknown"),
            "M5": topdown.get("execution_trend", "unknown"),
            "session": (analysis.get("session_analysis") or {}).get("session", "unknown"),
        },
        "visual_concepts": analysis.get("visual_concepts") or {},
    }
    setup["validation"] = _build_validation_snapshot(symbol, analysis, setup)
    observed = tuple(state["name"] for state in setup.get("states", []))
    if observed != SEQUENCE[: len(observed)]:
        raise RuntimeError(f"State sequence violated: {observed}")
    if not setup["executable"]:
        LOGGER.info("[%s] ICT SKIP -> KINGSBALFX FALLBACK | failed_step=%s | reason=%s", symbol, setup.get("failed_step"), setup.get("reason"))
        fallback_request, fallback_setup, fallback_safety = _evaluate_kingsbalfx_fallback(
            symbol,
            setup.get("direction") or setup.get("trend") or analysis.get("overall_trend"),
            analysis,
            tick,
            account,
            positions,
            setup,
        )
        if fallback_request:
            return fallback_request, fallback_setup, fallback_safety
        return None, fallback_setup, fallback_safety

    plan = setup["plan"]
    direction = setup["direction"]
    entry = tick["ask"] if direction == "buy" else tick["bid"]
    sl = float(plan["sl"])
    tp = float(plan["tp"])
    risk = abs(entry - sl)
    reward = abs(tp - entry)
    if risk <= 0 or reward < risk * 1.5:
        return None, setup, {"reason": "live_market_price_no_longer_provides_1.5R"}
    risk_amount = float(account["balance"]) * (_risk_percent() / 100.0)
    volume = calculate_volume_for_risk(symbol, entry, sl, risk_amount)
    if volume <= 0:
        return None, setup, {"reason": "broker_minimum_volume_exceeds_risk"}

    identity = setup_identity(symbol, direction, setup.get("retracement"))
    if not can_trade(symbol, identity, cooldown=int(os.getenv("SETUP_COOLDOWN_SECONDS", "1800"))):
        return None, setup, {"reason": "duplicate_setup"}
    safe, safety = validate_execution_safety(symbol, direction, entry, sl, tp, volume, account, positions)
    if not safe:
        return None, setup, safety
    return {
        "symbol": symbol,
        "direction": direction,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "lot": volume,
        "order_type": "market",
        "identity": identity,
    }, setup, safety


def _evaluate_symbol_safe(symbol: str, account: dict, positions: list) -> dict:
    try:
        request, setup, safety = _evaluate_symbol(symbol, account, positions)
        return {
            "symbol": symbol,
            "request": request,
            "setup": setup,
            "safety": safety,
            "error": None,
            "trace": None,
        }
    except (KeyError, RuntimeError, TypeError, ValueError) as exc:
        return {
            "symbol": symbol,
            "request": None,
            "setup": None,
            "safety": None,
            "error": str(exc),
            "trace": traceback.format_exc(),
        }


def _process_scan_result(result: dict, max_trades: int) -> dict:
    symbol = result["symbol"]
    if result["error"]:
        bot_log("symbol_error", f"[{symbol}] evaluation failed: {result['error']}", {"trace": result["trace"]})
        return {"evaluated": 1, "trades_opened": 0, "errors": 1}

    request = result["request"]
    setup = result["setup"]
    safety = result["safety"]
    _report_setup(symbol, setup, safety, request)
    if not request:
        bot_log("setup_observed", f"[{symbol}] skipped: {safety.get('reason') or setup.get('reason')}", {"setup": setup, "safety": safety}, persist=False)
        return {"evaluated": 1, "trades_opened": 0, "errors": 0}

    positions = get_open_positions() or []
    if len(positions) >= max_trades:
        _console_skip(symbol, "max_open_trades_reached_before_execution", {"open_positions": len(positions), "max_trades": max_trades})
        return {"evaluated": 1, "trades_opened": 0, "errors": 0}
    trade = execute_trade(
        request["symbol"],
        request["direction"],
        request["lot"],
        request["sl"],
        request["tp"],
        request["order_type"],
        request["entry"],
    )
    if not trade:
        _console_skip(symbol, "broker_rejected_or_failed_market_order", request)
        return {"evaluated": 1, "trades_opened": 0, "errors": 0}
    register_trade(symbol, request["identity"])
    payload = {**request, "state_machine": setup, "status": "open"}
    persist_signal_to_supabase(payload)
    push_trade(payload)
    strategy_name = request.get("strategy") or "ict_state_machine"
    if strategy_name == "kingsbalfx":
        bot_log("trade_opened", f"[{symbol}] Kingsbalfx fallback confirmed and trade opened", payload)
    else:
        bot_log("trade_opened", f"[{symbol}] strict ICT sequence confirmed and trade opened", payload)
    return {"evaluated": 1, "trades_opened": 1, "errors": 0}


def run_bot() -> None:
    if _launch_multi_account_children():
        return
    start_in_thread()
    connected = connect()
    set_connection(connected)
    if not connected:
        raise RuntimeError("Unable to connect to MT5")

    max_trades = get_profile_max_trades(get_user_profile())
    symbols, symbol_source, symbol_stats = _build_symbol_universe()
    LOGGER.info(
        "ICT state-machine bot started | symbols=%s | symbol_source=%s | raw_symbols=%s | max_trades=%s",
        len(symbols),
        symbol_source,
        symbol_stats.get("raw"),
        max_trades,
    )
    LOGGER.info(
        "SYMBOL UNIVERSE | source=%s | raw=%s | accepted=%s | unresolved=%s | asset_filtered=%s | allowlist_filtered=%s | blocklist_filtered=%s | duplicate_filtered=%s | allowed_assets=%s | groups=%s",
        symbol_source,
        symbol_stats.get("raw"),
        symbol_stats.get("accepted"),
        symbol_stats.get("unresolved"),
        symbol_stats.get("asset_filtered"),
        symbol_stats.get("allowlist_filtered"),
        symbol_stats.get("blocklist_filtered"),
        symbol_stats.get("duplicate_filtered"),
        symbol_stats.get("allowed_assets"),
        symbol_stats.get("groups"),
    )

    while is_running():
        try:
            if consume_restart_request():
                connected = reconnect()
                set_connection(connected)
                if not connected:
                    time.sleep(30)
                    continue
            account = get_account_snapshot()
            persist_account_snapshot_to_supabase(account)
            positions = get_open_positions() or []
            update_metrics(account=account, open_positions=len(positions))
            LOGGER.info(
                "SCAN START | balance=%s | equity=%s | open_positions=%s/%s | symbols=%s",
                account.get("balance"),
                account.get("equity"),
                len(positions),
                max_trades,
                len(symbols),
            )
            _manage_open_positions()
            _friday_close()

            evaluated = 0
            skipped_closed = 0
            skipped_friday = 0
            trades_opened = 0
            errors = 0
            scan_candidates = []
            log_symbol_skips = _truthy("SYMBOL_SKIP_LOGS", "false")

            positions = get_open_positions() or []
            if len(positions) >= max_trades:
                LOGGER.info("SCAN STOP | max open trades reached: %s/%s", len(positions), max_trades)

            for symbol in symbols:
                if len(positions) >= max_trades or not is_running():
                    break
                asset_class = infer_asset_class(symbol)
                if not asset_trading_open(asset_class):
                    skipped_closed += 1
                    if log_symbol_skips:
                        _console_skip(symbol, "asset_market_closed", {"asset_class": asset_class})
                    continue
                if not friday_entry_allowed(asset_class):
                    skipped_friday += 1
                    if log_symbol_skips:
                        _console_skip(symbol, "friday_entry_cutoff", {"asset_class": asset_class})
                    continue
                scan_candidates.append(symbol)

            batch_size = _int_env("SCAN_BATCH_SIZE", 25, minimum=1)
            batch_pause = _float_env("SCAN_BATCH_PAUSE_SECONDS", 0.0, minimum=0.0, maximum=60.0)
            scan_workers = _int_env("SCAN_WORKERS", 1, minimum=1, maximum=8)
            log_evaluating = _truthy("SYMBOL_EVALUATION_LOGS", "false")
            batch_count = (len(scan_candidates) + batch_size - 1) // batch_size if scan_candidates else 0
            LOGGER.info(
                "SCAN CANDIDATES | universe=%s | candidates=%s | skipped_market_closed=%s | skipped_friday_cutoff=%s | batch_size=%s | workers=%s",
                len(symbols),
                len(scan_candidates),
                skipped_closed,
                skipped_friday,
                batch_size,
                scan_workers,
            )

            for batch_index, batch in _chunks(scan_candidates, batch_size):
                if not is_running():
                    break
                positions = get_open_positions() or []
                if len(positions) >= max_trades:
                    LOGGER.info("SCAN STOP | max open trades reached: %s/%s", len(positions), max_trades)
                    break

                LOGGER.info(
                    "BATCH START | batch=%s/%s | symbols=%s | workers=%s",
                    batch_index,
                    batch_count,
                    len(batch),
                    scan_workers,
                )
                if scan_workers == 1:
                    for symbol in batch:
                        if log_evaluating:
                            LOGGER.info("[%s] EVALUATING", symbol)
                        counts = _process_scan_result(_evaluate_symbol_safe(symbol, account, positions), max_trades)
                        evaluated += counts["evaluated"]
                        trades_opened += counts["trades_opened"]
                        errors += counts["errors"]
                else:
                    results = []
                    with ThreadPoolExecutor(max_workers=scan_workers) as executor:
                        futures = {
                            executor.submit(_evaluate_symbol_safe, symbol, account, positions): symbol
                            for symbol in batch
                        }
                        for future in as_completed(futures):
                            results.append(future.result())
                    for result in results:
                        counts = _process_scan_result(result, max_trades)
                        evaluated += counts["evaluated"]
                        trades_opened += counts["trades_opened"]
                        errors += counts["errors"]

                LOGGER.info(
                    "BATCH COMPLETE | batch=%s/%s | evaluated_total=%s | trades_opened=%s | errors=%s",
                    batch_index,
                    batch_count,
                    evaluated,
                    trades_opened,
                    errors,
                )
                if batch_pause > 0 and batch_index < batch_count:
                    time.sleep(batch_pause)
            LOGGER.info(
                "SCAN SUMMARY | universe=%s | candidates=%s | evaluated=%s | trades_opened=%s | errors=%s | skipped_market_closed=%s | skipped_friday_cutoff=%s",
                len(symbols),
                len(scan_candidates),
                evaluated,
                trades_opened,
                errors,
                skipped_closed,
                skipped_friday,
            )
            LOGGER.info("SCAN COMPLETE | sleeping=%ss", max(15, int(os.getenv("SCAN_INTERVAL_SECONDS", "60"))))
            time.sleep(max(15, int(os.getenv("SCAN_INTERVAL_SECONDS", "60"))))
        except KeyboardInterrupt:
            return
        except (ConnectionError, RuntimeError, TypeError, ValueError) as exc:
            LOGGER.error("Loop error: %s", exc)
            LOGGER.debug(traceback.format_exc())
            time.sleep(30)


if __name__ == "__main__":
    run_bot()
