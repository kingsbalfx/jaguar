try:
    import MetaTrader5 as mt5
except Exception:
    mt5 = None
from datetime import datetime


def _require_mt5():
    if mt5 is None:
        raise RuntimeError(
            "MetaTrader5 package not available on this platform. "
            "Run the bot on Windows with MT5 installed."
        )


def calculate_lot_size(
    symbol: str,
    risk_percent: float,
    stop_loss_pips: float
) -> float:
    """
    Calculate position size based on % risk.
    """
    _require_mt5()
    account = mt5.account_info()
    if account is None:
        raise RuntimeError("MT5 not connected")

    balance = account.balance
    symbol_info = mt5.symbol_info(symbol)

    if symbol_info is None:
        raise RuntimeError(f"Symbol info not found: {symbol}")

    pip_value = symbol_info.trade_tick_value
    risk_amount = balance * (risk_percent / 100)

    lot_size = risk_amount / (stop_loss_pips * pip_value)

    return round(lot_size, 2)


def execute_trade(
    symbol: str,
    direction: str,
    lot: float,
    sl_price: float,
    tp_price: float,
    order_type: str = "market",
    entry_price: float | None = None,
):
    """
    Execute an MT5 trade request.

    order_type:
      - market (default)
      - limit
    """
    _require_mt5()

    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        raise RuntimeError(f"No tick data for {symbol}")

    direction_lower = direction.lower()
    if direction_lower not in ("buy", "sell"):
        raise RuntimeError(f"Unsupported direction: {direction}")

    market_price = tick.ask if direction_lower == "buy" else tick.bid
    order_type_lower = (order_type or "market").lower()

    request = {
        "symbol": symbol,
        "volume": lot,
        "sl": sl_price,
        "tp": tp_price,
        "deviation": 10,
        "magic": 202401,
        "comment": "ICT_AUTO",
        "type_time": mt5.ORDER_TIME_GTC,
    }

    if order_type_lower == "limit":
        request.update({
            "action": mt5.TRADE_ACTION_PENDING,
            "type": mt5.ORDER_TYPE_BUY_LIMIT if direction_lower == "buy" else mt5.ORDER_TYPE_SELL_LIMIT,
            "price": entry_price if entry_price is not None else market_price,
            "type_filling": mt5.ORDER_FILLING_RETURN,
        })
    else:
        request.update({
            "action": mt5.TRADE_ACTION_DEAL,
            "type": mt5.ORDER_TYPE_BUY if direction_lower == "buy" else mt5.ORDER_TYPE_SELL,
            "price": market_price,
            "type_filling": mt5.ORDER_FILLING_IOC,
        })

    result = mt5.order_send(request)

    if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
        msg = getattr(result, "comment", "unknown MT5 error")
        print(f"[{datetime.now()}] Trade failed: {msg}")
        return None

    placed_price = request.get("price", market_price)
    print(
        f"[{datetime.now()}] Trade placed → "
        f"{symbol} {direction_upper(direction_lower)} | {lot} lots | "
        f"Type {order_type_lower.upper()} | Entry {placed_price} | SL {sl_price} | TP {tp_price}"
    )

    return {
        "open": True,
        "ticket": getattr(result, "order", None) or getattr(result, "deal", None),
        "symbol": symbol,
        "direction": direction_lower,
        "entry": placed_price,
        "sl": sl_price,
        "tp": tp_price,
        "lot": lot,
        "stage": 0,
        "order_type": order_type_lower,
        "mt5_retcode": getattr(result, "retcode", None),
    }


def apply_trade_action(trade: dict, action: dict):
    """
    Apply local trade-management actions safely.

    NOTE: This keeps the in-memory trade state consistent and avoids runtime crashes.
    If you want actual MT5 SL modification / partial close, wire them here with order_send.
    """
    if not trade or not action:
        return trade

    action_type = action.get("action")
    if action_type in ("move_sl", "trail"):
        new_sl = action.get("sl")
        if new_sl is not None:
            trade["sl"] = new_sl
    elif action_type == "partial_close":
        pct = float(action.get("percent", 0) or 0)
        pct = max(0.0, min(1.0, pct))
        remaining = trade.get("lot", 0) * (1.0 - pct)
        trade["lot"] = round(max(0.0, remaining), 2)
        if trade["lot"] <= 0:
            trade["open"] = False

    return trade


def direction_upper(direction_lower: str) -> str:
    return "BUY" if direction_lower == "buy" else "SELL"
