import os
from supabase import create_client


"""
Test helper: persist a sample trade log to Supabase using the official client.
Usage:
  set SUPABASE_URL and SUPABASE_KEY env vars, then run:
    python scripts/test_webhook.py
"""

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

trade = {
    "symbol": "BTCUSD",
    "direction": "buy",
    "entry": 42000.0,
    "sl": 41900.0,
    "tp": 42500.0,
    "lot": 0.01,
    "ml_probability": 0.87,
    "status": "OPEN",
}


def main():
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("SUPABASE_URL and SUPABASE_KEY must be set to run this test script")
        return

    client = create_client(SUPABASE_URL, SUPABASE_KEY)
    print(f"Persisting test trade to Supabase via client to table bot_logs")
    res = client.table("bot_logs").insert({"event": "trade", "payload": trade}).execute()
    print("Result:", getattr(res, 'data', res))


if __name__ == '__main__':
    main()
