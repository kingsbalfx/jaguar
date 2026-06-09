"""Live unified ICT trading bot.

Strategy confirmations are soft-scored. Operational and account-risk checks are
hard gates. The same unified evaluator is designed for live and backtest use.
"""

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
from execution.order_router import choose_entry_price, choose_order_type
from execution.pre_trade_validator import validate_execution_safety
from execution.trade_executor import close_position, execute_trade, modify_position
from fundamentals.news_filter import news_allows_trade
from multi_account_runner import load_accounts
from risk.protection import can_trade, register_trade, setup_identity
from risk.profitability_guard import normalize_rr_after_sl_adjustment
from risk.trade_management import manage_trade
from strategy.execution_planner import plan_execution
from strategy.pre_trade_analysis import analyze_market_top_down
from strategy.unified_ict_engine import evaluate_unified_setup
from utils.logger import bot_log
from utils.sessions import asset_trading_open, in_london_session, in_newyork_session
from utils.symbol_profile import infer_asset_class
from utils.user_profiles import get_profile_max_trades, get_user_profile


load_dotenv()
logger = logging.getLogger("unified_ict_bot")
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    logger.addHandler(handler)
logger.setLevel(getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO))


def _truthy(name, default="false"):
    return os.getenv(name, default).lower() in ("1", "true", "yes", "on")


def _launch_multi_account_children():
    if not _truthy("MULTI_ACCOUNT_ENABLED") or _truthy("MULTI_ACCOUNT_CHILD"):
        return False
    import subprocess

    accounts = load_accounts()
    processes = []
    for index, account in enumerate(accounts):
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
        processes.append(subprocess.Popen([sys.executable, str(Path(__file__).resolve())], cwd=str(Path(__file__).parent), env=env))
        time.sleep(max(2, int(os.getenv("MULTI_ACCOUNT_START_DELAY_SECONDS", "35"))))
    for process in processes:
        process.wait()
    return True


def _resolve_symbol(symbol):
    try:
        import MetaTrader5 as mt5
    except Exception:
        return None
    for candidate in candidates_for(symbol):
        try:
            if mt5.symbol_select(candidate, True):
                tick = mt5.symbol_info_tick(candidate)
                if tick and float(tick.bid or 0.0) > 0:
                    return candidate
        except Exception:
            continue
    return None


def _correlated_symbol(symbol):
    pairs = {
        "EURUSD": "GBPUSD",
        "GBPUSD": "EURUSD",
        "AUDUSD": "NZDUSD",
        "NZDUSD": "AUDUSD",
        "XAUUSD": "XAGUSD",
        "XAGUSD": "XAUUSD",
        "BTCUSD": "ETHUSD",
        "ETHUSD": "BTCUSD",
        "NAS100": "US500",
        "US500": "NAS100",
    }
    raw = str(symbol or "").upper().replace("/", "").replace("-", "").replace("_", "")
    canonical = next((name for name in pairs if raw.startswith(name)), raw)
    return pairs.get(canonical)


def _smt_snapshot(symbol, analysis, trend):
    from ict_concepts.smt import detect_smt

    correlated = _correlated_symbol(symbol)
    if not correlated:
        return {"confirmed": False, "direction": None, "reason": "no_pair"}
    correlated = _resolve_symbol(correlated)
    if not correlated:
        return {"confirmed": False, "direction": None, "reason": "pair_unavailable"}
    try:
        tick = get_tick_snapshot(correlated)
        other = analyze_market_top_down(correlated, (tick["bid"] + tick["ask"]) / 2.0)
        main_candles = analysis.get("m5_candles") or []
        other_candles = other.get("m5_candles") or []
        if len(main_candles) < 10 or len(other_candles) < 10:
            return {"confirmed": False, "direction": None, "reason": "insufficient_data"}

        def summarize(candles):
            return {
                "high": max(float(c["high"]) for c in candles[-5:]),
                "low": min(float(c["low"]) for c in candles[-5:]),
                "prev_high": max(float(c["high"]) for c in candles[-10:-5]),
                "prev_low": min(float(c["low"]) for c in candles[-10:-5]),
                "timeframe": "M5",
            }

        return detect_smt(summarize(main_candles), summarize(other_candles), expected_direction=trend)
    except Exception as exc:
        return {"confirmed": False, "direction": None, "reason": str(exc)}


def _position_risk_percent():
    return max(0.05, min(float(os.getenv("RISK_PER_TRADE", "1.0")), 2.0))


def _manage_open_positions():
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
                },
                current,
                swings=(analysis.get("MTF") or {}).get("swings"),
                order_blocks=(analysis.get("MTF") or {}).get("order_blocks"),
                fvgs=(analysis.get("LTF") or {}).get("fvgs"),
            )
            if not action:
                continue
            if action["action"] in ("move_sl", "trail"):
                modify_position(ticket, sl=action["sl"], tp=position.get("tp"))
            elif action["action"] == "partial_close":
                close_position(ticket, symbol, position.get("direction"), max(0.0, float(position.get("volume", 0.0)) * float(action.get("percent", 0.5))))
                modify_position(ticket, sl=position.get("price"), tp=0.0)
        except Exception as exc:
            bot_log("management_error", f"[{position.get('symbol')}] management error: {exc}", {"ticket": ticket})


def _friday_close():
    now = datetime.datetime.now(datetime.timezone.utc)
    if not (now.weekday() == 4 and now.hour >= int(os.getenv("FRIDAY_CLOSE_HOUR_UTC", "16"))):
        return
    for position in get_open_positions() or []:
        if infer_asset_class(position.get("symbol")) == "crypto" or not position.get("ticket"):
            continue
        close_position(position["ticket"], position["symbol"], position.get("direction"), position.get("volume", 0.0))


def _evaluate_symbol(symbol, account, open_positions):
    tick = get_tick_snapshot(symbol)
    price = (tick["bid"] + tick["ask"]) / 2.0
    analysis = analyze_market_top_down(symbol, price)
    trend = analysis.get("overall_trend")
    smt = _smt_snapshot(symbol, analysis, trend)
    setup = evaluate_unified_setup(
        symbol,
        price,
        analysis,
        smt=smt,
        killzone_active=in_london_session() or in_newyork_session(),
    )
    if setup.get("execution_route") == "observe":
        return None, setup, {"reason": "setup_score_below_live_threshold"}
    direction = setup["direction"]
    features = {
        "atr": float((analysis.get("HTF") or {}).get("atr", 0.0) or 0.0),
    }
    plan = plan_execution(symbol, direction, price, features, analysis)
    entry = choose_entry_price(price, setup.get("retracement"), direction)
    order_type = choose_order_type(
        price=price,
        fvg=(setup.get("retracement") or {}).get("fvg"),
        direction=direction,
        candles=analysis.get("m5_candles"),
        mode=os.getenv("ORDER_ROUTING_MODE", "auto"),
        entry_price=entry,
    )
    if order_type == "market":
        entry = tick["ask"] if direction == "buy" else tick["bid"]
    sl = float(plan["sl"])
    tp = float(plan["tp"])
    sl, tp, _ = normalize_rr_after_sl_adjustment(direction, entry, sl, tp)
    risk_amount = float(account["balance"]) * (_position_risk_percent() / 100.0) * float(setup["risk_multiplier"])
    volume = calculate_volume_for_risk(symbol, entry, sl, risk_amount)
    if volume <= 0:
        return None, setup, {"reason": "broker_minimum_volume_exceeds_risk"}
    identity = setup_identity(symbol, direction, setup.get("retracement"))
    if not can_trade(symbol, identity, cooldown=int(os.getenv("SETUP_COOLDOWN_SECONDS", "1800"))):
        return None, setup, {"reason": "duplicate_setup"}
    safe, safety = validate_execution_safety(symbol, direction, entry, sl, tp, volume, account, open_positions)
    if not safe:
        return None, setup, safety
    trade_request = {
        "symbol": symbol,
        "direction": direction,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "lot": volume,
        "order_type": order_type,
        "identity": identity,
    }
    return trade_request, setup, safety


def run_bot():
    if _launch_multi_account_children():
        return
    start_in_thread()
    credentials = None
    login = os.getenv("MT5_ACCOUNT_LOGIN")
    if login:
        credentials = {"login": login, "password": os.getenv("MT5_ACCOUNT_PASSWORD"), "server": os.getenv("MT5_ACCOUNT_SERVER")}
    connect(credentials)
    set_connection(True)
    max_trades = get_profile_max_trades(get_user_profile())
    configured = [str(item.get("symbol") if isinstance(item, dict) else item).strip() for item in TradingPairs.get_trading_pairs()]
    symbols = [resolved for item in configured if item for resolved in [_resolve_symbol(item)] if resolved]
    logger.info("Unified ICT bot started | symbols=%s | max_trades=%s", len(symbols), max_trades)

    while is_running():
        try:
            if consume_restart_request():
                reconnect(credentials)
            account = get_account_snapshot()
            if not account:
                reconnect(credentials)
                time.sleep(20)
                continue
            open_positions = get_open_positions() or []
            update_metrics(
                open_positions=len(open_positions),
                floating_profit=sum(float(pos.get("profit", 0.0)) for pos in open_positions),
                balance=account.get("balance"),
                equity=account.get("equity"),
                margin_free=account.get("margin_free"),
                symbols=symbols,
            )
            persist_account_snapshot_to_supabase(account)
            _friday_close()
            _manage_open_positions()
            if len(open_positions) >= max_trades:
                time.sleep(60)
                continue

            for symbol in symbols:
                if len(get_open_positions() or []) >= max_trades or not is_running():
                    break
                asset_class = infer_asset_class(symbol)
                if not asset_trading_open(asset_class):
                    continue
                if asset_class != "crypto" and not news_allows_trade(symbol):
                    continue
                try:
                    request, setup, safety = _evaluate_symbol(symbol, account, get_open_positions() or [])
                    if not request:
                        bot_log("setup_observed", f"[{symbol}] {setup.get('reason')}", {"setup": setup, "safety": safety})
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
                        continue
                    register_trade(symbol, request["identity"])
                    payload = {**request, "confidence": setup["confidence"], "reason": setup, "status": "open"}
                    persist_signal_to_supabase(payload)
                    push_trade(payload)
                    bot_log("trade_opened", f"[{symbol}] {setup['execution_route']} trade opened at {setup['confidence']}/100", payload)
                except Exception as exc:
                    bot_log("symbol_error", f"[{symbol}] evaluation failed: {exc}", {"trace": traceback.format_exc()})
            time.sleep(max(15, int(os.getenv("SCAN_INTERVAL_SECONDS", "60"))))
        except KeyboardInterrupt:
            break
        except Exception as exc:
            logger.error("Loop error: %s", exc)
            traceback.print_exc()
            time.sleep(30)


if __name__ == "__main__":
    run_bot()
