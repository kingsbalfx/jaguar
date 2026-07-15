# Mirror Trading Setup Guide

## Overview

The Mirror Trading System allows trades executed on **any** multi-account child process to be automatically mirrored across all other accounts. When Account A executes a trade, it broadcasts the signal to Accounts B, C, etc., via their HTTP APIs.

### Key Architecture

```
Account A (port 8000)
  ├── Scans market -> finds trade -> EXECUTES
  ├── Broadcasts signal to Account B (port 8001) via HTTP POST
  ├── Broadcasts signal to Account C (port 8002) via HTTP POST
  ├── Pushes signal to Supabase (cross-machine)
  └── Saves signal to shared file (local fallback)

Account B (port 8001)
  ├── Receives signal at POST /api/mirror/signal
  ├── Validates (duplicate check, cooldown, not self-signal)
  ├── Calculates lot size proportional to Account B's balance
  └── Executes if valid

Account C (port 8002) -- same as Account B
```

### Strategy Detection

Both ICT State Machine and **Kingsbalfx** trades are mirrored:

- `source_strategy: "ict_state_machine"` — standard ICT 12-gate trade
- `source_strategy: "kingsbalfx"` — Kingsbalfx fallback trade
- The receiving account logs which strategy the leader used
- Both strategies use the same execution pipeline (entry, SL, TP are mirrored)

### Position Sizing

Each account calculates its own lot size based on:

```
lot_size = risk_amount / (stop_loss_distance * tick_value)
```

Where `risk_amount = account_balance * (MIRROR_RISK_PERCENT / 100)`

This means a $10,000 account will open a position 2x the size of a $5,000 account for the same signal.

---

## Environment Variables

### Core Mirror Settings
| Variable | Default | Description |
|---|---|---|
| `MIRROR_TRADING_ENABLED` | `true` | Master on/off switch |
| `MIRROR_AUTO_OPEN` | `true` | Automatically open trades when receiving signals |
| `MIRROR_COOLDOWN_SECONDS` | `300` (5 min) | Minimum time between mirror trades for same symbol |
| `MIRROR_API_TIMEOUT` | `10` | HTTP request timeout to peer APIs |
| `MIRROR_EXCLUDE_SAME` | `true` | Skip broadcasting to self (same login) |
| `MIRROR_RISK_PERCENT` | Uses `RISK_PER_TRADE` | Risk % per trade for mirror trades |
| `BOT_API_TOKEN` | (required) | Auth token for API communication |
| `API_HOST` | `127.0.0.1` | Host for peer API connections |

### Large-Scale Settings (100+ accounts)
| Variable | Default | Description |
|---|---|---|
| `MIRROR_BROADCAST_BATCH` | `10` | Number of peers per HTTP broadcast batch |
| `MIRROR_BROADCAST_DELAY` | `0.5` | Seconds delay between batches |
| `MIRROR_SUPABASE_TABLE` | `mirror_signals` | Supabase table for signal coordination |
| `MIRROR_SUPABASE_DISCOVERY` | `true` | Enable peer discovery via Supabase |
| `MT5_CREDENTIALS_TABLE` | `mt5_credentials` | Supabase table with account details |
| `SUPABASE_URL` | (required) | Your Supabase project URL |
| `SUPABASE_SERVICE_KEY` | (required) | Supabase service role key |
| `SUPABASE_KEY` | fallback | Fallback Supabase key |

---

## Does It Require a SQL Run?

**NO — no SQL setup is required.** The system works entirely without SQL:

1. **Local mode** (same machine): works via shared JSON file at `data/mirror_signals.json` — no database needed
2. **Supabase mode**: uses the Supabase REST API with `upsert()` — the table is auto-created by Supabase on first write
3. **No Supabase RPC or raw SQL** is needed; everything uses the standard Supabase client library

However, if you want to **pre-create** the Supabase table for cleaner setup, run this SQL once in the Supabase SQL Editor:

```sql
CREATE TABLE IF NOT EXISTS public.mirror_signals (
    id BIGSERIAL PRIMARY KEY,
    signal_id TEXT UNIQUE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    data JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_mirror_signal_id ON public.mirror_signals(signal_id);
CREATE INDEX IF NOT EXISTS idx_mirror_expires ON public.mirror_signals(expires_at);
```

This is **optional** — the system creates it automatically via upsert() if it doesn't exist.

---

## Can It Handle 100+ Accounts?

**YES — designed specifically for scale.** Three mechanisms coordinate signals across hundreds of accounts:

### 1. HTTP Broadcast (batched)
- Accounts on the same machine use HTTP POST to each other's APIs
- Batched to avoid network overload (`MIRROR_BROADCAST_BATCH=10`, `MIRROR_BROADCAST_DELAY=0.5s`)
- Example: 200 accounts broadcast in 20 batches of 10 (about 10 seconds total)

### 2. Supabase Push/Fetch (cross-machine)
- **Primary channel for cross-server coordination**
- Push: leader writes signal to Supabase table
- Fetch: each follower's periodic scan picks up signals from Supabase
- No direct HTTP needed between accounts on different machines

### 3. Shared File (local same-machine)
- Fallback for accounts on the same filesystem
- Located at `data/mirror_signals.json`
- Keeps last 500 signals only (auto-cleanup)

### Discovery for 100+ Accounts

Peers can be discovered automatically from:
1. **Multi-account config** (`.env` or `accounts.example.json`)
2. **Supabase mt5_credentials table** (set `MIRROR_SUPABASE_DISCOVERY=true`)
   - Filter by `enabled=true`
   - Includes `login`, `api_port`, `api_host` per account
   - No duplicates between local and Supabase configs

---

## API Endpoints

Each child process exposes these endpoints from `risk/mirror_trading.py`:

### `POST /api/mirror/signal`
Receive a mirror signal from another account.

**Request body:**
```json
{
  "signal_id": "MIRROR_3611136_EURUSD_buy_1700000000000",
  "symbol": "EURUSD",
  "direction": "buy",
  "entry_price": 1.08750,
  "stop_loss": 1.08500,
  "take_profit": 1.09250,
  "source_login": "3611136",
  "source_strategy": "ict_state_machine",
  "created_at": "2024-01-01T00:00:00Z"
}
```

**Response (executed):**
```json
{
  "action": "executed",
  "reason": "mirror_trade_executed",
  "symbol": "EURUSD",
  "direction": "buy",
  "volume": 0.05,
  "entry": 1.08750,
  "sl": 1.08500,
  "tp": 1.09250,
  "balance": 5000.00,
  "ticket": 12345678,
  "signal_id": "MIRROR_3611136_EURUSD_buy_1700000000000",
  "source_strategy": "ict_state_machine",
  "source_login": "3611136"
}
```

**Response (skipped):**
```json
{
  "action": "skipped",
  "reason": "mirror_cooldown_active_for_EURUSD",
  "signal_id": "...",
  "symbol": "EURUSD",
  "direction": "buy"
}
```

### `GET /api/mirror/status`
Returns mirror trading status for this account.

### `GET /api/mirror/peers`
Lists discovered peer accounts (local config + Supabase).

### `GET /api/mirror/health`
Lightweight health check for the mirror system.

---

## How It Works

### Leader Flow (when trade opens)
1. Trade is executed in `main.py` `_process_scan_result()`
2. Mirror system creates a signal with:
   - `source_strategy` = detected from `request["strategy"]` ("kingsbalfx" or "ict_state_machine")
   - `reason` = `"trade_executed_kingsbalfx"` or `"trade_executed_ict_state_machine"`
3. `broadcast_signal()` runs three channels:
   a. Saves to shared JSON file (local same-machine)
   b. Pushes to Supabase (cross-machine coordination)
   c. Sends HTTP POST to each peer's API (batched for scale)

### Follower Flow (when signal arrives)
1. Validates: not duplicate, within cooldown, not self-signal
2. Checks: MT5 connected, account has balance, no opposite positions
3. Calculates: lot size proportional to follower's balance
4. Executes: via `execute_trade()` with leader's entry/SL/TP

### Fallback Flow (periodic scan)
1. Every scan cycle in `run_bot()`, calls `check_pending_mirror_signals()`
2. Reads pending signals from shared file AND Supabase
3. Processes any unseen, non-expired signals
4. This catches signals missed during HTTP broadcast (offline peers)

## Authentication

Each API request includes the `BOT_API_TOKEN` in headers:
- `x-bot-api-token: YOUR_TOKEN`
- `Authorization: Bearer YOUR_TOKEN`

All child processes must share the same `BOT_API_TOKEN`.

## Configuration Example

```json
// accounts.example.json
{
  "accounts": [
    {
      "enabled": true,
      "login": "3611136",
      "bot_id": "windows_mt5_bot_3611136",
      "api_port": 8000,
      "symbols": ["EURUSD", "GBPUSD"]
    },
    {
      "enabled": true,
      "login": "7654321",
      "bot_id": "windows_mt5_bot_7654321",
      "api_port": 8001,
      "symbols": ["EURUSD", "GBPUSD"]
    }
  ]
}
```

### .env additions for mirror trading:
```env
# Required
BOT_API_TOKEN=your-secret-token

# Optional overrides
MIRROR_TRADING_ENABLED=true
MIRROR_AUTO_OPEN=true
MIRROR_COOLDOWN_SECONDS=300
MIRROR_RISK_PERCENT=1.0

# For 100+ accounts / cross-machine
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=your-service-role-key
MIRROR_SUPABASE_TABLE=mirror_signals
MIRROR_BROADCAST_BATCH=10
MIRROR_BROADCAST_DELAY=0.5
```

## File Structure

```
ict_trading_bot/
├── risk/
│   ├── mirror_trading.py       # Mirror trading system
│   └── MIRROR_TRADING_SETUP.md # This documentation
├── data/
│   └── mirror_signals.json     # Shared signal file (auto-created)
├── bot_api.py                  # Modified to register mirror endpoints
└── main.py                     # Modified to broadcast signals on trade
```
