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
    tp_price: float
):
    """
    Execute a market order on MT5.
    direction: 'buy' or 'sell'
    """
    _require_mt5()

    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        raise RuntimeError(f"No tick data for {symbol}")

    price = tick.ask if direction.lower() == "buy" else tick.bid

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lot,
        "type": mt5.ORDER_TYPE_BUY if direction.lower() == "buy" else mt5.ORDER_TYPE_SELL,
        "price": price,
        "sl": sl_price,
        "tp": tp_price,
        "deviation": 10,
        "magic": 202401,
        "comment": "ICT_AUTO",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC
    }

    result = mt5.order_send(request)

    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f"[{datetime.now()}] Trade failed:", result.comment)
        return None

    print(
        f"[{datetime.now()}] Trade placed → "
        f"{symbol} {direction.upper()} | {lot} lots | SL {sl_price} | TP {tp_price}"
    )

    return result
