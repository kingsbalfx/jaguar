import json
import os
import subprocess
import sys
import time
from collections import OrderedDict
from pathlib import Path

from utils.mt5_credentials import fetch_all_mt5_credentials


BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = Path(os.getenv("MULTI_ACCOUNT_CONFIG", BASE_DIR / "accounts.example.json"))


def _env_truthy(name, default="false"):
    return os.getenv(name, default).lower() in ("1", "true", "yes", "on")


def _split_csv(value):
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


def _indexed_env_accounts():
    accounts = []
    index = 1
    found_any = False
    base_api_port = int(os.getenv("MULTI_ACCOUNT_BASE_API_PORT", "8000"))
    while True:
        prefix = f"ACCOUNT_{index}_"
        enabled = _env_truthy(f"{prefix}ENABLED", "false")
        login = os.getenv(f"{prefix}LOGIN", "").strip()

        if not enabled and not login:
            if found_any:
                break
            index += 1
            continue

        found_any = True
        if not enabled:
            index += 1
            continue
        if not login:
            raise RuntimeError(f"{prefix}ENABLED=true but {prefix}LOGIN is missing")

        account = {
            "enabled": True,
            "login": login,
            "bot_id": os.getenv(f"{prefix}BOT_ID", f"mt5_bot_{login}"),
        }

        api_port = os.getenv(f"{prefix}API_PORT", "").strip()
        if api_port:
            account["api_port"] = int(api_port)
        else:
            account["api_port"] = base_api_port + (index - 1)

        mt5_path = os.getenv(f"{prefix}MT5_PATH", "").strip()
        if mt5_path:
            account["mt5_path"] = mt5_path

        password = os.getenv(f"{prefix}PASSWORD", "").strip()
        if password:
            account["password"] = password

        server = os.getenv(f"{prefix}SERVER", "").strip()
        if server:
            account["server"] = server

        symbols = _split_csv(os.getenv(f"{prefix}SYMBOLS", ""))
        if symbols:
            account["symbols"] = symbols

        backtest_report_path = os.getenv(f"{prefix}BACKTEST_REPORT_PATH", "").strip()
        if backtest_report_path:
            account["backtest_report_path"] = backtest_report_path
        else:
            account["backtest_report_path"] = f"backtest/latest_approval_{login}.json"

        extra_env_raw = os.getenv(f"{prefix}EXTRA_ENV_JSON", "").strip()
        if extra_env_raw:
            try:
                account["extra_env"] = json.loads(extra_env_raw)
            except Exception:
                pass

        if account["enabled"]:
            accounts.append(account)
        index += 1

    return accounts


def _json_env_accounts():
    raw = os.getenv("MULTI_ACCOUNT_ACCOUNTS_JSON", "").strip()
    if not raw:
        return []
    payload = json.loads(raw)
    accounts = payload.get("accounts") if isinstance(payload, dict) else payload
    return [account for account in (accounts or []) if account.get("enabled", True)]


def _server_accounts():
    if not _env_truthy("MULTI_ACCOUNT_LOAD_SERVER", "true"):
        return []
    try:
        credentials = fetch_all_mt5_credentials()
    except Exception as exc:
        print(f"[MULTI] Server account load skipped: {exc}")
        return []

    accounts = []
    for row in credentials:
        login = str(row.get("login") or "").strip()
        if not login:
            continue
        accounts.append(
            {
                "enabled": True,
                "login": login,
                "bot_id": f"mt5_bot_{login}",
                "password": row.get("password"),
                "server": row.get("server"),
                "source": "server",
            }
        )
    return accounts


def _merge_accounts(*groups):
    merged = OrderedDict()
    for group in groups:
        for account in group:
            login = str(account.get("login") or "").strip()
            if not login:
                continue
            current = merged.get(login, {})
            merged[login] = {**current, **account}

    base_api_port = int(os.getenv("MULTI_ACCOUNT_BASE_API_PORT", "8000"))
    for offset, login in enumerate(merged.keys()):
        account = merged[login]
        if account.get("api_port") is None:
            account["api_port"] = base_api_port + offset
        if not account.get("backtest_report_path"):
            account["backtest_report_path"] = f"backtest/latest_approval_{login}.json"

    return list(merged.values())


def load_accounts():
    env_accounts = _json_env_accounts()
    if not env_accounts:
        env_accounts = _indexed_env_accounts()

    server_accounts = _server_accounts()
    accounts = _merge_accounts(server_accounts, env_accounts)

    if not accounts and _env_truthy("MULTI_ACCOUNT_LOAD_CONFIG", "true"):
        with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
            payload = json.load(fh)
        config_accounts = [account for account in (payload.get("accounts") or []) if account.get("enabled", True)]
        accounts = _merge_accounts(server_accounts, env_accounts, config_accounts)
    if not accounts:
        raise RuntimeError(
            f"No accounts configured in env, server, or {CONFIG_PATH}. "
            "Use mt5_credentials rows, MULTI_ACCOUNT_ACCOUNTS_JSON, or ACCOUNT_1_LOGIN / ACCOUNT_2_LOGIN..."
        )
    return accounts


def build_env(account):
    env = os.environ.copy()
    env["MULTI_ACCOUNT_CHILD"] = "1"
    env["BOT_ID"] = str(account.get("bot_id") or f"mt5_bot_{account['login']}")
    env["MT5_ACCOUNT_LOGIN"] = str(account["login"])
    if account.get("password"):
        env["MT5_ACCOUNT_PASSWORD"] = str(account["password"])
    if account.get("server"):
        env["MT5_ACCOUNT_SERVER"] = str(account["server"])
    if account.get("api_port") is not None:
        env["API_PORT"] = str(account["api_port"])
    if account.get("mt5_path"):
        env["MT5_PATH"] = str(account["mt5_path"])
    if account.get("symbols"):
        env["SYMBOLS"] = ",".join(account["symbols"])
    if account.get("backtest_report_path"):
        env["BACKTEST_REPORT_PATH"] = str(account["backtest_report_path"])
    if account.get("extra_env"):
        for key, value in account["extra_env"].items():
            env[str(key)] = str(value)
    return env


def spawn_account(account):
    env = build_env(account)
    command = [sys.executable, "main.py"]
    return subprocess.Popen(command, cwd=str(BASE_DIR), env=env)


def _terminal_key(account):
    return (account.get("mt5_path") or os.getenv("MT5_PATH") or "<default_mt5_terminal>").strip().lower()


def main():
    accounts = load_accounts()
    allow_shared_terminal = _env_truthy("MULTI_ACCOUNT_ALLOW_SHARED_TERMINAL", "false")
    processes = []
    restart_on_exit = _env_truthy("MULTI_ACCOUNT_RESTART_ON_EXIT", "false")
    used_terminals = set()
    try:
        for account in accounts:
            terminal_key = _terminal_key(account)
            if not allow_shared_terminal and terminal_key in used_terminals:
                print(
                    f"[MULTI] Skipping account {account['login']} because it shares MT5 terminal "
                    f"'{terminal_key}' with another running account. Set a unique ACCOUNT_n_MT5_PATH "
                    f"for each account or enable MULTI_ACCOUNT_ALLOW_SHARED_TERMINAL=true at your own risk."
                )
                continue
            process = spawn_account(account)
            processes.append((account, process))
            used_terminals.add(terminal_key)
            print(
                f"[MULTI] Started account {account['login']} "
                f"(bot_id={account.get('bot_id')}, pid={process.pid})"
            )
            time.sleep(2)

        while True:
            for account, process in list(processes):
                if process.poll() is not None:
                    processes.remove((account, process))
                    print(f"[MULTI] Account {account['login']} exited with code {process.returncode}.")
                    if restart_on_exit:
                        restarted = spawn_account(account)
                        processes.append((account, restarted))
                        print(
                            f"[MULTI] Restarted account {account['login']} "
                            f"(bot_id={account.get('bot_id')}, pid={restarted.pid})"
                        )
            if not processes:
                raise RuntimeError("All multi-account bot processes have exited.")
            time.sleep(5)
    finally:
        for _, process in processes:
            if process.poll() is None:
                process.terminate()


if __name__ == "__main__":
    main()
