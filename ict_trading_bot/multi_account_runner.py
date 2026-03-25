import json
import os
import subprocess
import sys
import time
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = Path(os.getenv("MULTI_ACCOUNT_CONFIG", BASE_DIR / "accounts.example.json"))


def load_accounts():
    with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
        payload = json.load(fh)
    accounts = [account for account in (payload.get("accounts") or []) if account.get("enabled", True)]
    if not accounts:
        raise RuntimeError(f"No accounts configured in {CONFIG_PATH}")
    return accounts


def build_env(account):
    env = os.environ.copy()
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
