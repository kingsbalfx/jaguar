import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

try:
    import MetaTrader5 as mt5
except Exception:
    mt5 = None

from backtest.metrics import calculate_metrics
from config.symbol_mappings import candidates_for
from ict_concepts.fvg import detect_fvg_from_df
from ict_concepts.liquidity import detect_liquidity_zones
from market_structure.structure import analyze_market_structure
from strategy.pre_trade_analysis import (
    _external_liquidity as _live_external_liquidity,
    _background_reference_levels as _live_background_reference_levels,
    _h1_m15_candle_alignment as _live_h1_m15_candle_alignment,
    _opening_gap_from_state as _live_opening_gap_from_state,
    _select_background_context as _live_select_background_context,
    _standard_fetch_bars as _live_standard_fetch_bars,
    _visual_live_concepts as _live_visual_concepts,
)
from strategy.unified_strategy import evaluate_unified_setup
from utils.sessions import in_london_session, in_newyork_session
from utils.symbol_profile import build_symbol_profile_snapshot, get_entry_profile

RATE_COLUMNS = [
    "time",
    "open",
    "high",
    "low",
    "close",
    "tick_volume",
    "spread",
    "real_volume",
]
_RATE_SYMBOL_CACHE = {}


def _env_int(name, default, minimum=1, maximum=None):
    try:
        value = int(str(os.getenv(name, str(default))).strip())
    except (TypeError, ValueError):
        value = default
    value = max(minimum, value)
    if maximum is not None:
        value = min(maximum, value)
    return value


def _concept_candle_windows():
    return {
        "fetch_per_timeframe": _env_int("CANDLE_FETCH_PER_TIMEFRAME", 1000, minimum=500, maximum=5000),
        "htf_context": _env_int("HTF_CONTEXT_CANDLES", 120, minimum=50, maximum=500),
        "external_liquidity": _env_int("EXTERNAL_LIQUIDITY_CANDLES", 200, minimum=50, maximum=500),
        "structure": _env_int("STRUCTURE_CANDLES", 80, minimum=20, maximum=250),
        "true_fvg_ob_context": _env_int("TRUE_FVG_OB_CONTEXT_CANDLES", 100, minimum=20, maximum=250),
        "smt": _env_int("SMT_CANDLES", 20, minimum=10, maximum=50),
        "sweep": _env_int("SWEEP_CANDLES", 20, minimum=5, maximum=50),
        "displacement": _env_int("DISPLACEMENT_CANDLES", 10, minimum=3, maximum=30),
        "execution_confirmation": _env_int("EXECUTION_CONFIRMATION_CANDLES", 50, minimum=10, maximum=100),
    }


def _candle_window(candles, size):
    if not candles:
        return []
    return candles[-max(1, min(int(size), len(candles))):]


def _require_mt5():
    if mt5 is None:
        raise RuntimeError("MetaTrader5 package not available for backtesting")


def _tf_to_mt5(tf):
    _require_mt5()
    mapping = {
        "M1": mt5.TIMEFRAME_M1,
        "M5": mt5.TIMEFRAME_M5,
        "M15": mt5.TIMEFRAME_M15,
        "M30": mt5.TIMEFRAME_M30,
        "H1": mt5.TIMEFRAME_H1,
        "H4": mt5.TIMEFRAME_H4,
        "W1": mt5.TIMEFRAME_W1,
        "D1": mt5.TIMEFRAME_D1,
    }
    return mapping[tf]


def _profile_snapshot():
    profile = {
        "weekly_timeframe": os.getenv("WEEKLY_TIMEFRAME", "W1"),
        "daily_timeframe": os.getenv("DAILY_TIMEFRAME", "D1"),
        "daily_context_fallback_timeframe": os.getenv("DAILY_CONTEXT_FALLBACK_TIMEFRAME", os.getenv("D1_CONTEXT_FALLBACK_TIMEFRAME", "H4")),
        "htf_timeframe": os.getenv("HTF_TIMEFRAME", "H1"),
        "mtf_timeframe": os.getenv("MTF_TIMEFRAME", "M15"),
        "ltf_timeframe": os.getenv("LTF_TIMEFRAME", "M5"),
        "default_rr_ratio": float(os.getenv("DEFAULT_RR_RATIO", "3.0")),
        "min_rr_ratio": float(os.getenv("MIN_RR_RATIO", "2.0")),
        "liquidity_tolerance_ratio": float(os.getenv("LIQUIDITY_TOLERANCE_RATIO", "0.0015")),
        "entry_fib_buffer_ratio": float(os.getenv("ENTRY_FIB_BUFFER_RATIO", "0.08")),
        "news_filter_strict": os.getenv("NEWS_FILTER_STRICT", "false").lower() in ("1", "true", "yes"),
    }
    profile.update(build_symbol_profile_snapshot())
    return profile


def _fetch_rates(symbol, timeframe, bars):
    symbol = str(symbol or "").strip().upper()
    attempts = []
    cached_symbol = _RATE_SYMBOL_CACHE.get(symbol)
    if cached_symbol:
        attempts.append(cached_symbol)
    attempts.extend(candidate for candidate in candidates_for(symbol) if candidate not in attempts)

    required_columns = {"time", "open", "high", "low", "close"}
    for candidate_symbol in attempts:
        rates = mt5.copy_rates_from_pos(candidate_symbol, _tf_to_mt5(timeframe), 0, bars)
        if rates is None or len(rates) == 0:
            continue
        df = pd.DataFrame(rates)
        if not required_columns.issubset(df.columns):
            continue
        df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
        _RATE_SYMBOL_CACHE[symbol] = candidate_symbol
        return df
    return pd.DataFrame(columns=RATE_COLUMNS)


def _swings_from_df(df):
    swings = []
    if df is None or len(df) < 5:
        return swings
    for i in range(2, len(df) - 2):
        row = df.iloc[i]
        high = row["high"]
        low = row["low"]
        if high > df.iloc[i - 1]["high"] and high > df.iloc[i + 1]["high"]:
            swings.append(
                {
                    "type": "high",
                    "price": float(high),
                    "index": int(i),
                    "time": row["time"],
                }
            )
        if low < df.iloc[i - 1]["low"] and low < df.iloc[i + 1]["low"]:
            swings.append(
                {
                    "type": "low",
                    "price": float(low),
                    "index": int(i),
                    "time": row["time"],
                }
            )
    return swings


def _trend_from_swings(swings):
    highs = [s for s in swings if s["type"] == "high"]
    lows = [s for s in swings if s["type"] == "low"]
    if len(highs) < 2 or len(lows) < 2:
        return "neutral"
    if highs[-1]["price"] > highs[-2]["price"] and lows[-1]["price"] > lows[-2]["price"]:
        return "bullish"
    if highs[-1]["price"] < highs[-2]["price"] and lows[-1]["price"] < lows[-2]["price"]:
        return "bearish"
    return "range"


def _fib_from_df(df):
    high = float(df["high"].max())
    low = float(df["low"].min())
    return {
        "0.0": low,
        "0.25": low + 0.25 * (high - low),
        "0.5": low + 0.5 * (high - low),
        "0.75": low + 0.75 * (high - low),
        "1.0": high,
    }


def _order_blocks_from_df(symbol, timeframe, df):
    obs = []
    if df is None or len(df) < 5:
        return obs
    for i in range(2, len(df) - 2):
        current = df.iloc[i]
        previous = df.iloc[i - 1]
        body = abs(float(current["close"]) - float(current["open"]))
        candle_range = max(float(current["high"]) - float(current["low"]), 1e-9)
        displacement = body / candle_range
        average_volume = float(df.iloc[max(0, i - 10) : i]["tick_volume"].mean()) if "tick_volume" in df.columns else 0.0
        volume_boost = float(current.get("tick_volume", 0.0)) >= max(average_volume * 1.15, 1.0)

        if float(current["close"]) > float(current["open"]):
            prior_low = float(df.iloc[max(0, i - 4) : i]["low"].min())
            liquidity_sweep = float(current["low"]) < prior_low
            order_type = "bullish"
        else:
            prior_high = float(df.iloc[max(0, i - 4) : i]["high"].max())
            liquidity_sweep = float(current["high"]) > prior_high
            order_type = "bearish"

        institutional_footprint = displacement >= 0.70 and volume_boost and liquidity_sweep
        if not institutional_footprint:
            continue

        obs.append(
            {
                "type": order_type,
                "high": float(previous["high"]),
                "low": float(previous["low"]),
                "index": int(i),
                "timeframe": timeframe,
                "id": f"{symbol}|{timeframe}|{order_type}|{i}",
                "displacement": round(displacement, 3),
                "liquidity_sweep_confirmed": liquidity_sweep,
                "volume_boost": volume_boost,
                "institutional_footprint": institutional_footprint,
                "final_opposing_candle": (
                    float(previous["close"]) < float(previous["open"])
                    if order_type == "bullish"
                    else float(previous["close"]) > float(previous["open"])
                ),
                "fresh": True,
                "mitigated": False,
            }
        )
    return obs


def _recent_candles_from_df(df, bars=4):
    if df is None or len(df) == 0:
        return []
    candles = []
    for _, candle in df.tail(bars).iterrows():
        candles.append(
            {
                "open": float(candle["open"]),
                "high": float(candle["high"]),
                "low": float(candle["low"]),
                "close": float(candle["close"]),
                "volume": float(candle.get("tick_volume", 0.0)),
                "time": candle.get("time"),
            }
        )
    return candles


def _atr_from_df(df, period=14):
    if df is None or len(df) == 0:
        return 0.0

    recent_df = df.tail(max(period + 1, 2)).reset_index(drop=True)
    true_ranges = []
    previous_close = None
    for _, candle in recent_df.iterrows():
        high_price = float(candle["high"])
        low_price = float(candle["low"])
        close_price = float(candle["close"])
        if previous_close is None:
            true_range = high_price - low_price
        else:
            true_range = max(
                high_price - low_price,
                abs(high_price - previous_close),
                abs(low_price - previous_close),
            )
        true_ranges.append(true_range)
        previous_close = close_price

    if not true_ranges:
        return 0.0
    window = true_ranges[-max(1, min(period, len(true_ranges))):]
    return sum(window) / len(window)


def _empty_timeframe_state(timeframe):
    return {
        "timeframe": timeframe,
        "trend": "neutral",
        "fib": {},
        "fvgs": [],
        "order_blocks": [],
        "liquidity": {"EQH": [], "EQL": []},
        "swings": [],
        "market_structure": {
            "timeframe": timeframe,
            "trend": "range",
            "events": [],
            "last_event": None,
            "bos": False,
            "choch": False,
            "mss": False,
        },
        "recent_candles": [],
        "concept_windows": {
            "htf_context": [],
            "external_liquidity": [],
            "structure": [],
            "true_fvg_ob_context": [],
            "smt": [],
            "sweep": [],
            "displacement": [],
            "execution_confirmation": [],
        },
        "candle_window_lengths": {
            "fetched": 0,
            "htf_context": 0,
            "external_liquidity": 0,
            "structure": 0,
            "true_fvg_ob_context": 0,
            "smt": 0,
            "sweep": 0,
            "displacement": 0,
            "execution_confirmation": 0,
        },
        "atr": 0.0,
    }


def _analysis_from_frames(symbol, price, frames, profile):
    weekly_tf = str(profile.get("weekly_timeframe", "W1")).upper()
    daily_tf = str(profile.get("daily_timeframe", "D1")).upper()
    daily_fallback_tf = str(profile.get("daily_context_fallback_timeframe", "H4")).upper()
    htf = profile["htf_timeframe"]
    mtf = profile["mtf_timeframe"]
    ltf = profile["ltf_timeframe"]
    required_timeframes = {str(htf), str(mtf), str(ltf)}
    background_timeframes = {daily_tf, weekly_tf}
    if daily_fallback_tf:
        background_timeframes.add(daily_fallback_tf)

    analysis = {}
    entry_profile = get_entry_profile(symbol)
    candle_windows = _concept_candle_windows()
    base_recent_candle_count = max(int(entry_profile["recent_candles"]), candle_windows["fetch_per_timeframe"])
    atr_period = max(5, int(profile.get("entry_atr_period", 14)))
    for timeframe, df in frames.items():
        if df is None or len(df) < 20:
            if timeframe in required_timeframes:
                return None
            if timeframe in background_timeframes:
                analysis[timeframe] = _empty_timeframe_state(timeframe)
                continue
            continue
        swings = _swings_from_df(df)
        timeframe_trend = _trend_from_swings(swings)
        market_structure = analyze_market_structure(swings, direction=timeframe_trend, timeframe=timeframe)
        if timeframe_trend not in ("bullish", "bearish") and market_structure.get("trend") in ("bullish", "bearish"):
            timeframe_trend = market_structure["trend"]
        timeframe_fetch_bars = _live_standard_fetch_bars(timeframe, base_recent_candle_count)
        recent_candles = _recent_candles_from_df(df, bars=timeframe_fetch_bars)
        analysis[timeframe] = {
            "trend": timeframe_trend,
            "fetch_bars": timeframe_fetch_bars,
            "fib": _fib_from_df(df),
            "fvgs": [
                {**fvg, "timeframe": timeframe}
                for fvg in detect_fvg_from_df(df, trend=timeframe_trend)
            ],
            "order_blocks": _order_blocks_from_df(symbol, timeframe, df),
            "liquidity": detect_liquidity_zones(swings),
            "swings": swings,
            "market_structure": market_structure,
            "recent_candles": recent_candles,
            "concept_windows": {
                "htf_context": _candle_window(recent_candles, candle_windows["htf_context"]),
                "external_liquidity": _candle_window(recent_candles, candle_windows["external_liquidity"]),
                "structure": _candle_window(recent_candles, candle_windows["structure"]),
                "true_fvg_ob_context": _candle_window(recent_candles, candle_windows["true_fvg_ob_context"]),
                "smt": _candle_window(recent_candles, candle_windows["smt"]),
                "sweep": _candle_window(recent_candles, candle_windows["sweep"]),
                "displacement": _candle_window(recent_candles, candle_windows["displacement"]),
                "execution_confirmation": _candle_window(recent_candles, candle_windows["execution_confirmation"]),
            },
            "candle_window_lengths": {
                "fetched": len(recent_candles),
                "requested_fetch": timeframe_fetch_bars,
                "htf_context": len(_candle_window(recent_candles, candle_windows["htf_context"])),
                "external_liquidity": len(_candle_window(recent_candles, candle_windows["external_liquidity"])),
                "structure": len(_candle_window(recent_candles, candle_windows["structure"])),
                "true_fvg_ob_context": len(_candle_window(recent_candles, candle_windows["true_fvg_ob_context"])),
                "smt": len(_candle_window(recent_candles, candle_windows["smt"])),
                "sweep": len(_candle_window(recent_candles, candle_windows["sweep"])),
                "displacement": len(_candle_window(recent_candles, candle_windows["displacement"])),
                "execution_confirmation": len(_candle_window(recent_candles, candle_windows["execution_confirmation"])),
            },
            "atr": _atr_from_df(df, period=atr_period),
        }

    for timeframe in background_timeframes:
        analysis.setdefault(timeframe, _empty_timeframe_state(timeframe))

    overall_trend = analysis[htf]["trend"]
    if overall_trend not in ("bullish", "bearish"):
        mtf_trend = analysis[mtf]["trend"]
        if mtf_trend in ("bullish", "bearish"):
            overall_trend = mtf_trend
    external_liquidity = _live_external_liquidity(
        (htf, analysis[htf]),
        (mtf, analysis[mtf]),
        (ltf, analysis[ltf]),
    )
    for state in (analysis[htf], analysis[mtf], analysis[ltf]):
        state["external_liquidity"] = external_liquidity
    analysis[htf]["liquidity"] = external_liquidity
    h1_m15_alignment = _live_h1_m15_candle_alignment(analysis[htf], analysis[mtf])
    if h1_m15_alignment.get("confirmed") and h1_m15_alignment.get("direction"):
        overall_trend = "bullish" if h1_m15_alignment["direction"] == "buy" else "bearish"
    background_state, previous_day_context = _live_select_background_context(
        analysis.get(daily_tf, _empty_timeframe_state(daily_tf)),
        analysis.get(daily_fallback_tf, _empty_timeframe_state(daily_fallback_tf)),
        price,
        primary_timeframe=daily_tf,
        fallback_timeframe=daily_fallback_tf,
    )
    opening_gaps = {
        "NDOG": _live_opening_gap_from_state(analysis.get(daily_tf, _empty_timeframe_state(daily_tf)), price, "NDOG", daily_tf),
        "NWOG": _live_opening_gap_from_state(analysis.get(weekly_tf, _empty_timeframe_state(weekly_tf)), price, "NWOG", weekly_tf),
    }
    visual_concepts = _live_visual_concepts(
        symbol,
        price,
        overall_trend,
        ((htf, analysis[htf]), (mtf, analysis[mtf]), (ltf, analysis[ltf])),
        reference_levels=_live_background_reference_levels(background_state),
    )
    return {
        "overall_trend": overall_trend,
        "daily_trend": analysis.get(daily_tf, {}).get("trend"),
        "topdown": {
            "trend": overall_trend,
            "context_alignment": "aligned" if h1_m15_alignment.get("confirmed") else "mixed",
            "daily_trend": analysis.get(daily_tf, {}).get("trend"),
            "background_trend": background_state.get("trend"),
            "background_timeframe": previous_day_context.get("source_timeframe"),
            "h1_trend": analysis[htf].get("trend"),
            "m15_trend": analysis[mtf].get("trend") if str(mtf).upper() == "M15" else "not_used",
            "m5_trend": analysis[ltf].get("trend") if str(ltf).upper() == "M5" else "not_used",
            "execution_trend": analysis[ltf].get("trend"),
            "h1_m15_alignment": h1_m15_alignment,
            "previous_day_context": previous_day_context,
            "opening_gaps": opening_gaps,
            "visual_concepts": visual_concepts,
        },
        "price": price,
        "timeframes": {
            "WEEKLY": weekly_tf,
            "DAILY": daily_tf,
            "DAILY_CONTEXT_FALLBACK": daily_fallback_tf,
            "BACKGROUND_CONTEXT": previous_day_context.get("source_timeframe"),
            "HTF": htf,
            "MTF": mtf,
            "LTF": ltf,
            "EXECUTION": ltf,
        },
        "candle_windows": candle_windows,
        "candle_window_usage": {
            "fetch_per_timeframe": recent_candle_count,
            "htf_narrative": candle_windows["htf_context"],
            "external_liquidity": candle_windows["external_liquidity"],
            "market_structure_mss_bos": candle_windows["structure"],
            "true_fvg_order_block_context": candle_windows["true_fvg_ob_context"],
            "smt_divergence": candle_windows["smt"],
            "liquidity_sweep": candle_windows["sweep"],
            "displacement": candle_windows["displacement"],
            "m1_m5_confirmation": candle_windows["execution_confirmation"],
        },
        "HTF": analysis[htf],
        "MTF": analysis[mtf],
        "LTF": analysis[ltf],
        "EXECUTION": analysis[ltf],
        "m5_candles": analysis[ltf].get("recent_candles", []),
        "m1_candles": [],
        "WEEKLY": analysis.get(weekly_tf, _empty_timeframe_state(weekly_tf)),
        "DAILY": analysis.get(daily_tf, _empty_timeframe_state(daily_tf)),
        "DAILY_CONTEXT": background_state,
        "DAILY_CONTEXT_FALLBACK": analysis.get(daily_fallback_tf, _empty_timeframe_state(daily_fallback_tf)),
        "D1": analysis.get(daily_tf, _empty_timeframe_state(daily_tf)),
        "external_liquidity": external_liquidity,
        "h1_m15_alignment": h1_m15_alignment,
        "previous_day_context": previous_day_context,
        "opening_gaps": opening_gaps,
        "visual_concepts": visual_concepts,
        "correlated": {},
    }


def _simulate_outcome(direction, entry, sl, tp, future_df, symbol=""):
    spread_pips = float(os.getenv("BACKTEST_SPREAD_PIPS", "1.0"))
    slippage_pips = float(os.getenv("BACKTEST_SLIPPAGE_PIPS", "0.2"))
    pip_size = 0.01 if "JPY" in str(symbol) else 0.0001
    spread_cost = spread_pips * pip_size
    slippage_cost = slippage_pips * pip_size

    if direction == "buy":
        effective_entry = entry + spread_cost + slippage_cost
    else:
        effective_entry = entry - spread_cost - slippage_cost

    for offset, (_, candle) in enumerate(future_df.iterrows(), start=1):
        high = float(candle["high"])
        low = float(candle["low"])
        if direction == "buy":
            if low <= sl:
                return -1.0, offset
            if high >= tp:
                risk = abs(effective_entry - sl)
                reward = abs(tp - effective_entry)
                return reward / risk if risk else 0.0, offset
        else:
            if high >= sl:
                return -1.0, offset
            if low <= tp:
                risk = abs(sl - effective_entry)
                reward = abs(effective_entry - tp)
                return reward / risk if risk else 0.0, offset
    return 0.0, len(future_df)


def run_strategy_backtest(symbols):
    _require_mt5()
    profile = _profile_snapshot()
    history_bars = int(os.getenv("BACKTEST_HISTORY_BARS", "2400"))
    lookahead_bars = int(os.getenv("BACKTEST_LOOKAHEAD_BARS", "24"))
    step_bars = max(1, int(os.getenv("BACKTEST_STEP_BARS", "24")))
    warmup_bars = max(200, int(os.getenv("BACKTEST_WARMUP_BARS", "300")))
    progress_logs = os.getenv("BACKTEST_PROGRESS_LOGS", "false").lower() in ("1", "true", "yes")

    all_trades = []
    equity = 10000.0
    equity_curve = [equity]
    symbol_stats = {}

    for symbol_index, symbol in enumerate(symbols, start=1):
        if progress_logs:
            print(f"[BACKTEST] {symbol_index}/{len(symbols)} {symbol} ...")
        htf = profile["htf_timeframe"]
        mtf = profile["mtf_timeframe"]
        ltf = profile["ltf_timeframe"]
        weekly_tf = str(profile.get("weekly_timeframe", "W1")).upper()
        daily_tf = str(profile.get("daily_timeframe", "D1")).upper()
        daily_fallback_tf = str(profile.get("daily_context_fallback_timeframe", "H4")).upper()
        base_fetch = _concept_candle_windows()["fetch_per_timeframe"]
        frames_full = {
            htf: _fetch_rates(symbol, htf, max(history_bars, _live_standard_fetch_bars(htf, base_fetch))),
            mtf: _fetch_rates(symbol, mtf, max(history_bars, _live_standard_fetch_bars(mtf, base_fetch))),
            ltf: _fetch_rates(symbol, ltf, max(history_bars, _live_standard_fetch_bars(ltf, base_fetch))),
            weekly_tf: _fetch_rates(symbol, weekly_tf, max(260, _live_standard_fetch_bars(weekly_tf, base_fetch), history_bars // 24)),
            daily_tf: _fetch_rates(symbol, daily_tf, max(370, _live_standard_fetch_bars(daily_tf, base_fetch), history_bars // 4)),
        }
        if daily_fallback_tf and daily_fallback_tf not in frames_full:
            frames_full[daily_fallback_tf] = _fetch_rates(symbol, daily_fallback_tf, max(720, _live_standard_fetch_bars(daily_fallback_tf, base_fetch), history_bars // 2))
        ltf_df = frames_full[ltf]
        if ltf_df.empty or len(ltf_df) <= warmup_bars + lookahead_bars:
            continue

        symbol_trades = []
        symbol_equity = 10000.0
        symbol_curve = [symbol_equity]
        i = warmup_bars
        while i < len(ltf_df) - lookahead_bars:
            current_time = ltf_df.iloc[i]["time"]
            if not (in_london_session(current_time) or in_newyork_session(current_time)):
                i += step_bars
                continue
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

            unified_setup = evaluate_unified_setup(
                symbol,
                price,
                analysis,
                smt={"confirmed": False},
                killzone_active=True,
            )
            if not unified_setup.get("executable"):
                i += step_bars
                continue

            direction = unified_setup["direction"]
            retracement = unified_setup.get("retracement") or {}
            plan = unified_setup.get("plan") or {}
            sl = float(plan.get("sl", 0.0) or 0.0)
            tp = float(plan.get("tp", 0.0) or 0.0)
            risk = abs(price - sl)
            reward = abs(tp - price)
            if plan.get("order_type") != "market" or risk <= 0 or reward < risk * 1.5:
                i += step_bars
                continue
            future_df = ltf_df.iloc[i + 1 : i + 1 + lookahead_bars]
            result, bars_held = _simulate_outcome(direction, price, sl, tp, future_df, symbol=symbol)

            trade = {
                "symbol": symbol,
                "direction": direction,
                "entry": price,
                "sl": sl,
                "tp": tp,
                "result": result,
                "opened_at": current_time.isoformat(),
                "bars_held": bars_held,
                "sequence": [state["name"] for state in unified_setup["states"]],
                "retracement": retracement,
            }
            all_trades.append(trade)
            symbol_trades.append(trade)
            equity += result * 100.0
            equity_curve.append(equity)
            symbol_equity += result * 100.0
            symbol_curve.append(symbol_equity)
            i += max(bars_held, step_bars)

        if symbol_trades:
            symbol_stats[symbol] = calculate_metrics(symbol_trades, symbol_curve)

    metrics = calculate_metrics(all_trades, equity_curve)
    if progress_logs:
        print(
            "[BACKTEST] completed "
            f"{len(symbols)} symbols | trades={metrics.get('trades')} "
            f"win_rate={metrics.get('win_rate')} profit_factor={metrics.get('profit_factor')}"
        )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "profile": profile,
        "symbols": symbols,
        "metrics": metrics,
        "symbol_metrics": symbol_stats,
        "trades_sample": all_trades[:25],
    }


def generate_latest_approval(symbols=None, report_path=None):
    symbols = symbols or [item.strip().upper() for item in os.getenv("SYMBOLS", "").split(",") if item.strip()]
    report = run_strategy_backtest(symbols)
    report_path = Path(report_path or os.getenv("BACKTEST_REPORT_PATH", "backtest/latest_approval.json"))
    if not report_path.is_absolute():
        report_path = Path(__file__).resolve().parent.parent / report_path
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    return report
