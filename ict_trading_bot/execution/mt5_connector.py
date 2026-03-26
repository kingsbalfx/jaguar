try:
    import MetaTrader5 as mt5
except Exception as e:
    mt5 = None
    _MT5_IMPORT_ERROR = e
import time
import os

from utils.mt5_credentials import fetch_mt5_credentials


def _require_mt5():
    if mt5 is None:
        raise RuntimeError(
            "MetaTrader5 package not available on this platform. "
            "Run the bot on Windows with MT5 installed, or set MT5_DISABLED=1 "
            "to skip live trading in Linux environments."
        )


def _build_initialize_kwargs(login_value, password, server):
    kwargs = {
    }

    mt5_path = os.getenv("MT5_PATH", "").strip()
    if mt5_path:
        kwargs["path"] = mt5_path

    timeout_raw = os.getenv("MT5_TIMEOUT", "").strip()
    if timeout_raw:
        try:
            kwargs["timeout"] = int(timeout_raw)
        except ValueError:
            pass
    elif os.getenv("MT5_PORTABLE", "").lower() in ("1", "true", "yes"):
        # Portable terminals often need longer to spin up on first launch.
        kwargs["timeout"] = 180000

    if os.getenv("MT5_PORTABLE", "").lower() in ("1", "true", "yes"):
        kwargs["portable"] = True

    return kwargs


def _build_login_kwargs(login_value, password, server):
    return {
        "login": login_value,
        "password": password,
        "server": server,
    }


def _env_int(name, default):
    try:
        return int(os.getenv(name, str(default)))
    except Exception:
        return default


def _portable_enabled():
    return os.getenv("MT5_PORTABLE", "").lower() in ("1", "true", "yes")


def connect(credentials=None):
    _require_mt5()
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

    def _account_matches():
        account_info = mt5.account_info()
        if account_info is None:
            return None

        account_login = str(getattr(account_info, "login", ""))
        account_server = str(getattr(account_info, "server", "")).lower()
        expected_login = str(login_value)
        expected_server = str(server).lower()

        if account_login == expected_login and account_server == expected_server:
            return account_info

        return None

    initialize_kwargs = _build_initialize_kwargs(login_value, password, server)
    login_kwargs = _build_login_kwargs(login_value, password, server)
    max_attempts = max(1, _env_int("MT5_INIT_MAX_ATTEMPTS", 4))
    retry_wait = max(5, _env_int("MT5_INIT_RETRY_WAIT_SECONDS", 15))
    mt5_path = os.getenv("MT5_PATH", "").strip()
    direct_initialize_first = (
        os.getenv("MT5_INIT_MODE", "auto").lower() in ("direct", "auto")
        and bool(mt5_path)
        and _portable_enabled()
    )

    last_error = None

    for attempt in range(1, max_attempts + 1):
        if direct_initialize_first:
            init_ok = mt5.initialize(**{**initialize_kwargs, **login_kwargs})
        else:
            init_ok = mt5.initialize(**initialize_kwargs)

        # More reliable flow on Windows: attach to the terminal first, then log in.
        if init_ok:
            account_info = _account_matches()
            if account_info is None:
                if not mt5.login(**login_kwargs):
                    last_error = mt5.last_error()
                    account_info = _account_matches()
                    if account_info is None:
                        mt5.shutdown()
                        if attempt < max_attempts:
                            print(
                                f"[BOT] MT5 login retry {attempt}/{max_attempts} for account {login_value} "
                                f"after error: {last_error}"
                            )
                            time.sleep(retry_wait)
                            continue
                        raise RuntimeError(f"MT5 login failed: {last_error}")
            break

        first_error = mt5.last_error()
        last_error = first_error

        mt5.shutdown()

        if attempt < max_attempts:
            print(
                f"[BOT] MT5 initialize retry {attempt}/{max_attempts} for account {login_value}: "
                f"{first_error}"
            )
            time.sleep(retry_wait)
            continue

        # Final fallback for setups that only accept login during initialize.
        direct_initialize_kwargs = {
            **initialize_kwargs,
            **login_kwargs,
        }
        if mt5.initialize(**direct_initialize_kwargs):
            break

        last_error = mt5.last_error()
        raise RuntimeError(
            f"MT5 initialization failed: {first_error}; fallback failed: {last_error}; path={mt5_path}"
        )

    account_info = mt5.account_info()
    if account_info is None:
        raise RuntimeError("Failed to get account info")

    print(f"Connected to MT5 | Balance: {account_info.balance}")
    return True


def reconnect(credentials=None):
    _require_mt5()
    try:
        mt5.shutdown()
    except Exception:
        pass
    return connect(credentials)


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


def get_account_snapshot():
    _require_mt5()
    account = mt5.account_info()
    if account is None:
        return None

    return {
        "login": getattr(account, "login", None),
        "server": getattr(account, "server", None),
        "balance": getattr(account, "balance", None),
        "equity": getattr(account, "equity", None),
        "profit": getattr(account, "profit", None),
        "margin": getattr(account, "margin", None),
        "margin_free": getattr(account, "margin_free", None),
        "currency": getattr(account, "currency", None),
        "company": getattr(account, "company", None),
    }
