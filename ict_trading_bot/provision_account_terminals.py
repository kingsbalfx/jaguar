"""One-off helper: provision the portable MT5 terminal for every configured account.

Same operation the bot performs automatically at spawn time when
``MULTI_ACCOUNT_AUTO_CREATE_TERMINAL=true`` (equivalent to
``setup_multi_account_mt5.ps1``). Run:

    .\\.venv\\Scripts\\python.exe provision_account_terminals.py
"""
import json
import os

from dotenv import load_dotenv

load_dotenv()

from multi_account_runner import ensure_account_terminal, load_accounts  # noqa: E402
from utils.mt5_terminal import master_terminal, multi_root  # noqa: E402

print(f"master install : {master_terminal()}")
print(f"multi root     : {multi_root()}")
print(f"auto create    : {os.getenv('MULTI_ACCOUNT_AUTO_CREATE_TERMINAL')}")
print("-" * 70)

for account in load_accounts(strict=False):
    login = account.get("login")
    if not account.get("password") or not account.get("server"):
        print(f"{login}: skipped (no password/server in this source)")
        continue
    result = ensure_account_terminal(account)
    status = "OK  " if result.get("ok") else "FAIL"
    print(f"{status} login={login} | source={result.get('source')} | path={result.get('path') or '-'}")
    if not result.get("ok"):
        print(f"      reason={result.get('reason')}")
        print(f"      checked={json.dumps(result.get('checked'))}")
