try:
    import MetaTrader5 as mt5
except Exception as e:
    mt5 = None
    _MT5_IMPORT_ERROR = e
import time

from utils.mt5_credentials import fetch_mt5_credentials

def connect(credentials=None):
    if mt5 is None:
        raise RuntimeError(
            "MetaTrader5 package not available on this platform. "
            "Run the bot on Windows with MT5 installed, or set MT5_DISABLED=1 "
            "to skip live trading in Linux environments."
        )
    if credentials is None:
        credentials = fetch_mt5_credentials()

    login = credentials.get("login")
    password = credentials.get("password")
    server = credentials.get("server")

    if not login or not password or not server:
        raise RuntimeError("MT5 credentials missing (login, password, server)")

    try:
        login_value = int(login)
    except Exception:
        login_value = login

    if not mt5.initialize(login=login_value, password=password, server=server):
        last_error = mt5.last_error()
        raise RuntimeError(f"MT5 initialization failed: {last_error}")

    account_info = mt5.account_info()
    if account_info is None:
        raise RuntimeError("Failed to get account info")

    print(f"Connected to MT5 | Balance: {account_info.balance}")
    return True


def ensure_symbol(symbol):
    if not mt5.symbol_select(symbol, True):
        raise RuntimeError(f"Failed to select symbol {symbol}")


def get_price(symbol):
    """Return last market price (midpoint of ask/bid)."""
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        raise RuntimeError(f"No tick data for {symbol}")

    # prefer mid price
    try:
        return (tick.ask + tick.bid) / 2.0
    except Exception:
        return tick.last


def get_open_positions():
    """Return simplified open positions list for portfolio allocation.

    Each position is a dict: { symbol, volume, price, profit, risk }
    """
    positions = mt5.positions_get()
    if positions is None:
        return []

    out = []
    for p in positions:
        try:
            out.append({
                "symbol": p.symbol,
                "volume": p.volume,
                "price": p.price_open,
                "profit": p.profit,
                # risk placeholder (should be computed by risk manager)
                "risk": 0.5
            })
        except Exception:
            continue

    return out
