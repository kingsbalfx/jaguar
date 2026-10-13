# MT5 Trade History & Performance Sync

Cloud-native sync of **closed MT5 positions** into Supabase, plus per-pair
performance analytics. No local terminal, no Docker: a Vercel cron (or a manual
button) asks a hosted REST bridge for the account's deal history, pairs the MT5
IN/OUT deals into one row per closed position, stores them and rebuilds the
per-pair aggregates.

```
                            ┌──────────────────────────┐
  Vercel cron ──┐           │  services/mt5Sync.js     │
  user "Sync" ──┼──▶ run ──▶│  window → fetch → pair   │
  admin "Sync" ─┘           │  → upsert → re-aggregate │
                            └───────────┬──────────────┘
                                        │ bridge (lib/mt5-bridge.js)
                     ┌──────────────────┼───────────────────┐
                     ▼                  ▼                   ▼
             MetaApi cloud        relay (bot host)     broker MT5 WebAPI
             terminal             /mt5/history/deals   manager session
                     │                  │                   │
                     └──────────► raw deals ────────────────┘
                                        │ lib/mt5-normalize.js (pair IN/OUT)
                                        ▼
        public.trade_history ──▶ public.pair_analytics ──▶ dashboards
                     │
                     └──▶ public.mt5_sync_runs (audit)
```

## 1. Files

| File | Purpose |
| --- | --- |
| `sql/2026-10-13_mt5_trade_sync.sql` | Tables, indexes, RLS (safe to re-run) |
| `lib/mt5-bridge.js` | Bridge clients + provider resolution + health snapshot |
| `lib/mt5-normalize.js` | Provider-agnostic deal readers and IN/OUT position pairing |
| `lib/mt5-exit-reason.js` | Exit-reason classification (SL/TP/Manual/EA/Stop-out/Other) |
| `lib/mt5-metrics.js` | Pip maths, PnL, aggregation, sorting, paging, period helpers |
| `services/mt5Sync.js` | Sync orchestration, upserts, analytics rebuild, audit rows |
| `lib/api-auth.js` | Shared session/role/admin guard for the API routes |
| `pages/api/cron/mt5-sync.js` | Cron entry point (`CRON_SECRET`) |
| `pages/api/user/mt5-sync.js` | Link / unlink / sync an account, status snapshot |
| `pages/api/user/trade-history.js` | Filtered, paged closed trades + breakdowns |
| `pages/api/user/pair-performance.js` | Per-pair analytics (+ live fallback) |
| `pages/api/admin/mt5-performance.js` | Platform macro overview + admin sync trigger |
| `pages/api/admin/mt5-links.js` | Admin link management |
| `components/TradeHistoryTable.jsx` | Trade history table, filters, summary, breakdowns |
| `components/PairPerformanceBreakdown.jsx` | Per-pair table with exit mix |
| `components/Mt5SyncStatusPanel.jsx` | Bridge health, link form, link + run tables |
| `pages/dashboard/trade-history.js` | Trader page |
| `pages/admin/mt5-performance.js` | Admin page |
| `scripts/verify-mt5-sync.js` | 230+ offline checks (`npm run verify:mt5-sync`) |
| `scripts/mt5-fake-supabase.js` | In-memory Supabase stand-in used by the checks |

## 2. Apply the migration

Run `sql/2026-10-13_mt5_trade_sync.sql` in the Supabase SQL editor (or
`supabase db push`). It creates:

* `mt5_account_links` – one row per synced account: encrypted credentials
  (`lib/mt5-crypto.js`, AES-256-GCM), bridge account id/region, sync cursor
  (`last_deal_time`), enable flag and status/error columns.
* `trade_history` – one row per **closed position**. `deal_ticket` is the stable
  sync key (`position:<id>` when the bridge reports a position id, otherwise the
  final closing deal ticket) and is unique per link.
* `pair_analytics` – pre-aggregated per `(link, period, symbol)`; `period` is
  `all` or `YYYY-MM`.
* `mt5_sync_runs` – audit row per attempt (trigger, provider, window, counts,
  duration, error).

RLS is enabled on all four tables: authenticated users can `select` their own
rows, admins can select everything, and **all writes go through the service
role** (the sync service and the admin API). Credential columns are never
returned by any endpoint – only `password_last4`.

## 3. Configure a bridge

### Where each value comes from

| Variable | Where to get it | Notes |
| --- | --- | --- |
| `METAAPI_TOKEN` | [app.metaapi.cloud](https://app.metaapi.cloud) → sign up → **API tokens** (or `https://mt-provisioning-api-v1.agiliumtrade.ai/users/current/api-tokens` with an existing token) | One platform-wide token; it **creates and reads** cloud terminals for every linked account, so treat it like a production secret. |
| `METAAPI_REGION` | The MetaApi app shows the region of each account (`london`, `new-york`, `singapore`, …) | Optional. It only rewrites the host to `mt-client-api-v1.<region>.agiliumtrade.ai`; leave empty for the default host. |
| `BOT_API_URL` / `MT5_RELAY_URL` | The public URL of your own bot host (`ict_trading_bot/bot_api.py`, e.g. `https://bot.kingsbalfx.com`) | Already used for signal delivery, so it is usually present. |
| `BOT_API_TOKEN` / `MT5_RELAY_TOKEN` | The secret you generated in `ict_trading_bot/.env` (`BOT_API_TOKEN=replace_with_a_long_random_token`) | Must match on both sides; the web sends it as `X-Bot-Token`. |
| `MT5_WEBAPI_URL` + `MT5_WEBAPI_LOGIN` / `MT5_WEBAPI_PASSWORD` | Your **broker's** MT5 WebAPI (manager) endpoint and manager account | Only brokers that enable the HTTP/WebAPI manager API provide these; ask support for the manager login and a whitelisted IP. This is not your trading login. |
| `MT5_WEBAPI_SERVER` | The MT5 server name shown in the terminal (`Broker-Live`, `Broker-Demo`) | Optional filter; needed only when the manager serves several servers. |
| `MT5_CREDENTIALS_SECRET` | Generate once: `node -e "console.log(require('crypto').randomBytes(32).toString('base64url'))"` | Encrypts the MT5 passwords stored in `mt5_account_links` (AES-256-GCM). **Changing it invalidates every stored password** – re-link after rotating. |
| `CRON_SECRET` | Same generator command as above | Sent by Vercel Cron as `Authorization: Bearer …`; any long random string works. |
| `MT5_SYNC_LOOKBACK_DAYS` | Your choice (default 120) | First-run backfill window; per-link overrides win. |

### Where to set them

* **Locally:** `jaguar-main/.env.local` (git-ignored). Copy the block from `.env.example`.
* **Vercel:** Project → *Settings → Environment Variables* (or `vercel env add METAAPI_TOKEN production`). Add them for **Production** and **Preview**, then redeploy — env changes do not apply to existing deployments.
* **Self-hosted (`node server.js`):** export them in the process environment or keep `.env.local` next to `server.js`.

### Verify before wiring real accounts

```bash
npm run check:mt5-bridge                 # provider detection + missing vars (no secrets printed)
npm run check:mt5-bridge -- --probe      # live: MetaApi account list / bot-host /health / auth-start
npm run check:mt5-bridge -- --deals --login=5551234 --server=Broker-Demo --days=3
npm run check:mt5-bridge -- --deals --login=5551234 --accountId=<metaapi account id>
```

`--deals` exercises the exact client the cron uses, so a passing run means the bridge,
the credentials and the deal payload shape are all good. The same health block is
embedded in `GET /api/user/mt5-sync` and rendered by the sync status panel.

Pick one provider. `MT5_BRIDGE_PROVIDER` forces a choice; otherwise the service
auto-detects in this order: **metaapi → relay → mt5webapi**.

### MetaApi (hosted cloud terminal, recommended)

```bash
METAAPI_TOKEN=...            # MetaApi auth token (sent as the auth-token header)
METAAPI_REGION=london        # optional; sets mt-client-api-v1.<region>.agiliumtrade.ai
# METAAPI_CLIENT_BASE_URL=      # optional host overrides
# METAAPI_PROVISIONING_BASE_URL=
```

When a user links an account with a password, the API calls
`POST {provisioning}/users/current/accounts` once (idempotently – an existing
account for the same login/server is reused) and stores the returned account id
plus region on the link. Deal history comes from
`GET {client}/users/current/accounts/{accountId}/history-deals/time/{start}/{end}`.

### Relay (this project's own bot host)

Use when the bot host (`ict_trading_bot`) already owns a logged-in terminal:

```bash
MT5_BRIDGE_PROVIDER=relay
MT5_RELAY_URL=https://bot.example.com        # or reuse BOT_API_URL
MT5_RELAY_TOKEN=...                          # or reuse BOT_API_TOKEN
MT5_RELAY_DEALS_PATH=/mt5/history/deals      # default
```

The relay is called with `X-Bot-Token` and a JSON body
`{ login, server, since, until, limit }`; it must answer with a bare array or
`{ deals: [...] }`. Deal objects may use MetaApi-style keys
(`id, positionId, type, entryType, time, symbol, volume, price, profit,
commission, swap, comment, reason`) **or** MT5 WebAPI-style keys
(`Deal, PositionID, Action, Entry, Time, Symbol, Volume, Price, Profit,
Commission, Storage, Reason, ExpertID, Comment`) – both are normalised.

### Broker MT5 WebAPI (manager session)

```bash
MT5_BRIDGE_PROVIDER=mt5webapi
MT5_WEBAPI_URL=https://broker-webapi.example.com
MT5_WEBAPI_LOGIN=<manager login>
MT5_WEBAPI_PASSWORD=<manager password>
MT5_WEBAPI_SERVER=<optional server filter>
```

The client performs the standard `api/auth/start` → `api/auth/answer` MD5
challenge, then reads `api/deal/get_total` + `api/deal/get_page` and filters the
window client side (get_page has no time filter).

### Tuning

```bash
MT5_BRIDGE_TIMEOUT_MS=15000   # hard timeout for every bridge call
MT5_SYNC_LOOKBACK_DAYS=120    # first-run backfill (per-link column wins)
```

## 4. How a sync run works

1. **Window.** `computeSyncWindow()` uses `last_deal_time - 15 min` for an
   incremental run (the overlap catches deals that settle late) and
   `now - lookback days` on the first run.
2. **Fetch.** The bridge returns raw deals for that window; `dedupeDealsById()`
   protects against pages that repeat or ignore offsets.
3. **Pair.** `pairDealsIntoPositions()` groups deals by position id and produces
   one record per closed position: side from the opening deal (or inverted from
   the closing deal when the open is outside the window), volume-weighted close
   price across partial closes, summed profit/commission/swap, the closing deal's
   exit reason, held duration, pip result and period bucket.
   **Positions that are still open are skipped** – the live floating panel already
   covers them.
4. **Store.** Rows are upserted on `(link_id, deal_ticket)`; the run reports
   `inserted` vs `updated` so the audit trail is meaningful.
5. **Aggregate.** `pair_analytics` is rebuilt for `all` plus the recent monthly
   buckets: the periods owned by the link are deleted and re-inserted, so removed
   or renamed symbols cannot linger as stale rows.
6. **Cursor + audit.** `last_deal_time`, counters and status/error are written to
   the link row, and a row is appended to `mt5_sync_runs`.

Failures never throw out of `syncAllLinks()`: the link is flagged
(`sync_status = 'error'`, `sync_error = message`) and the audit row records the
message, provider and duration. A `truncated` bridge window (page cap reached)
marks the run `partial` and asks for another run to continue the backfill.

## 5. API surface

| Route | Method | Auth | Notes |
| --- | --- | --- | --- |
| `/api/cron/mt5-sync` | `GET`/`POST` | `Authorization: Bearer $CRON_SECRET` | `?limit=` (max 50), `?ids=a,b` |
| `/api/user/mt5-sync` | `GET` | session | Bridge health, own links, recent runs, totals |
| `/api/user/mt5-sync` | `POST` | session + paid bot access | `{ login, server, password, label?, lookbackDays?, provider?, provision? }` to link and sync; `{ linkId, syncEnabled?, label?, password?, lookbackDays? }` to update and sync |
| `/api/user/mt5-sync` | `DELETE` | session | `{ linkId }` removes the link and its trades (cascade) |
| `/api/user/trade-history` | `GET` | session | `period, symbol, side, exitReason, linkId, from, to, sortBy, sortDir, page, pageSize`; admins may add `scope=all` |
| `/api/user/pair-performance` | `GET` | session | `period`, `linkId`; admins may add `scope=all` (recomputes from `trade_history` when analytics are empty) |
| `/api/admin/mt5-performance` | `GET` | admin | `period`, `userId`, `linkId`, `limit` – macro roll-up, runs, bridge health |
| `/api/admin/mt5-performance` | `POST` | admin | `{ linkId }` or `{ all: true }`; `reset: true` clears the cursor for a full backfill |
| `/api/admin/mt5-links` | `GET`/`POST`/`PATCH`/`DELETE` | admin | List/sync/update/remove any link (`withCounts=1` adds trade counts) |

Vercel cron entry (already in `vercel.json`):

```json
{ "path": "/api/cron/mt5-sync", "schedule": "30 7 * * *" }
```

The Vercel Hobby plan only permits once-per-day schedules; Pro projects can
tighten this to `*/15 * * * *`. The per-account **Sync now** button covers
immediacy in the meantime.

## 6. Exit-reason classification

`lib/mt5-exit-reason.js` classifies in order of trust and stores both the reason
and the evidence (`exit_source`):

1. numeric `ENUM_DEAL_REASON` (`4`→SL, `5`→TP, `3`→EA, `6`/`8`→stop-out,
   `0/1/2`→manual, `7`→rollover, `9`+→other) → `trade_reason`
2. textual labels (`"DEAL_REASON_SL"`, `"expert"`, …) → `label`
3. comment patterns (`"[sl 1.23456]"`, `"[tp …]"`, `"so: …"`, `"closed by user"`) → `comment`
4. `magic != 0` implies an expert advisor → `heuristic`
5. otherwise `OTHER` → `unknown`

MT5 WebAPI returns the deal comment as a numeric enum rather than prose; those
values are deliberately **not** guessed (the trade falls through to the EA
heuristic or OTHER).

## 7. UI surfaces

* `/dashboard/trade-history` – traders: sync panel (bridge health status, link
  form, per-account pause/resume/remove, recent runs), trade history with
  period/symbol/side/exit/sort filters, summary cards, per-pair and exit-reason
  breakdowns.
* `/admin/mt5-performance` – admins: platform stat cards, sync panel across every
  account, per-pair analytics for a chosen period, full trade history.
* Navigation: `Trade History` is added to the trader menu and
  `MT5 Performance` to the admin menu (`components/QuickNav.jsx`).

## 8. Verification

```bash
npm run verify:mt5-sync
```

Runs 235 checks with plain Node – no jest, no network, no Supabase:

* pip maths for FX/JPY/metals, net PnL with the swap→storage fallback, period
  helpers, aggregation, profit factor, sorting and paging;
* exit-reason codes, labels, comments, the magic heuristic and unknown handling;
* provider-agnostic normalisation of MetaApi **and** MT5 WebAPI deal payloads;
* position pairing: partial closes, open positions skipped, INOUT reversals not
  double counted, duplicate deals collapsed;
* bridge behaviour against a fake `fetch`: auth headers (`auth-token`,
  `X-Bot-Token`), MetaApi paging and provisioning idempotency, the WebAPI MD5
  challenge flow, 401 propagation and request timeouts;
* the sync service end to end against an in-memory Supabase: insert/update
  counts, analytics rebuild, cursor movement, audit rows, idempotent re-runs,
  recorded bridge failures, "no bridge configured" degradation, and the guarantee
  that credential ciphertext never appears in a status payload.

## 9. Troubleshooting

| Symptom | Cause / fix |
| --- | --- |
| Panel says *not configured* | No bridge env vars: set `METAAPI_TOKEN`, or `BOT_API_URL`+`BOT_API_TOKEN`, or the WebAPI manager credentials |
| `setupRequired: true` in responses | The migration has not been applied yet |
| `BRIDGE_NOT_CONFIGURED` in a run result | `MT5_BRIDGE_PROVIDER` was forced to a provider with no credentials |
| Run status `partial` | The bridge page cap was reached – run the sync again to continue the backfill |
| `provisioning_error` on a link | The bridge rejected login/server/password (wrong live-vs-demo server, or an investor password that is disabled) |
| Trades missing for an older period | Raise `lookbackDays` and use the admin `reset: true` action to backfill again |
| Implausible pips on an exotic symbol | The bridge omitted `digits`, so `digitsForSymbol()` guessed. Return `digits` from the bridge or extend the keyword table |

## 10. Deliberate non-goals

* **No order execution.** This module only reads history; nothing here can place,
  modify or close a trade.
* **No local MT5 terminal or container** in the web deployment – all terminal work
  stays behind the bridge.
* **No live-position history.** Only closed positions are stored; floating P/L
  remains in the existing account-float panel.
* **No on-read backfill.** `/api/user/pair-performance` serves pre-aggregated rows
  and only computes on the fly while the analytics table is still empty.


