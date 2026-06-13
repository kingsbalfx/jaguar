"""Live ICT state-machine orchestrator."""

import datetime
import logging
import os
import sys
import time
import traceback
from pathlib import Path

from dotenv import load_dotenv

from bot_api import start_in_thread
from bot_state import consume_restart_request, is_running, set_connection, update_metrics
from config.symbol_mappings import candidates_for
from config.smt_correlations import correlated_markets
from config.trading_pairs import TradingPairs
from dashboard.bridge import persist_account_snapshot_to_supabase, persist_signal_to_supabase, push_trade
from execution.mt5_connector import (
    calculate_volume_for_risk,
    connect,
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
        return f"D1={evidence.get('D1', 'unknown')} H4={evidence.get('H4', 'unknown')} agreement={_yes_no(confirmed)}"
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
    if name == "displacement_fvg":
        fvg = evidence.get("fvg") or {}
        return (
            f"FVG_created_by_displacement={_yes_no(fvg)} type={fvg.get('type', 'none')} "
            f"timeframe={fvg.get('timeframe', 'none')} fresh={_yes_no(fvg.get('fresh'))} active={_yes_no(fvg.get('active'))}"
        )
    if name == "true_order_block":
        block = evidence.get("order_block") or {}
        return (
            f"true_OB_found={_yes_no(block)} type={block.get('type', 'none')} timeframe={block.get('timeframe', 'none')} "
            f"final_opposing_candle={_yes_no(block.get('final_opposing_candle'))} fresh={_yes_no(block.get('fresh'))}"
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
        for timeframe in ("D1", "H4", "H1", "M15", "M5")
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


def _smt_snapshot(symbol: str, analysis: dict, trend: str) -> dict:
    from ict_concepts.smt import detect_smt

    related = correlated_markets(_canonical_symbol(symbol))
    if not related:
        return {"confirmed": False, "direction": None, "pair": None, "reason": "no configured SMT correlation"}

    def summary(candles):
        return {
            "high": max(float(candle["high"]) for candle in candles[-5:]),
            "low": min(float(candle["low"]) for candle in candles[-5:]),
            "prev_high": max(float(candle["high"]) for candle in candles[-10:-5]),
            "prev_low": min(float(candle["low"]) for candle in candles[-10:-5]),
            "timeframe": "M5",
        }

    main_candles = analysis.get("m5_candles") or []
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


def _evaluate_symbol(symbol: str, account: dict, positions: list):
    tick = get_tick_snapshot(symbol)
    price = (tick["bid"] + tick["ask"]) / 2.0
    analysis = analyze_market_top_down(symbol, price)
    setup = evaluate_strategy(symbol, price, analysis)
    try:
        smt = _smt_snapshot(symbol, analysis, setup.get("trend") or analysis.get("overall_trend"))
    except Exception as exc:
        smt = {"confirmed": False, "direction": None, "reason": f"SMT unavailable: {exc}"}
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
            "D1": topdown.get("daily_trend", "unknown"),
            "H4": topdown.get("h4_trend", "unknown"),
            "H1": topdown.get("h1_trend", "unknown"),
            "M15": topdown.get("m15_trend", "unknown"),
            "M5": topdown.get("execution_trend", "unknown"),
        },
    }
    observed = tuple(state["name"] for state in setup.get("states", []))
    if observed != SEQUENCE[: len(observed)]:
        raise RuntimeError(f"State sequence violated: {observed}")
    if not setup["executable"]:
        return None, setup, {"reason": setup["reason"]}

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


def run_bot() -> None:
    if _launch_multi_account_children():
        return
    start_in_thread()
    connected = connect()
    set_connection(connected)
    if not connected:
        raise RuntimeError("Unable to connect to MT5")

    max_trades = get_profile_max_trades(get_user_profile())
    configured = [str(item.get("symbol") if isinstance(item, dict) else item).strip() for item in TradingPairs.get_trading_pairs()]
    symbols = [resolved for item in configured if item for resolved in [_resolve_symbol(item)] if resolved]
    LOGGER.info("ICT state-machine bot started | symbols=%s | max_trades=%s", len(symbols), max_trades)

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

            for symbol in symbols:
                positions = get_open_positions() or []
                if len(positions) >= max_trades:
                    LOGGER.info("SCAN STOP | max open trades reached: %s/%s", len(positions), max_trades)
                    break
                if not is_running():
                    break
                asset_class = infer_asset_class(symbol)
                if not asset_trading_open(asset_class):
                    _console_skip(symbol, "asset_market_closed", {"asset_class": asset_class})
                    continue
                if not friday_entry_allowed(asset_class):
                    _console_skip(symbol, "friday_entry_cutoff", {"asset_class": asset_class})
                    continue
                try:
                    LOGGER.info("[%s] EVALUATING", symbol)
                    request, setup, safety = _evaluate_symbol(symbol, account, positions)
                    _console_state_report(symbol, setup, safety, request)
                    if not request:
                        bot_log("setup_observed", f"[{symbol}] skipped: {safety.get('reason') or setup.get('reason')}", {"setup": setup, "safety": safety}, persist=False)
                        continue
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
                        continue
                    register_trade(symbol, request["identity"])
                    payload = {**request, "state_machine": setup, "status": "open"}
                    persist_signal_to_supabase(payload)
                    push_trade(payload)
                    bot_log("trade_opened", f"[{symbol}] strict ICT sequence confirmed and trade opened", payload)
                except (KeyError, RuntimeError, TypeError, ValueError) as exc:
                    bot_log("symbol_error", f"[{symbol}] evaluation failed: {exc}", {"trace": traceback.format_exc()})
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
