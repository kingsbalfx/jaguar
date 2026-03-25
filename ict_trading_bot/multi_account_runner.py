import json
import os
import subprocess
import sys
import time
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = Path(os.getenv("MULTI_ACCOUNT_CONFIG", BASE_DIR / "accounts.example.json"))


def _env_truthy(name, default="false"):
    return os.getenv(name, default).lower() in ("1", "true", "yes", "on")


def _split_csv(value):
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


def _indexed_env_accounts():
    accounts = []
    index = 1
    while True:
        prefix = f"ACCOUNT_{index}_"
        login = os.getenv(f"{prefix}LOGIN", "").strip()
        if not login:
            break

        account = {
            "enabled": _env_truthy(f"{prefix}ENABLED", "true"),
            "login": login,
            "bot_id": os.getenv(f"{prefix}BOT_ID", f"mt5_bot_{login}"),
        }

        api_port = os.getenv(f"{prefix}API_PORT", "").strip()
        if api_port:
            account["api_port"] = int(api_port)

        mt5_path = os.getenv(f"{prefix}MT5_PATH", "").strip()
        if mt5_path:
            account["mt5_path"] = mt5_path

        symbols = _split_csv(os.getenv(f"{prefix}SYMBOLS", ""))
        if symbols:
            account["symbols"] = symbols

        backtest_report_path = os.getenv(f"{prefix}BACKTEST_REPORT_PATH", "").strip()
        if backtest_report_path:
            account["backtest_report_path"] = backtest_report_path

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


def load_accounts():
    accounts = _json_env_accounts()
    if not accounts:
        accounts = _indexed_env_accounts()
    if not accounts:
        with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
            payload = json.load(fh)
        accounts = [account for account in (payload.get("accounts") or []) if account.get("enabled", True)]
    if not accounts:
        raise RuntimeError(
            f"No accounts configured in env or {CONFIG_PATH}. "
            "Use MULTI_ACCOUNT_ACCOUNTS_JSON or ACCOUNT_1_LOGIN / ACCOUNT_2_LOGIN..."
        )
    return accounts


def build_env(account):
    env = os.environ.copy()
    env["MULTI_ACCOUNT_CHILD"] = "1"
    env["BOT_ID"] = str(account.get("bot_id") or f"mt5_bot_{account['login']}")
    env["MT5_ACCOUNT_LOGIN"] = str(account["login"])
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


def main():
    accounts = load_accounts()
    processes = []
    try:
        for account in accounts:
            process = spawn_account(account)
            processes.append((account, process))
            print(
                f"[MULTI] Started account {account['login']} "
                f"(bot_id={account.get('bot_id')}, pid={process.pid})"
            )
            time.sleep(2)

        while True:
            for account, process in list(processes):
                if process.poll() is not None:
                    raise RuntimeError(
                        f"Account {account['login']} process exited with code {process.returncode}"
                    )
            time.sleep(5)
    finally:
        for _, process in processes:
            if process.poll() is None:
                process.terminate()


if __name__ == "__main__":
    main()
