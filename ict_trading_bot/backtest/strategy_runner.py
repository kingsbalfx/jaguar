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
from ict_concepts.fvg import detect_fvg_from_df
from ict_concepts.liquidity import detect_liquidity_zones
from risk.sl_tp_engine import calculate_sl_tp
from strategy.entry_model import check_entry
from strategy.liquidity_filter import liquidity_taken


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
        "D1": mt5.TIMEFRAME_D1,
    }
    return mapping[tf]


def _profile_snapshot():
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


def _fetch_rates(symbol, timeframe, bars):
    rates = mt5.copy_rates_from_pos(symbol, _tf_to_mt5(timeframe), 0, bars)
    if rates is None or len(rates) == 0:
        return pd.DataFrame()
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s", utc=True)
    return df


def _swings_from_df(df):
    swings = []
    if df is None or len(df) < 5:
        return swings
    for i in range(2, len(df) - 2):
        high = df.iloc[i]["high"]
        low = df.iloc[i]["low"]
        if high > df.iloc[i - 1]["high"] and high > df.iloc[i + 1]["high"]:
            swings.append({"type": "high", "price": float(high), "index": int(i)})
        if low < df.iloc[i - 1]["low"] and low < df.iloc[i + 1]["low"]:
            swings.append({"type": "low", "price": float(low), "index": int(i)})
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
        hi = float(df.iloc[i]["high"])
        lo = float(df.iloc[i]["low"])
        prev_hi = float(df.iloc[i - 1]["high"])
        prev_lo = float(df.iloc[i - 1]["low"])
        next_hi = float(df.iloc[i + 1]["high"])
        next_lo = float(df.iloc[i + 1]["low"])
        if hi > prev_hi and hi > next_hi:
            obs.append(
                {
                    "type": "bearish",
                    "high": prev_hi,
                    "low": prev_lo,
                    "index": int(i),
                    "timeframe": timeframe,
                    "id": f"{symbol}|{timeframe}|bearish|{i}",
                }
            )
        if lo < prev_lo and lo < next_lo:
            obs.append(
                {
                    "type": "bullish",
                    "high": prev_hi,
                    "low": prev_lo,
                    "index": int(i),
                    "timeframe": timeframe,
                    "id": f"{symbol}|{timeframe}|bullish|{i}",
                }
            )
    return obs


def _analysis_from_frames(symbol, price, frames, profile):
    htf = profile["htf_timeframe"]
    mtf = profile["mtf_timeframe"]
    ltf = profile["ltf_timeframe"]

    analysis = {}
    for timeframe, df in frames.items():
        if df is None or len(df) < 20:
            return None
        swings = _swings_from_df(df)
        analysis[timeframe] = {
            "trend": _trend_from_swings(swings),
            "fib": _fib_from_df(df),
            "fvgs": [
                {**fvg, "timeframe": timeframe}
                for fvg in detect_fvg_from_df(df)
            ],
            "order_blocks": _order_blocks_from_df(symbol, timeframe, df),
            "liquidity": detect_liquidity_zones(swings),
        }

    overall_trend = analysis[htf]["trend"]
    if overall_trend not in ("bullish", "bearish"):
        mtf_trend = analysis[mtf]["trend"]
        if mtf_trend in ("bullish", "bearish"):
            overall_trend = mtf_trend
        elif profile["allow_ltf_trend_fallback"]:
            ltf_trend = analysis[ltf]["trend"]
            if ltf_trend in ("bullish", "bearish"):
                overall_trend = ltf_trend

    return {
        "overall_trend": overall_trend,
        "price": price,
        "timeframes": {"HTF": htf, "MTF": mtf, "LTF": ltf},
        "HTF": analysis[htf],
        "MTF": analysis[mtf],
        "LTF": analysis[ltf],
        "D1": analysis.get("D1", {}),
        "correlated": {},
    }


def _rule_quality_from_context(signal, daily_trend):
    score = 0
    if signal.get("fib_zone") in ["discount", "premium"]:
        score += 1
    fvg = signal.get("fvg")
    if isinstance(fvg, dict) and fvg.get("timeframe") == "M15":
        score += 1
    htf_ob = signal.get("htf_ob")
    if isinstance(htf_ob, dict) and htf_ob.get("timeframe") in ["H1", "H4"]:
        score += 1
    if daily_trend == signal.get("trend"):
        score += 1
    return score >= 3


def _simulate_outcome(direction, entry, sl, tp, future_df):
    for offset, (_, candle) in enumerate(future_df.iterrows(), start=1):
        high = float(candle["high"])
        low = float(candle["low"])
        if direction == "buy":
            if low <= sl:
                return -1.0, offset
            if high >= tp:
                risk = abs(entry - sl)
                reward = abs(tp - entry)
                return reward / risk if risk else 0.0, offset
        else:
            if high >= sl:
                return -1.0, offset
            if low <= tp:
                risk = abs(sl - entry)
                reward = abs(entry - tp)
                return reward / risk if risk else 0.0, offset
    return 0.0, len(future_df)


def run_strategy_backtest(symbols):
    _require_mt5()
    profile = _profile_snapshot()
    history_bars = int(os.getenv("BACKTEST_HISTORY_BARS", "600"))
    lookahead_bars = int(os.getenv("BACKTEST_LOOKAHEAD_BARS", "24"))
    step_bars = max(1, int(os.getenv("BACKTEST_STEP_BARS", "12")))
    warmup_bars = max(150, int(os.getenv("BACKTEST_WARMUP_BARS", "200")))
    progress_logs = os.getenv("BACKTEST_PROGRESS_LOGS", "true").lower() in ("1", "true", "yes")

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
        frames_full = {
            htf: _fetch_rates(symbol, htf, history_bars),
            mtf: _fetch_rates(symbol, mtf, history_bars),
            ltf: _fetch_rates(symbol, ltf, history_bars),
            "D1": _fetch_rates(symbol, "D1", max(400, history_bars // 4)),
        }
        ltf_df = frames_full[ltf]
        if ltf_df.empty or len(ltf_df) <= warmup_bars + lookahead_bars:
            continue

        symbol_trades = []
        symbol_equity = 10000.0
        symbol_curve = [symbol_equity]
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

            liquidity_ok = liquidity_taken(price, analysis["MTF"]["liquidity"], direction)
            smt_ok = True
            daily_trend = analysis["D1"].get("trend")
            rule_ok = _rule_quality_from_context(signal, daily_trend)
            ml_ok = True

            if profile["rule_quality_required"] and not rule_ok:
                i += step_bars
                continue

            confirmation_flags = {
                "liquidity": liquidity_ok,
                "smt": smt_ok,
                "rule_quality": rule_ok,
                "ml": ml_ok,
            }
            if profile["count_fundamentals_as_confirmation"]:
                confirmation_flags["fundamentals"] = True

            if sum(1 for passed in confirmation_flags.values() if passed) < profile["min_extra_confirmations"]:
                i += step_bars
                continue

            htf_ob = signal.get("htf_ob") or {}
            if htf_ob.get("low") is None or htf_ob.get("high") is None:
                i += step_bars
                continue

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
                "confirmations": [name for name, passed in confirmation_flags.items() if passed],
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
