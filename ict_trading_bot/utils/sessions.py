from datetime import datetime
import pytz

def in_london_session():
    now = datetime.now(pytz.UTC).hour
    return 7 <= now <= 11

def in_newyork_session():
    now = datetime.now(pytz.UTC).hour
    return 12 <= now <= 17
