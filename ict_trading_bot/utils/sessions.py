from datetime import datetime
import pytz
import os

def in_london_session():
    now = datetime.now(pytz.UTC).hour
    return 7 <= now <= 11

def in_newyork_session():
    now = datetime.now(pytz.UTC).hour
    return 12 <= now <= 17


def trading_session_open():
    if os.getenv("TRADE_ALL_SESSIONS", "true").lower() in ("1", "true", "yes"):
        return True
    return in_london_session() or in_newyork_session()
