# =====================================================
# ICT PROBABILISTIC INTRADAY TRADING BOT
# =====================================================
# Fully integrated probabilistic ICT engine:
#   - market_features.py, regime_classifier.py
#   - ict_setup_quality.py, execution_planner.py
#   - probability_updater.py
# + Robust features:
#   - Symbol mapping, multi‑account, per‑account MT5 isolation
#   - Adaptive trailing stop (OB → FVG → swing point)
#   - SMT divergence, session as confidence modifier
#   - Fallback ATR/OB, minimum lot 0.01
#   - Metals filter < $50, news filter
#   - Deeper lookback (500+ candles for structure)
#   - Max‑trades per account strictly enforced
#   - Friday ICT rules (forex/metals only, crypto 24/7)
#   - Trend‑strength gate (real rhythm from structure)
#   - Retracement confirmation (price must be inside OB or FVG)
#   - Silver Bullet entry model (10‑11 AM NY)
#   - Portfolio‑level correlation risk filter
#   - Partial close at initial TP (50 %), trail remainder
# =====================================================

from dotenv import load_dotenv
import sys, os, time, traceback, datetime, logging
from pathlib import Path

# =====================================================
# CORE DEPENDENCIES
# =====================================================
from config.trading_pairs import TradingPairs
from execution.mt5_connector import (
    connect, reconnect, get_price, get_open_positions, get_account_snapshot,
)
from multi_account_runner import load_accounts
from utils.symbol_profile import infer_asset_class
from utils.user_profiles import get_user_profile, get_profile_max_trades
from utils.logger import bot_log
from config.symbol_mappings import candidates_for
from execution.trade_executor import execute_trade
from execution.order_router import choose_order_type

# =====================================================
# PROBABILISTIC ICT ENGINE
# =====================================================
from strategy.market_features import extract_features
from strategy.regime_classifier import classify_regime, is_tradeable_regime
from strategy.ict_setup_quality import calculate_success_probability
from strategy.execution_planner import plan_execution
from strategy.probability_updater import update_probability_table

# =====================================================
# EXISTING ICT ANALYSIS
# =====================================================
from strategy.pre_trade_analysis import analyze_market_top_down
from strategy.setup_confirmations import liquidity_sweep_or_swing, bos_setup
from strategy.entry_model import hybrid_entry_model
from ict_concepts.fib import calculate_fib_levels
from ict_concepts.order_blocks import detect_htf_order_blocks
from ict_concepts.fvg import detect_fvgs
from ict_concepts.market_structure import analyze_structure

# =====================================================
# EXECUTION & RISK
# =====================================================
from risk.sl_tp_engine import calculate_sl_tp
from risk.protection import can_trade, register_trade
from fundamentals.news_filter import news_allows_trade
from utils.sessions import in_london_session, in_newyork_session, trading_session_open

from dashboard.bridge import push_trade, persist_signal_to_supabase
from bot_state import is_running, set_connection, append_log

# =====================================================
# ICT ENHANCEMENTS
# =====================================================
from ict_concepts.smt import detect_smt
from risk.trade_management import manage_trade
from risk.trend_dynamics import analyze_market_rhythm
from risk.rule_based_risk_manager import RuleBasedRiskManager

# =====================================================
# SILVER BULLET ENTRY
# =====================================================
from strategy.silver_bullet import detect_silver_bullet_entry

load_dotenv()

# -------------------------------
def cleanup_stale_locks():
    data_dir = Path(__file__).resolve().parent / "data"
    for lock_file in data_dir.glob("*.lock"):
        try: lock_file.unlink()
        except: pass
cleanup_stale_locks()

MULTI_ACCOUNT_CHILD = os.getenv("MULTI_ACCOUNT_CHILD", "false").lower() in ("1","true","yes","on")
if os.getenv("MULTI_ACCOUNT_ENABLED","false").lower() in ("1","true","yes","on") and not MULTI_ACCOUNT_CHILD:
    import subprocess
    accounts = load_accounts()
    seen = set()
    unique = [a for a in accounts if (a.get("login") or a.get("id")) and str(a.get("login") or a["id"]) not in seen and not seen.add(str(a.get("login") or a["id"]))]
    print(f"[MULTI] {len(unique)} unique accounts")
    if unique:
        processes = []
        for i, acc in enumerate(unique):
            env = os.environ.copy()
            env["MULTI_ACCOUNT_CHILD"] = "true"
            env["BOT_ACCOUNT_INDEX"] = str(i)
            env["BOT_ACCOUNT_ID"] = acc.get("bot_id", f"bot_acc_{i+1}")
            env["MT5_ACCOUNT_LOGIN"] = str(acc.get("login",""))
            env["MT5_ACCOUNT_PASSWORD"] = str(acc.get("password",""))
            env["MT5_ACCOUNT_SERVER"] = str(acc.get("server",""))

            # ---- PER-ACCOUNT TERMINAL PATH ----
            account_login = str(acc.get("login","")).strip()
            specific_key = f"ACCOUNT_{account_login}_MT5_PATH"
            specific_path = os.getenv(specific_key)
            alt_key = f"ACCOUNT_{i+1}_MT5_PATH"
            alt_path = os.getenv(alt_key)
            if specific_path:
                env["MT5_PATH"] = specific_path
                env["MT5_PORTABLE"] = "1"
            elif alt_path:
                env["MT5_PATH"] = alt_path
                env["MT5_PORTABLE"] = "1"
            else:
                global_mt5 = os.getenv("MT5_PATH", "").strip()
                if global_mt5:
                    env["MT5_PATH"] = global_mt5
                env["MT5_PORTABLE"] = "1"

            proc = subprocess.Popen([sys.executable, str(Path(__file__).resolve())], cwd=str(Path(__file__).parent), env=env)
            processes.append(proc)
            time.sleep(35)
        for p in processes: p.wait()
        sys.exit(0)

logger = logging.getLogger("ict_probabilistic_bot")
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('[%(levelname)s] %(message)s'))
logger.addHandler(handler)
logger.setLevel(logging.INFO)

risk_manager = RuleBasedRiskManager()

SYMBOL_MAP = {}
def build_symbol_map(desired_pairs):
    global SYMBOL_MAP
    SYMBOL_MAP = {}
    try:
        import MetaTrader5 as mt5
        all_sym = mt5.symbols_get()
        if not all_sym: return
        broker = {s.name.upper(): s.name for s in all_sym}
    except: return
    for desired in desired_pairs:
        desired_upper = desired.upper()
        matched = None
        if desired_upper in broker:
            matched = broker[desired_upper]
        else:
            for cand in candidates_for(desired):
                if cand.upper() in broker: matched = broker[cand.upper()]; break
            if not matched:
                for suf in ["m","M",".m",".M",".i",".pro",".ecn",".std",".micro","#","_"]:
                    test = desired_upper + suf
                    if test in broker: matched = broker[test]; break
        if matched:
            try:
                if mt5.symbol_select(matched, True):
                    tick = mt5.symbol_info_tick(matched)
                    if tick and tick.bid > 0: SYMBOL_MAP[desired] = matched
            except: pass
        else:
            logger.warning(f"Unresolved: {desired}")
    logger.info(f"Mapped {len(SYMBOL_MAP)}/{len(desired_pairs)} pairs")

def resolve_symbol(candidate):
    mapped = SYMBOL_MAP.get(candidate)
    if mapped:
        try:
            price_info = get_price(mapped)
            if isinstance(price_info, dict): val = price_info.get("bid") or price_info.get("ask") or 0
            else: val = float(price_info)
            if val > 0: return mapped
        except: pass
    try:
        import MetaTrader5 as mt5
        if mt5.symbol_select(candidate, True):
            tick = mt5.symbol_info_tick(candidate)
            if tick and tick.bid > 0: return candidate
    except: pass
    for cand in candidates_for(candidate):
        if cand == mapped: continue
        try:
            if mt5.symbol_select(cand, True):
                tick = mt5.symbol_info_tick(cand)
                if tick and tick.bid > 0: return cand
        except: continue
    return None

def record_skip(reason, symbol, details=None):
    bot_log("setup_skipped", f"[{symbol}] Skip: {reason}" + (f" - {details}" if details else ""),
            {"symbol": symbol, "reason": reason, "details": details or {}})

def is_friday_ict_cutoff():
    """ICT Friday rule: no new entries for forex/metals after 14:00 UTC Friday. Crypto excluded."""
    now = datetime.datetime.now(datetime.timezone.utc)
    return now.weekday() == 4 and now.hour >= 14

def is_friday_position_close():
    """Close all forex/metals positions at 16:00 UTC Friday. Crypto untouched."""
    now = datetime.datetime.now(datetime.timezone.utc)
    return now.weekday() == 4 and now.hour >= 16

# --- Portfolio correlation map ---
CORRELATED_PAIRS = {
    "EURUSD": "GBPUSD",
    "GBPUSD": "EURUSD",
    "AUDUSD": "NZDUSD",
    "NZDUSD": "AUDUSD",
    "XAUUSD": "XAGUSD",
    "XAGUSD": "XAUUSD",
    "BTCUSD": "ETHUSD",
    "ETHUSD": "BTCUSD",
}

def has_correlated_position(symbol, direction):
    """
    Check if there is already an open position in the correlated pair in the same direction.
    Returns True if such a position exists.
    """
    corr = CORRELATED_PAIRS.get(symbol)
    if not corr:
        return False
    for pos in (get_open_positions() or []):
        if pos.get("symbol") == corr and pos.get("direction", "").lower() == direction.lower():
            return True
    return False

def run_bot():
    logger.info("="*70)
    logger.info("ICT PROBABILISTIC INTRADAY BOT STARTED")
    logger.info("="*70)
    login = os.getenv("MT5_ACCOUNT_LOGIN")
    creds = {"login": login, "password": os.getenv("MT5_ACCOUNT_PASSWORD"), "server": os.getenv("MT5_ACCOUNT_SERVER")} if login else None
    if not connect(creds): sys.exit(1)
    set_connection(True)

    pairs = TradingPairs.get_trading_pairs()
    trading_pairs = [p["symbol"] if isinstance(p,dict) else p for p in pairs]
    trading_pairs = [str(s).strip() for s in trading_pairs if s]
    build_symbol_map(trading_pairs)
    profile = get_user_profile()
    max_trades = get_profile_max_trades(profile)

    iteration = 0
    while is_running():
        iteration += 1
        try:
            acc = get_account_snapshot()
            if not acc: reconnect(); time.sleep(30); continue
            balance = acc["balance"]
            open_pos = len(get_open_positions() or [])
            logger.info(f"\nIter {iteration} | Bal {balance} | Open {open_pos}/{max_trades}")

            # ================================================================
            # FRIDAY POSITION CLOSE (forex/metals only, crypto left alone)
            # ================================================================
            if is_friday_position_close():
                for pos in (get_open_positions() or []):
                    try:
                        sym = pos.get("symbol", "")
                        asset_class = infer_asset_class(sym)
                        if asset_class == "crypto":
                            continue
                        import MetaTrader5 as mt5
                        pos_ticket = pos.get("ticket")
                        if pos_ticket:
                            pos_dir = pos.get("direction", "buy")
                            pos_vol = pos.get("volume", 0.01)
                            cur = get_price(sym)
                            cur = (cur["bid"]+cur["ask"])/2 if isinstance(cur, dict) else float(cur)
                            close_type = mt5.ORDER_TYPE_SELL if pos_dir == "buy" else mt5.ORDER_TYPE_BUY
                            mt5.order_send({"action": mt5.TRADE_ACTION_DEAL, "symbol": sym,
                                            "volume": pos_vol, "type": close_type,
                                            "position": pos_ticket, "price": cur})
                            logger.info(f"[{sym}] 🔒 Friday close – position liquidated per ICT rule")
                    except Exception:
                        pass
                logger.info("[BOT] Friday 16:00 UTC – all forex/metals positions closed. Sleeping.")
                time.sleep(300)
                continue

            # ================================================================
            # ADAPTIVE ICT TRADE MANAGEMENT
            # (uses OB, FVG, and strong swings for trailing stop)
            # ================================================================
            for pos in (get_open_positions() or []):
                try:
                    sym = pos.get("symbol")
                    pr = get_price(sym)
                    cur = (pr["bid"]+pr["ask"])/2 if isinstance(pr,dict) else float(pr)

                    # Get full structural context for this symbol
                    pos_topdown = analyze_market_top_down(sym, cur)
                    pos_swings = (pos_topdown.get("MTF", {}) or {}).get("swings", [])
                    pos_order_blocks = (pos_topdown.get("MTF", {}) or {}).get("order_blocks", [])
                    pos_fvgs = (pos_topdown.get("LTF", {}) or {}).get("fvgs", [])

                    trade_dict = {"symbol": sym, "direction": pos.get("direction","buy"),
                                  "entry": pos.get("price",0), "sl": pos.get("sl",0),
                                  "tp": pos.get("tp",0), "lot": pos.get("volume",0.01), "stage": 0, "open": True}

                    action = manage_trade(trade_dict, cur,
                                          swings=pos_swings,
                                          order_blocks=pos_order_blocks,
                                          fvgs=pos_fvgs,
                                          atr=None)   # ATR from features if needed
                    if action:
                        action_type = action.get("action")
                        try:
                            import MetaTrader5 as mt5
                            pos_ticket = pos.get("ticket")
                            if pos_ticket:
                                if action_type in ("move_sl", "trail"):
                                    mt5.order_send({"action": mt5.TRADE_ACTION_SLTP, "position": pos_ticket, "sl": action["sl"]})
                                elif action_type == "partial_close":
                                    close_pct = action.get("percent", 0.5)
                                    vol = round(pos.get("volume",0.01) * close_pct, 2)
                                    if vol >= 0.01:
                                        close_type = mt5.ORDER_TYPE_SELL if pos.get("direction")=="buy" else mt5.ORDER_TYPE_BUY
                                        mt5.order_send({"action": mt5.TRADE_ACTION_DEAL, "symbol": sym, "volume": vol, "type": close_type, "position": pos_ticket, "price": cur})
                        except: pass
                except: pass

            # Re‑fetch open positions after management actions
            open_pos = len(get_open_positions() or [])
            if open_pos >= max_trades:
                logger.info(f"[BOT] Max trades reached ({open_pos}/{max_trades}). Skipping new entries.")
                time.sleep(60); continue

            symbols_evaluated = 0
            symbols_traded = 0

            for sym_cand in trading_pairs:
                if not is_running(): break
                # === MAX TRADES CHECK (within iteration) ===
                if open_pos + symbols_traded >= max_trades:
                    logger.info(f"[BOT] Max trades reached during iteration ({open_pos + symbols_traded}/{max_trades}). Stopping scan.")
                    break

                symbol = resolve_symbol(sym_cand)
                if not symbol:
                    record_skip("symbol_not_found", sym_cand); continue
                symbols_evaluated += 1
                try:
                    price_info = get_price(symbol)
                    current_price = (price_info["bid"]+price_info["ask"])/2 if isinstance(price_info,dict) else float(price_info)
                    if current_price <= 0: continue

                    topdown = analyze_market_top_down(symbol, current_price)
                    trend = topdown.get("overall_trend","neutral")
                    if trend not in ("bullish","bearish"): continue

                    # ---- COMPUTE REAL TREND STRENGTH FROM MARKET RHYTHM ----
                    rhythm = analyze_market_rhythm(topdown, trend)
                    real_trend_strength = rhythm.get("trend_strength", 0.6)
                    market_condition = rhythm.get("market_condition", "normal")

                    # ---- TREND STRENGTH GATE (reject weak / transitioning trends) ----
                    if real_trend_strength < 0.60:
                        logger.info(f"[{symbol}] ⏸ Weak trend strength ({real_trend_strength:.2f}) – skipping")
                        continue

                    # ---- BUILD MARKET DATA WITH REAL trend_strength ----
                    market_data = {
                        "trend": trend,
                        "price": current_price,
                        "atr": topdown.get("HTF", {}).get("atr", 0.0),
                        "m1_candles": topdown.get("m1_candles", []),
                        "m5_candles": topdown.get("m5_candles", []),
                        "swing_low": min([s.get("price", current_price) for s in (topdown.get("MTF", {}).get("swings") or [])]) if any(s.get("price") for s in topdown.get("MTF", {}).get("swings", [])) else current_price,
                        "swing_high": max([s.get("price", current_price) for s in (topdown.get("MTF", {}).get("swings") or [])]) if any(s.get("price") for s in topdown.get("MTF", {}).get("swings", [])) else current_price,
                        "trend_strength": real_trend_strength,
                        "market_condition": market_condition,
                    }
                    # Enrich with first available FVG & OB from the top-down analysis
                    market_data["fvg"] = next(iter((topdown.get("LTF", {}) or {}).get("fvgs", [])), None)
                    market_data["htf_ob"] = next(iter((topdown.get("MTF", {}) or {}).get("order_blocks", [])), None)

                    signal = hybrid_entry_model(market_data)
                    if not signal:
                        continue

                    # 1. EXTRACT FEATURES (ICT → MATH)
                    features = extract_features(symbol, current_price, topdown)
                    if features is None: continue

                    # 2. REGIME CLASSIFICATION
                    regime = classify_regime(features, topdown)
                    if not is_tradeable_regime(regime):
                        logger.info(f"[{symbol}] ⏸ Untradeable regime ({regime})")
                        continue

                    # 3. SMT DIVERGENCE
                    smt_result = {"confirmed": False}
                    try:
                        correlated = {"EURUSD":"GBPUSD","GBPUSD":"EURUSD","AUDUSD":"NZDUSD","NZDUSD":"AUDUSD",
                                      "XAUUSD":"XAGUSD","XAGUSD":"XAUUSD","BTCUSD":"ETHUSD","ETHUSD":"BTCUSD"}
                        corr = correlated.get(symbol)
                        if corr:
                            corr_price = get_price(corr)
                            corr_price = (corr_price["bid"]+corr_price["ask"])/2 if isinstance(corr_price,dict) else float(corr_price)
                            corr_top = analyze_market_top_down(corr, corr_price)
                            main_candles = topdown.get("m5_candles",[])
                            corr_candles = corr_top.get("m5_candles",[])
                            if len(main_candles)>=10 and len(corr_candles)>=10:
                                pair_a = {"high": max(c["high"] for c in main_candles[-5:]),
                                          "low": min(c["low"] for c in main_candles[-5:]),
                                          "prev_high": max(c["high"] for c in main_candles[-10:-5]),
                                          "prev_low": min(c["low"] for c in main_candles[-10:-5]),
                                          "timeframe":"M5"}
                                pair_b = {"high": max(c["high"] for c in corr_candles[-5:]),
                                          "low": min(c["low"] for c in corr_candles[-5:]),
                                          "prev_high": max(c["high"] for c in corr_candles[-10:-5]),
                                          "prev_low": min(c["low"] for c in corr_candles[-10:-5]),
                                          "timeframe":"M5"}
                                smt_result = detect_smt(pair_a, pair_b)
                                if smt_result.get("confirmed"):
                                    features["smt"] = True
                                    logger.info(f"[{symbol}] 🔥 SMT divergence")
                    except: pass

                    # 4. PROBABILITY ESTIMATION
                    killzone = (in_london_session() or in_newyork_session())
                    prob, quality = calculate_success_probability(features, regime, killzone)
                    logger.info(f"[{symbol}] prob={prob:.2f} quality={quality:.1f}")

                    MIN_PROB = 0.52
                    if prob < MIN_PROB:
                        logger.info(f"[{symbol}] ❌ prob {prob:.2f} < {MIN_PROB}")
                        continue

                    # 5. EXECUTION PLANNING
                    direction = "buy" if trend == "bullish" else "sell"
                    plan = plan_execution(symbol, direction, current_price, features, topdown)
                    sl = float(plan["sl"])
                    tp = float(plan["tp"])
                    logger.info(f"[{symbol}] plan: SL={sl:.5f} TP={'trailing' if tp == 0 else f'{tp:.5f}'} ({plan['method']})")

                    # ================================================================
                    # RETRACEMENT CHECK – price must be inside a valid OB or FVG
                    # ================================================================
                    valid_entry = False
                    entry_ob = None
                    entry_fvg = None

                    obs = (topdown.get("MTF", {}) or {}).get("order_blocks", [])
                    fvgs = (topdown.get("LTF", {}) or {}).get("fvgs", [])

                    for ob in obs:
                        if (isinstance(ob, dict) and
                            not ob.get("mitigated", False) and
                            ob.get("type") == ("bullish" if trend == "bullish" else "bearish")):
                            try:
                                ob_low = float(ob["low"])
                                ob_high = float(ob["high"])
                                if ob_low <= current_price <= ob_high:
                                    valid_entry = True
                                    entry_ob = ob
                                    break
                            except Exception:
                                continue

                    if not valid_entry:
                        for fvg in fvgs:
                            if (isinstance(fvg, dict) and
                                fvg.get("active", True) and
                                not fvg.get("mitigated", False) and
                                fvg.get("type") == ("bullish" if trend == "bullish" else "bearish")):
                                try:
                                    fvg_low = float(fvg["low"])
                                    fvg_high = float(fvg["high"])
                                    if fvg_low <= current_price <= fvg_high:
                                        valid_entry = True
                                        entry_fvg = fvg
                                        break
                                except Exception:
                                    continue

                    if not valid_entry:
                        logger.info(f"[{symbol}] ❌ Price not in OB/FVG – no valid retracement")
                        continue

                    # ================================================================
                    # SILVER BULLET ENTRY (optional path – bypasses normal entry)
                    # ================================================================
                    silver_entry = None
                    now_utc = datetime.datetime.now(datetime.timezone.utc)
                    if 14 <= now_utc.hour < 15:   # 10‑11 AM NY
                        silver_entry = detect_silver_bullet_entry(symbol, current_price, topdown, trend)
                        if silver_entry:
                            # Override SL/TP with tighter Silver Bullet levels
                            sl = silver_entry["sl"]
                            tp = silver_entry["tp"]
                            logger.info(f"[{symbol}] 🔫 Silver Bullet entry overrides normal setup")

                    # 6. GATES
                    if not news_allows_trade(symbol):
                        record_skip("news", symbol); continue
                    if not trading_session_open(symbol):
                        logger.info(f"[{symbol}] ⚠️ Outside session")

                    asset_class = infer_asset_class(symbol)
                    if asset_class == "metals" and balance < 50:
                        logger.info(f"[{symbol}] ⛔ Metals blocked – balance ${balance:.2f} < $50")
                        continue

                    # ---- FRIDAY ICT GATE (forex/metals only, crypto 24/7) ----
                    if asset_class != "crypto" and is_friday_ict_cutoff():
                        logger.info(f"[{symbol}] ⛔ Friday cutoff – no new entries after 14:00 UTC")
                        continue

                    # ---- PORTFOLIO CORRELATION RISK ----
                    if has_correlated_position(symbol, direction):
                        logger.info(f"[{symbol}] ⛔ Correlated pair already open in same direction")
                        continue

                    if not can_trade(symbol, ""):
                        logger.info(f"[{symbol}] ⛔ Cooldown"); continue

                    # 7. FALLBACK ATR & OB
                    atr_value = float(features.get("atr", 0.0) or 0.0)
                    if atr_value <= 0:
                        if asset_class == "forex":
                            atr_value = current_price * 0.001
                        else:
                            atr_value = current_price * 0.005
                        logger.info(f"[{symbol}] ⚠️ ATR missing – fallback ATR={atr_value:.5f}")

                    htf_ob = {}
                    if not htf_ob or (not htf_ob.get("low") and not htf_ob.get("high")):
                        htf_ob = {"low": features.get("swing_low", current_price), "high": features.get("swing_high", current_price)}
                        logger.info(f"[{symbol}] ⚠️ No valid OB – using swing low/high")

                    # 8. POSITION SIZE
                    sl_distance = abs(current_price - sl)
                    if sl_distance <= 0:
                        logger.info(f"[{symbol}] ❌ SL distance zero – skip"); continue

                    if "JPY" in symbol.upper():
                        pip_size = 0.01
                    else:
                        pip_size = 0.0001

                    try:
                        import MetaTrader5 as mt5
                        sym_info = mt5.symbol_info(symbol)
                        if sym_info is not None:
                            tick_value = getattr(sym_info, "trade_tick_value", 0.01)
                            tick_size = getattr(sym_info, "trade_tick_size", pip_size) or 1e-9
                            pip_value = (tick_value / tick_size) * pip_size
                        else:
                            pip_value = 1.0 if "JPY" in symbol else 10.0
                    except:
                        pip_value = 1.0 if "JPY" in symbol else 10.0

                    risk_amount = balance * 0.01
                    lot = risk_amount / (sl_distance / pip_size * pip_value)
                    lot = round(float(lot), 2)

                    if lot < 0.01:
                        logger.info(f"[{symbol}] ⚠️ Lot {lot:.4f} < 0.01 – forcing 0.01")
                        lot = 0.01
                    if lot <= 0:
                        logger.info(f"[{symbol}] ❌ Lot size zero – skip"); continue

                    # 9. EXECUTE
                    order_type = choose_order_type(
                        price=current_price,
                        fvg=features.get("fvg"),
                        direction=direction,
                        candles=topdown.get("m5_candles"),
                        mode="auto"
                    )

                    trade = execute_trade(symbol, direction, lot, sl, tp, order_type, current_price)
                    if trade:
                        symbols_traded += 1
                        register_trade(symbol, None)
                        push_trade({"symbol":symbol, "direction":direction,
                                    "entry":current_price, "sl":sl, "tp":tp, "lot":lot, "status":"OPEN"})
                        logger.info(f"[{symbol}] 🎯 Trade placed")
                    else:
                        logger.info(f"[{symbol}] ❌ MT5 rejected")

                except Exception as e:
                    logger.error(f"[{sym_cand}] Error: {e}")

            logger.info(f"\nSummary: Eval {symbols_evaluated}, Traded {symbols_traded}")
            time.sleep(60)

        except KeyboardInterrupt:
            break
        except Exception as e:
            logger.error(f"Loop error: {e}")
            traceback.print_exc()
            time.sleep(60)

if __name__ == "__main__":
    try: run_bot()
    except Exception as e: print(f"CRITICAL: {e}")