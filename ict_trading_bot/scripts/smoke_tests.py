#!/usr/bin/env python3
"""
Smoke tests for the trading bot.
Run: python scripts/smoke_tests.py
"""
import sys
import requests
import json
from datetime import datetime

BASE_URL = "https://your-bot-host:8000"

def test(name, fn):
    try:
        fn()
        print(f"✓ {name}")
        return True
    except Exception as e:
        print(f"✗ {name}: {e}")
        return False

def main():
    print("Running Python bot smoke tests...\n")
    
    passed = 0
    failed = 0

    if test("Bot health endpoint", lambda: (
        resp := requests.get(f"{BASE_URL}/health", timeout=3),
        resp.raise_for_status(),
        resp.json()["status"] == "ok"
    )[-1]):
        passed += 1
    else:
        failed += 1

    if test("Bot status endpoint", lambda: (
        resp := requests.get(f"{BASE_URL}/status", timeout=3),
        resp.raise_for_status()
    )[-1]):
        passed += 1
    else:
        failed += 1

    if test("Bot control endpoint (auth check)", lambda: (
        resp := requests.post(f"{BASE_URL}/control", json={"action": "test"}),
        resp.status_code < 500  # should fail gracefully
    )[-1]):
        passed += 1
    else:
        failed += 1

    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed > 0 else 0)

if __name__ == "__main__":
    main()
