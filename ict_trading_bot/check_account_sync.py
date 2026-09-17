"""Diagnostic: local -> Supabase account sync + live mirror peer set."""
import json
import os
import sys

from dotenv import load_dotenv

load_dotenv()

OUT = open("check_account_sync.out", "w", encoding="utf-8")


def emit(*parts):
    line = " ".join(str(part) for part in parts)
    print(line)
    OUT.write(line + "\n")
    OUT.flush()

from multi_account_runner import load_accounts, read_active_accounts, sync_accounts_to_server  # noqa: E402

accounts = load_accounts(strict=False)
emit("ACCOUNTS:", [a.get("login") for a in accounts])
emit("SOURCES:", sorted({str(a.get("source")) for a in accounts}))

sync = sync_accounts_to_server(accounts)
emit("SYNC:", json.dumps(sync))

emit("REGISTRY:", json.dumps(read_active_accounts()))

try:
    from risk.mirror_trading import _get_peers

    emit("PEERS:", json.dumps(_get_peers()))
except Exception as exc:
    emit("PEERS ERROR:", exc)

try:
    from config.supabase_credentials import resolve_supabase_credentials
    from supabase import create_client

    resolved = resolve_supabase_credentials()
    client = create_client(resolved["url"], resolved["service_key"] or resolved["key"])
    table = os.getenv("MT5_CREDENTIALS_TABLE", "mt5_credentials")
    try:
        rows = client.table(table).select("login,server,active,api_port").limit(50).execute()
        data = getattr(rows, "data", None) or []
        emit("SUPABASE ROWS:", len(data), json.dumps(data[:12]))
    except Exception as exc:
        emit("SUPABASE SELECT ERROR:", exc)
except Exception as exc:
    emit("SUPABASE CLIENT ERROR:", exc)

OUT.close()
sys.exit(0)
