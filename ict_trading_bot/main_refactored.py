# =====================================================
# PURE RULE-BASED ICT & SMT TRADING BOT
# =====================================================
# This is the REFACTORED main.py that runs ONLY:
# - 7 Mandatory ICT Core Rules
# - SMT Divergence Validation (Advisory)
# - Deterministic Position Sizing
# - Clean, Auditable Decision Trail
# =====================================================

from dotenv import load_dotenv
import sys
import os
import time
import traceback
import datetime
import logging
from pathlib import Path

# =====================================================
# CORE DEPENDENCIES
# =====================================================
from config.trading_pairs import TradingPairs
from execution.mt5_connector import (
    connect,
    reconnect,
    ensure_symbol,
    get_price,
    get_open_positions,
    get_account_snapshot,
)
from multi_account_runner import load_accounts
from utils.symbol_profile import (
    LIQUID_FOREX,
    LIQUID_METALS,
    LIQUID_CRYPTO,
    infer_asset_class,
)
from utils.user_profiles import (
    get_user_profile,
    get_profile_max_trades,
)
from utils.logger import bot_log
from config.symbol_mappings import candidates_for
from execution.trade_executor import execute_trade
from execution.order_router import choose_order_type

# =====================================================
# PURE RULE-BASED SYSTEM (NEW)
# =====================================================
from strategy.pure_rule_based_engine import PureRuleBasedEngine
from risk.rule_based_risk_manager import RuleBasedRiskManager, RuleBasedRiskParams

# =====================================================
# MINIMAL DEPENDENCIES (Market Data Only)
# =====================================================
from strategy.pre_trade_analysis import analyze_market_top_down
from strategy.entry_model import hybrid_entry_model
from risk.sl_tp_engine import calculate_sl_tp
from risk.protection import can_trade, register_trade
from risk.correlation_manager import get_pair_correlation_risk
from fundamentals.news_filter import news_allows_trade
from utils.sessions import in_london_session, in_newyork_session, trading_session_open, asset_trading_open

# =====================================================
# PORTFOLIO & DASHBOARD
# =====================================================
from portfolio.allocator import allocate_risk
from dashboard.bridge import (
    push_trade,
    persist_signal_to_supabase,
    persist_log_to_supabase,
    persist_account_snapshot_to_supabase,
)
from bot_state import (
    is_running,
    consume_restart_request,
    set_connection,
    update_metrics,
    append_log,
)

load_dotenv()

# =====================================================
# CLEANUP STALE LOCKS
# =====================================================
def cleanup_stale_locks():
    data_dir = Path(__file__).resolve().parent / "data"
    if data_dir.exists():
        for lock_file in data_dir.glob("*.lock"):
            try:
                lock_file.unlink()
                print(f"[SYSTEM] Cleaned up stale lock: {lock_file.name}")
            except: pass
cleanup_stale_locks()

# =====================================================
# MULTI-ACCOUNT SETUP
# =====================================================
if (
    os.getenv("MULTI_ACCOUNT_ENABLED", "false").lower() in ("1", "true", "yes", "on")
    and os.getenv("MULTI_ACCOUNT_CHILD", "false").lower() not in ("1", "true", "yes", "on")
):
    import subprocess
    from multiprocessing import Process
    
    accounts = load_accounts()
    print(f"[MULTI] {len(accounts)} accounts detected. Spawning child processes...")
    processes = []
    script_path = Path(__file__).resolve()
    
    for idx, acc in enumerate(accounts):
        env = os.environ.copy()
        env["MULTI_ACCOUNT_CHILD"] = "true"
        env["BOT_ACCOUNT_INDEX"] = str(idx)
        env["BOT_ACCOUNT_ID"] = acc.get("bot_id", acc.get("id", f"bot_acc_{idx+1}"))
        
        proc = subprocess.Popen(
            [sys.executable, str(script_path)],
            cwd=str(script_path.parent),
            env=env,
        )
        processes.append(proc)
        print(f"[MULTI] Started account {env['BOT_ACCOUNT_ID']} (login={acc.get('login', 'unknown')}, pid={proc.pid})")
        time.sleep(35)  # Wait between account starts
    
    for proc in processes:
        try:
            proc.wait()
        except KeyboardInterrupt:
            proc.terminate()
    sys.exit(0)

# =====================================================
# LOGGER SETUP
# =====================================================
logger = logging.getLogger("pure_rule_based_bot")
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('[%(levelname)s] %(message)s'))
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# =====================================================
# PURE RULE-BASED ENGINE INITIALIZATION
# =====================================================
pure_engine = PureRuleBasedEngine()
risk_manager = RuleBasedRiskManager()

# =====================================================
# HELPER: Record Skip Reason
# =====================================================
def record_skip(reason: str, symbol: str, details: dict = None):
    """Log a skipped setup"""
    bot_log(
        "setup_skipped",
        f"[{symbol}] Setup skipped: {reason}" + (f" - {details}" if details else ""),
        {"symbol": symbol, "reason": reason, "details": details or {}}
    )

# =====================================================
# MAIN BOT LOOP
# =====================================================
def run_bot():
    """Pure Rule-Based Trading Bot Main Loop"""
    
    logger.info("=" * 60)
    logger.info("PURE RULE-BASED ICT & SMT TRADING BOT STARTED")
    logger.info("=" * 60)
    logger.info("Mode: PURE RULES ONLY (No Intelligence, No ML)")
    logger.info("Rules Enforced: 7 Mandatory ICT Core Rules")
    logger.info("Entry Decision: All 7 Rules MUST Pass")
    logger.info("=" * 60)
    
    # Connect to MT5
    mt5 = connect()
    if not mt5:
        logger.error("Failed to connect to MT5. Exiting.")
        sys.exit(1)
    
    set_connection(mt5)
    logger.info("[BOT] Connected to MT5")
    
    # Get user profile and limits
    profile = get_user_profile()
    max_trades = get_profile_max_trades(profile)
    logger.info(f"[BOT] Profile loaded: max_trades={max_trades}")
    
    # Get trading pairs
    pairs = TradingPairs.get_trading_pairs()
    trading_pairs = [p["symbol"] if isinstance(p, dict) and "symbol" in p else p for p in pairs]
    trading_pairs = [str(symbol).strip() for symbol in trading_pairs if symbol]

    logger.info(f"[BOT] Trading {len(trading_pairs)} symbols")
    logger.info("=" * 60)
    
    # Main loop
    iteration_count = 0
    while is_running():
        iteration_count += 1
        
        try:
            # Account snapshot
            account = get_account_snapshot()
            if not account:
                logger.warning("[BOT] Could not get account snapshot. Reconnecting...")
                mt5 = reconnect()
                continue
            
            balance = account.get("balance", 0)
            equity = account.get("equity", 0)
            open_positions = len(get_open_positions() or [])
            
            logger.info(f"\n[BOT] Iteration {iteration_count} | Balance: {balance} | "
                       f"Equity: {equity} | Open Positions: {open_positions} | "
                       f"Max Trades: {max_trades}")
            
            # Check if we can take more trades
            if open_positions >= max_trades:
                logger.info(f"[BOT] Max trades reached ({open_positions}/{max_trades}). Skipping new entries.")
                time.sleep(60)
                continue
            
            # ======================================================
            # SYMBOL SCANNING LOOP
            # ======================================================
            symbols_evaluated = 0
            symbols_traded = 0
            
            for symbol_candidate in trading_pairs:
                if not is_running():
                    break
                
                # Resolve symbol
                try:
                    symbol = ensure_symbol(symbol_candidate)
                except RuntimeError as e:
                    logger.debug(f"[{symbol_candidate}] Symbol not available: {e}")
                    record_skip("unavailable", symbol_candidate)
                    continue
                
                if not symbol:
                    logger.debug(f"[{symbol_candidate}] Symbol not available. Skipping.")
                    record_skip("unavailable", symbol_candidate)
                    continue
                
                symbols_evaluated += 1
                
                # Get current price data
                try:
                    price_info = get_price(symbol)
                    if not price_info or price_info.get("bid") is None:
                        logger.debug(f"[{symbol}] No price data available. Skipping.")
                        record_skip("price_unavailable", symbol)
                        continue
                    
                    current_price = price_info["bid"]
                    ask_price = price_info["ask"]
                    
                except Exception as e:
                    logger.debug(f"[{symbol}] Error getting price: {e}")
                    record_skip("price_error", symbol, {"error": str(e)})
                    continue
                
                # ======================================================
                # STEP 1: MARKET ANALYSIS (Get signal data)
                # ======================================================
                try:
                    # Run top-down analysis to get trend + multi-TF context
                    topdown_result = analyze_market_top_down(symbol)
                    if not topdown_result:
                        record_skip("topdown_analysis_failed", symbol)
                        continue
                    
                    trend = topdown_result.get("trend", "neutral")
                    
                    # Get entry model signal (HTF OB, FVG, etc.)
                    signal = hybrid_entry_model(symbol)
                    if not signal:
                        record_skip("entry_signal_generation_failed", symbol)
                        continue
                    
                except Exception as e:
                    logger.debug(f"[{symbol}] Analysis error: {e}")
                    record_skip("analysis_error", symbol, {"error": str(e)})
                    continue
                
                # ======================================================
                # STEP 2: PURE RULE-BASED ENTRY EVALUATION
                # ======================================================
                try:
                    # Prepare data for rules engine
                    rule_data = {
                        "symbol": symbol,
                        "trend": trend,
                        "price": current_price,
                        "signal": signal,
                        "topdown": topdown_result,
                    }
                    
                    # Evaluate all 7 ICT rules + SMT
                    should_trade, reason, rule_breakdown = pure_engine.evaluate_entry(rule_data)
                    
                    # Log rule evaluation
                    met_rules = rule_breakdown.get("met_rules", [])
                    violations = rule_breakdown.get("violations", [])
                    
                    logger.info(f"[{symbol}] Rules Evaluation:")
                    logger.info(f"  Met Rules: {len(met_rules)}/7 - {met_rules}")
                    if violations:
                        logger.info(f"  Violations: {violations}")
                    
                    if not should_trade:
                        record_skip(f"rules_failed", symbol, {
                            "met_rules": met_rules,
                            "violations": violations,
                            "reason": reason
                        })
                        continue
                    
                    logger.info(f"[{symbol}] ✅ ALL 7 RULES PASSED - PROCEEDING TO EXECUTION")
                    
                except Exception as e:
                    logger.error(f"[{symbol}] Rule evaluation error: {e}")
                    record_skip("rule_evaluation_error", symbol, {"error": str(e)})
                    continue
                
                # ======================================================
                # STEP 3: VALIDATE EXECUTION CONSTRAINTS
                # ======================================================
                
                # Check session
                session_active = trading_session_open(symbol)
                if not session_active:
                    record_skip("session_closed", symbol)
                    continue
                
                # Check news
                news_ok = news_allows_trade(symbol)
                if not news_ok:
                    record_skip("news_high_impact", symbol)
                    continue
                
                # Check can_trade (slot available, correlations, etc.)
                can_trade_result = can_trade(
                    symbol=symbol,
                    max_concurrent=max_trades,
                    max_per_asset_class=3,
                )
                if not can_trade_result:
                    record_skip("trade_slot_unavailable", symbol)
                    continue
                
                logger.info(f"[{symbol}] ✅ All constraints passed")
                
                # ======================================================
                # STEP 4: CALCULATE STOP LOSS & TAKE PROFIT
                # ======================================================
                try:
                    direction = "BUY" if trend == "bullish" else "SELL"
                    
                    # Use structural SL/TP from signal (OB, FVG levels)
                    sl_tp_result = calculate_sl_tp(
                        symbol=symbol,
                        signal=signal,
                        direction=direction,
                    )
                    
                    if not sl_tp_result:
                        record_skip("sl_tp_calculation_failed", symbol)
                        continue
                    
                    sl_price = sl_tp_result.get("sl")
                    tp_price = sl_tp_result.get("tp")
                    
                    if not sl_price or not tp_price:
                        record_skip("invalid_sl_tp", symbol)
                        continue
                    
                    logger.info(f"[{symbol}] SL: {sl_price} | TP: {tp_price}")
                    
                except Exception as e:
                    logger.error(f"[{symbol}] SL/TP calculation error: {e}")
                    record_skip("sl_tp_error", symbol, {"error": str(e)})
                    continue
                
                # ======================================================
                # STEP 5: DETERMINISTIC POSITION SIZING
                # ======================================================
                try:
                    asset_class = infer_asset_class(symbol)
                    
                    # Calculate position size using DETERMINISTIC formula
                    lot_result = risk_manager.calculate_position_size(
                        account_balance=balance,
                        symbol=symbol,
                        direction=direction,
                        entry_price=current_price,
                        sl_price=sl_price,
                        tp_price=tp_price,
                        risk_percent=2.0,  # Fixed 2% risk
                        asset_class=asset_class,
                        session="london" if in_london_session() else 
                               "newyork" if in_newyork_session() else "asia",
                    )
                    
                    lot = lot_result.get("lot_size", 0)
                    sizing_reason = lot_result.get("reason", "")
                    
                    if lot <= 0:
                        record_skip("position_sizing_failed", symbol, {"reason": sizing_reason})
                        continue
                    
                    logger.info(f"[{symbol}] Position Size: {lot} lot ({sizing_reason})")
                    
                except Exception as e:
                    logger.error(f"[{symbol}] Position sizing error: {e}")
                    record_skip("position_sizing_error", symbol, {"error": str(e)})
                    continue
                
                # ======================================================
                # STEP 6: EXECUTE TRADE
                # ======================================================
                try:
                    order_type = choose_order_type(symbol)
                    
                    logger.info(f"[{symbol}] EXECUTING TRADE:")
                    logger.info(f"  Direction: {direction}")
                    logger.info(f"  Lot: {lot}")
                    logger.info(f"  Entry: {current_price}")
                    logger.info(f"  SL: {sl_price}")
                    logger.info(f"  TP: {tp_price}")
                    logger.info(f"  Order Type: {order_type}")
                    
                    trade = execute_trade(
                        symbol=symbol,
                        direction=direction,
                        lot=lot,
                        sl_price=sl_price,
                        tp_price=tp_price,
                        order_type=order_type,
                        entry_price=current_price,
                    )
                    
                    if not trade:
                        logger.error(f"[{symbol}] Trade execution failed")
                        record_skip("trade_execution_failed", symbol)
                        continue
                    
                    logger.info(f"[{symbol}] ✅ TRADE OPENED SUCCESSFULLY")
                    symbols_traded += 1
                    
                    # Register trade
                    register_trade(symbol, None)
                    
                    # Push to dashboard
                    push_trade({
                        "symbol": symbol,
                        "direction": direction,
                        "entry": current_price,
                        "sl": sl_price,
                        "tp": tp_price,
                        "lot": lot,
                        "status": "OPEN"
                    })
                    
                    # Log trade
                    bot_log(
                        "trade_opened",
                        f"[PURE RULES] Trade opened on {symbol} ({direction}). "
                        f"All 7 ICT rules passed. Position: {lot} lot | "
                        f"Entry: {current_price} | SL: {sl_price} | TP: {tp_price}",
                        {
                            "symbol": symbol,
                            "direction": direction,
                            "entry": current_price,
                            "sl": sl_price,
                            "tp": tp_price,
                            "lot": lot,
                            "rule_breakdown": rule_breakdown,
                        }
                    )
                    
                except Exception as e:
                    logger.error(f"[{symbol}] Trade execution exception: {e}")
                    traceback.print_exc()
                    record_skip("trade_execution_exception", symbol, {"error": str(e)})
                    continue
            
            # ======================================================
            # ITERATION SUMMARY
            # ======================================================
            logger.info(f"\n[BOT] Iteration Summary:")
            logger.info(f"  Symbols Evaluated: {symbols_evaluated}")
            logger.info(f"  Trades Opened: {symbols_traded}")
            logger.info(f"  Open Positions: {open_positions + symbols_traded}/{max_trades}")
            logger.info("=" * 60)
            
            # Sleep before next iteration
            time.sleep(60)
            
        except KeyboardInterrupt:
            logger.info("[BOT] Bot interrupted by user. Shutting down...")
            break
        except Exception as e:
            logger.error(f"[BOT] Unhandled error in main loop: {e}")
            traceback.print_exc()
            time.sleep(60)

# =====================================================
# ENTRY POINT
# =====================================================
if __name__ == "__main__":
    try:
        run_bot()
    except Exception as e:
        logger.error(f"[BOT] Fatal error: {e}")
        traceback.print_exc()
        sys.exit(1)
