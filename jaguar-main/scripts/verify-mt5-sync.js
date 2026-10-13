// scripts/verify-mt5-sync.js
//
// Self-contained checks for the MT5 trade-history sync module. Runs with plain
// Node (no jest, no network, no Supabase):
//
//   npm run verify:mt5-sync
//
// It covers the pure domain modules (pip/PnL maths, exit-reason classification,
// IN/OUT deal pairing), the bridge clients (MetaApi / WebAPI / relay against a
// fake fetch) and the sync service end to end against an in-memory Supabase.

import crypto from "crypto";
import { createFakeSupabase } from "./mt5-fake-supabase.js";
import * as metrics from "../lib/mt5-metrics.js";
import * as exitReasons from "../lib/mt5-exit-reason.js";
import * as normalizer from "../lib/mt5-normalize.js";
import * as bridge from "../lib/mt5-bridge.js";
import * as mt5Sync from "../services/mt5Sync.js";

let passed = 0;
const failures = [];

function check(name, condition, detail = "") {
  if (condition) {
    passed += 1;
    return true;
  }
  failures.push({ name, detail });
  return false;
}

function eq(name, actual, expected) {
  return check(name, JSON.stringify(actual) === JSON.stringify(expected), `expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`);
}

function close(name, actual, expected, tolerance = 0.01) {
  const diff = Math.abs(Number(actual) - Number(expected));
  return check(name, diff <= tolerance, `expected ~${expected}, got ${actual}`);
}

async function test(name, fn) {
  try {
    await fn();
  } catch (error) {
    failures.push({ name, detail: error?.message || String(error) });
  }
}

/** Minimal fetch stand-in: routes are [matcher, handler] pairs. */
function fakeFetch(routes = []) {
  const calls = [];
  const impl = async (url, options = {}) => {
    calls.push({ url, options });
    for (const [matcher, handler] of routes) {
      const isMatch = typeof matcher === "string" ? String(url).includes(matcher) : matcher.test(String(url));
      if (!isMatch) continue;
      const result = typeof handler === "function" ? handler({ url, options }) : handler;
      const status = result?.status || 200;
      return {
        ok: status < 400,
        status,
        statusText: result?.statusText || "OK",
        text: async () => JSON.stringify(result?.body === undefined ? result : result.body),
      };
    }
    return {
      ok: false,
      status: 404,
      statusText: "Not Found",
      text: async () => JSON.stringify({ message: `no fake route for ${url}` }),
    };
  };
  impl.calls = calls;
  return impl;
}

const md5 = (value) => crypto.createHash("md5").update(String(value)).digest("hex");

// ---------------------------------------------------------------------------
// Fixtures: the same closed position expressed the MetaApi way and the WebAPI way
// ---------------------------------------------------------------------------
const METAAPI_DEALS = [
  {
    id: "d-1",
    positionId: "501",
    type: "DEAL_TYPE_BUY",
    entryType: "DEAL_ENTRY_IN",
    time: "2026-10-01T08:00:00.000Z",
    symbol: "EURUSD",
    volume: 0.5,
    price: 1.1,
    commission: -1.5,
    swap: 0,
    profit: 0,
    reason: 0,
  },
  {
    id: "d-2",
    positionId: "501",
    type: "DEAL_TYPE_SELL",
    entryType: "DEAL_ENTRY_OUT",
    time: "2026-10-01T10:30:00.000Z",
    symbol: "EURUSD",
    volume: 0.5,
    price: 1.105,
    commission: -1.5,
    swap: -0.2,
    profit: 250,
    comment: "[tp 1.10500]",
    reason: 5,
  },
  {
    id: "d-3",
    positionId: "502",
    type: "DEAL_TYPE_SELL",
    entryType: "DEAL_ENTRY_IN",
    time: "2026-10-02T09:00:00.000Z",
    symbol: "XAUUSD",
    volume: 0.1,
    price: 2650.5,
    reason: 0,
  },
  {
    id: "d-4",
    positionId: "503",
    type: "DEAL_TYPE_SELL",
    entryType: "DEAL_ENTRY_IN",
    time: "2026-10-03T07:00:00.000Z",
    symbol: "GBPJPY",
    volume: 0.3,
    price: 195.5,
    commission: -0.9,
    reason: 3,
    magic: 777,
  },
  {
    id: "d-5",
    positionId: "503",
    type: "DEAL_TYPE_BUY",
    entryType: "DEAL_ENTRY_OUT",
    time: "2026-10-03T08:00:00.000Z",
    symbol: "GBPJPY",
    volume: 0.1,
    price: 195.4,
    commission: -0.3,
    profit: 10,
    reason: 4,
  },
  {
    id: "d-6",
    positionId: "503",
    type: "DEAL_TYPE_BUY",
    entryType: "DEAL_ENTRY_OUT",
    time: "2026-10-03T09:15:00.000Z",
    symbol: "GBPJPY",
    volume: 0.2,
    price: 195.6,
    commission: -0.6,
    profit: -40,
    reason: 4,
    comment: "[sl 195.6]",
  },
];

const WEBAPI_DEALS = [
  {
    Deal: 9001,
    PositionID: 801,
    Action: 0,
    Entry: 0,
    Time: 1759312800,
    Symbol: "EURUSD",
    Digits: 5,
    Volume: 50,
    Price: 1.1,
    Commission: -2,
    Storage: 0,
    Profit: 0,
    ExpertID: 0,
    Comment: 0,
  },
  {
    Deal: 9002,
    PositionID: 801,
    Action: 1,
    Entry: 1,
    Time: 1759316400,
    Symbol: "EURUSD",
    Digits: 5,
    Volume: 50,
    Price: 1.105,
    Commission: -2,
    Storage: -1.25,
    Profit: 250,
    Reason: 5,
    Comment: 4,
  },
];

// ---------------------------------------------------------------------------
// 1. Pure metrics
// ---------------------------------------------------------------------------
await test("metrics: pip size and pip maths per instrument family", () => {
  eq("EURUSD digits", metrics.digitsForSymbol("EURUSD"), 5);
  eq("USDJPY digits", metrics.digitsForSymbol("USDJPY"), 3);
  eq("XAUUSD digits", metrics.digitsForSymbol("XAUUSD"), 2);
  close("EURUSD pip size", metrics.pipSizeForSymbol("EURUSD"), 0.0001, 1e-9);
  close("XAUUSD pip size", metrics.pipSizeForSymbol("XAUUSD"), 0.1, 1e-9);
  close("buy pips", metrics.computePips({ side: "buy", openPrice: 1.1, closePrice: 1.105, symbol: "EURUSD" }), 50);
  close("sell pips", metrics.computePips({ side: "sell", openPrice: 195.5, closePrice: 195.6, symbol: "GBPJPY" }), -10);
  eq("unusable prices do not fabricate a result", metrics.computePips({ side: "buy", openPrice: 0, closePrice: 0, symbol: "EURUSD" }), null);
});

await test("metrics: net PnL counts swap once and falls back to storage", () => {
  close("profit + commission + swap", metrics.computeNetPnl({ profit: 250, commission: -3, swap: -0.2, storage: -0.2 }), 246.8);
  close("storage fallback when swap is absent", metrics.computeNetPnl({ profit: 250, commission: -4, swap: null, storage: -1.25 }), 244.75);
});

await test("metrics: period helpers", () => {
  eq("period key", metrics.buildPeriod(new Date("2026-10-13T00:00:00Z")), "2026-10");
  eq("period label", metrics.periodLabel("2026-10"), "Oct 2026");
  eq("all-time label", metrics.periodLabel("all"), "All time");
  eq("filter passes a month", metrics.normalizePeriodFilter("2026-10"), "2026-10");
  eq("filter rejects junk", metrics.normalizePeriodFilter("last-month"), "all");
  eq("period start", metrics.periodBounds("2026-10").start, "2026-10-01T00:00:00.000Z");
  eq("recent periods newest first", metrics.listRecentPeriods(3, new Date("2026-10-13T00:00:00Z")), [
    "2026-10",
    "2026-09",
    "2026-08",
  ]);
});

await test("metrics: aggregation, pair breakdown, sorting, paging", () => {
  const trades = [
    { symbol: "EURUSD", net_pnl: 100, volume: 0.5, pips: 20, close_time: "2026-10-01T10:00:00.000Z", exit_reason: "TP" },
    { symbol: "EURUSD", net_pnl: -40, volume: 0.5, pips: -10, close_time: "2026-10-02T10:00:00.000Z", exit_reason: "SL" },
    { symbol: "XAUUSD", net_pnl: 10, volume: 0.1, pips: 5, close_time: "2026-10-02T11:00:00.000Z", exit_reason: "TP" },
  ];
  const totals = metrics.aggregateTrades(trades);
  eq("trade count", totals.trades, 3);
  eq("wins", totals.wins, 2);
  eq("losses", totals.losses, 1);
  close("net pnl", totals.netPnl, 70);
  close("win rate", totals.winRate, 66.67);
  close("profit factor", totals.profitFactor, 2.75);
  close("pips", totals.pips, 15);
  eq("last trade time", totals.lastTradeAt, "2026-10-02T11:00:00.000Z");

  const pairs = metrics.computePairMetrics(trades);
  eq("pairs sorted by net pnl", pairs.map((pair) => pair.symbol), ["EURUSD", "XAUUSD"]);
  close("pair net", pairs[0].netPnl, 60);
  eq("pair trades", pairs[0].trades, 2);
  close("pair win rate", pairs[0].winRate, 50);

  const sorted = metrics.sortTrades(trades, { sortBy: "net_pnl", direction: "desc" });
  eq("descending net", sorted.map((trade) => trade.net_pnl), [100, 10, -40]);
  const page = metrics.paginate([1, 2, 3, 4, 5], { page: 2, pageSize: 2 });
  eq("page slice", page.items, [3, 4]);
  eq("has more", page.hasMore, true);
  eq("total pages", page.totalPages, 3);
  const analytics = metrics.buildPairAnalyticsRows({
    trades: trades.map((trade) => ({ ...trade, period: "2026-10", exit_reason: trade.exit_reason })),
    link: { id: "link-1", user_id: "user-1", login: "1001" },
    period: "all",
  });
  eq("analytics rows", analytics.length, 2);
  const eur = analytics.find((row) => row.symbol === "EURUSD");
  eq("tp count", eur.tp_trades, 1);
  eq("sl count", eur.sl_trades, 1);
  eq("analytics link", eur.link_id, "link-1");
});

// ---------------------------------------------------------------------------
// 2. Exit-reason classification
// ---------------------------------------------------------------------------
await test("exit reasons: ENUM_DEAL_REASON codes win over comments", () => {
  eq("SL", exitReasons.exitReasonFor({ reason: 4 }), "SL");
  eq("TP", exitReasons.exitReasonFor({ reason: 5 }), "TP");
  eq("stop out", exitReasons.exitReasonFor({ reason: 6 }), "STOP_OUT");
  eq("expert", exitReasons.exitReasonFor({ reason: 3 }), "EA");
  eq("client", exitReasons.exitReasonFor({ reason: 0 }), "MANUAL");
  eq("rollover", exitReasons.exitReasonFor({ reason: 7 }), "ROLLOVER");
  eq("code beats a misleading comment", exitReasons.exitReasonFor({ reason: 5, comment: "[sl 1.1]" }), "TP");
});

await test("exit reasons: labels, comments and the magic heuristic", () => {
  eq("label SL", exitReasons.exitReasonFor({ reason: "DEAL_REASON_SL" }), "SL");
  eq("label expert", exitReasons.exitReasonFor({ reason: "DEAL_REASON_EXPERT" }), "EA");
  eq("comment sl", exitReasons.exitReasonFor({ comment: "[sl 1.23456]" }), "SL");
  eq("comment tp", exitReasons.exitReasonFor({ comment: "[tp 1.23456]" }), "TP");
  eq("comment stop out", exitReasons.exitReasonFor({ comment: "so: 1.2345" }), "STOP_OUT");
  eq("magic implies an EA", exitReasons.exitReasonFor({ magic: 2024 }), "EA");
  eq("WebAPI numeric comment is not guessed", exitReasons.exitReasonFor({ Comment: 4 }), "OTHER");
  const classified = exitReasons.classifyExitReason({ reason: 4, comment: "[sl 1.0]" });
  eq("classification source", classified.source, "trade_reason");
  eq("human label", exitReasons.exitReasonLabel("STOP_OUT"), "Stop Out / Margin Call");
  eq(
    "breakdown keeps display order and skips empty buckets",
    exitReasons.exitReasonBreakdown([
      { exit_reason: "SL", net_pnl: -1 },
      { exit_reason: "TP", net_pnl: 2 },
    ]).map((bucket) => bucket.reason),
    ["TP", "SL"],
  );
});

// ---------------------------------------------------------------------------
// 3. Deal normalisation + IN/OUT position pairing
// ---------------------------------------------------------------------------
await test("normalize: MetaApi deal shape", () => {
  const deal = normalizer.normalizeDeal(METAAPI_DEALS[1], { source: "metaapi" });
  eq("ticket", deal.ticket, "d-2");
  eq("position id", deal.positionId, "501");
  eq("side", deal.side, "sell");
  eq("entry", deal.entryType, "out");
  eq("symbol", deal.symbol, "EURUSD");
  eq("reason code", deal.reasonCode, 5);
  eq("comment", deal.comment, "[tp 1.10500]");
  eq("time", deal.time, "2026-10-01T10:30:00.000Z");
});

await test("normalize: MT5 WebAPI deal shape (unix seconds, capitalised keys)", () => {
  const deal = normalizer.normalizeDeal(WEBAPI_DEALS[1], { source: "mt5webapi" });
  eq("ticket", deal.ticket, "9002");
  eq("entry number becomes out", deal.entryType, "out");
  eq("action number becomes sell", deal.side, "sell");
  eq("unix seconds become ISO", deal.time, new Date(1759316400 * 1000).toISOString());
  eq("numeric comment is not treated as prose", deal.comment, null);
  eq("missing ExpertID stays null", deal.magic, null);
  eq("explicit ExpertID 0 is read as 0", normalizer.normalizeDeal(WEBAPI_DEALS[0], { source: "mt5webapi" }).magic, 0);
  eq("ExpertID 0 does not imply an EA", exitReasons.exitReasonFor(WEBAPI_DEALS[0]), "OTHER");
  close("storage is read", deal.storage, -1.25);
});

await test("pairing: one row per closed position, open positions skipped", () => {
  const rows = normalizer.toTradeRows(METAAPI_DEALS, {
    link: { id: "link-1", user_id: "user-1", login: "1001", server: "Demo" },
    source: "metaapi",
  });
  eq("closed positions only", rows.length, 2);
  eq("newest close first", rows[0].symbol, "GBPJPY");
  eq("open XAUUSD position is not stored", rows.some((row) => row.symbol === "XAUUSD"), false);

  const eurusd = rows.find((row) => row.symbol === "EURUSD");
  eq("side from the opening deal", eurusd.side, "buy");
  eq("volume", eurusd.volume, 0.5);
  close("open price", eurusd.open_price, 1.1, 1e-8);
  close("close price", eurusd.close_price, 1.105, 1e-8);
  close("pips", eurusd.pips, 50);
  close("profit", eurusd.profit, 250);
  close("commission across both deals", eurusd.commission, -3);
  close("net pnl", eurusd.net_pnl, 246.8);
  eq("exit reason from the deal reason code", eurusd.exit_reason, "TP");
  eq("exit source", eurusd.exit_source, "trade_reason");
  eq("period bucket", eurusd.period, "2026-10");
  eq("stable sync key", eurusd.deal_ticket, "position:501");
  eq("link id", eurusd.link_id, "link-1");
  eq("open ticket", eurusd.open_ticket, "d-1");
  eq("held duration", eurusd.duration_seconds, 9000);

  const gbpjpy = rows.find((row) => row.symbol === "GBPJPY");
  eq("side from the opening deal (short)", gbpjpy.side, "sell");
  close("volume is the sum of the close legs", gbpjpy.volume, 0.3);
  close("close price is volume weighted", gbpjpy.close_price, 195.53333333, 1e-6);
  close("net pnl across partial closes", gbpjpy.net_pnl, -31.8);
  eq("exit reason from the final close", gbpjpy.exit_reason, "SL");
  eq("magic number", gbpjpy.magic, 777);
  eq("comment", gbpjpy.comment, "[sl 195.6]");
});

await test("pairing: WebAPI fixture produces the same closed position", () => {
  const rows = normalizer.toTradeRows(WEBAPI_DEALS, { link: { id: "link-2", login: "2002" }, source: "mt5webapi" });
  eq("rows", rows.length, 1);
  const row = rows[0];
  eq("side", row.side, "buy");
  eq("volume", row.volume, 50);
  close("pips from supplied digits", row.pips, 50);
  close("net pnl uses storage as swap", row.net_pnl, 244.75);
  eq("exit reason from the Reason code", row.exit_reason, "TP");
  eq("source is recorded", row.source, "mt5webapi");
});

await test("pairing: INOUT reversal is not double counted", () => {
  const deals = [
    {
      id: "r1",
      positionId: "601",
      type: "DEAL_TYPE_BUY",
      entryType: "DEAL_ENTRY_IN",
      time: "2026-10-05T08:00:00.000Z",
      symbol: "USDJPY",
      volume: 1,
      price: 150,
      commission: -1,
      reason: 0,
    },
    {
      id: "r2",
      positionId: "601",
      type: "DEAL_TYPE_SELL",
      entryType: "DEAL_ENTRY_INOUT",
      time: "2026-10-05T09:00:00.000Z",
      symbol: "USDJPY",
      volume: 1,
      price: 150.5,
      commission: -1,
      profit: 50,
      reason: 2,
    },
    {
      id: "r3",
      positionId: "602",
      type: "DEAL_TYPE_SELL",
      entryType: "DEAL_ENTRY_OUT",
      time: "2026-10-05T11:00:00.000Z",
      symbol: "USDJPY",
      volume: 1,
      price: 149.5,
      commission: -1,
      profit: 100,
      reason: 4,
    },
  ];
  const rows = normalizer.toTradeRows(deals, { link: { id: "link-3", login: "3003" }, source: "metaapi" });
  eq("two positions", rows.length, 2);

  const first = rows.find((row) => row.deal_ticket === "position:601");
  eq("601 side", first.side, "buy");
  close("601 profit comes from the INOUT close", first.profit, 50);
  close("601 net", first.net_pnl, 48);

  const second = rows.find((row) => row.deal_ticket === "position:602");
  eq("602 side inferred by inverting a SELL close (the position was long)", second.side, "buy");
  close("602 does not inherit the reversal profit", second.profit, 100);
  eq("602 exit reason", second.exit_reason, "SL");
});

await test("pairing: duplicate deals and rows are collapsed", () => {
  const rows = normalizer.toTradeRows([METAAPI_DEALS[0], METAAPI_DEALS[1], METAAPI_DEALS[1]], { link: { id: "link-1" } });
  eq("duplicate deal tickets collapse", rows.length, 1);
  const deduped = normalizer.dedupeTradeRows([
    { link_id: "a", deal_ticket: "x", close_time: "2026-10-01T00:00:00.000Z" },
    { link_id: "a", deal_ticket: "x", close_time: "2026-10-02T00:00:00.000Z" },
  ]);
  eq("dedupeTradeRows keeps one row per key", deduped.length, 1);
  eq("newest close wins", deduped[0].close_time, "2026-10-02T00:00:00.000Z");
  eq("grouping exposes the position id", normalizer.groupDealsByPosition(METAAPI_DEALS)[0].positionId, "501");
});

// ---------------------------------------------------------------------------
// 4. Bridge clients (fake fetch, no network)
// ---------------------------------------------------------------------------
const BRIDGE_ENV_KEYS = [
  "MT5_BRIDGE_PROVIDER",
  "METAAPI_TOKEN",
  "METAAPI_REGION",
  "METAAPI_CLIENT_BASE_URL",
  "METAAPI_PROVISIONING_BASE_URL",
  "MT5_RELAY_URL",
  "MT5_RELAY_TOKEN",
  "MT5_RELAY_DEALS_PATH",
  "MT5_WEBAPI_URL",
  "MT5_WEBAPI_LOGIN",
  "MT5_WEBAPI_PASSWORD",
  "MT5_WEBAPI_SERVER",
  "BOT_API_URL",
  "BOT_API_INTERNAL",
  "BOT_API_TOKEN",
  "BOT_SIGNAL_SECRET",
];

function resetBridgeEnv() {
  for (const key of BRIDGE_ENV_KEYS) delete process.env[key];
}

// Snapshot taken before any test mutates the environment, restored at the end.
const ORIGINAL_ENV = {};
for (const key of BRIDGE_ENV_KEYS) ORIGINAL_ENV[key] = process.env[key];

await test("bridge: nothing configured is reported, not guessed", async () => {
  resetBridgeEnv();
  const resolved = bridge.resolveBridgeProvider();
  eq("no provider", resolved.provider, null);
  eq("not configured", resolved.configured, false);
  check("reason explains what to set", /METAAPI_TOKEN/.test(resolved.reason || ""));
  const health = bridge.getBridgeHealth();
  eq("health flag", health.configured, false);
  eq("three providers probed", health.providers.map((entry) => entry.provider), ["metaapi", "relay", "mt5webapi"]);
  await bridge
    .fetchDealsForLink({ link: { login: "1001" }, since: "2026-10-01T00:00:00Z", until: "2026-10-02T00:00:00Z" })
    .then(
      () => check("fetchDealsForLink must refuse", false, "expected BRIDGE_NOT_CONFIGURED"),
      (error) => eq("error code", error.code, "BRIDGE_NOT_CONFIGURED"),
    );
});

await test("bridge: provider detection order and region hosts", () => {
  resetBridgeEnv();
  process.env.METAAPI_TOKEN = "metaapi-token";
  eq("metaapi is auto-detected", bridge.resolveBridgeProvider().provider, "metaapi");
  const defaultHealth = bridge.getBridgeHealth();
  eq("default client host", defaultHealth.metaApi.clientBase, "https://mt-client-api-v1.agiliumtrade.ai");
  eq("token never leaked into health", JSON.stringify(defaultHealth).includes("metaapi-token"), false);

  resetBridgeEnv();
  process.env.MT5_BRIDGE_PROVIDER = "metaapi";
  process.env.METAAPI_TOKEN = "metaapi-token";
  process.env.METAAPI_REGION = "london";
  eq("region host", bridge.getBridgeHealth().metaApi.clientBase, "https://mt-client-api-v1.london.agiliumtrade.ai");

  resetBridgeEnv();
  process.env.BOT_API_URL = "https://bot.example.com";
  eq("relay needs its token too", bridge.providerAvailability("relay").configured, false);
  process.env.BOT_API_TOKEN = "bot-token";
  eq("relay becomes available", bridge.providerAvailability("relay").configured, true);
  eq("relay is auto-detected second", bridge.resolveBridgeProvider().provider, "relay");
  eq("relay deals path default", bridge.relayConfig().path, "/mt5/history/deals");

  resetBridgeEnv();
  process.env.MT5_WEBAPI_URL = "https://webapi.example.com/";
  process.env.MT5_WEBAPI_LOGIN = "mgr";
  process.env.MT5_WEBAPI_PASSWORD = "mgr-pass";
  eq("webapi is the last fallback", bridge.resolveBridgeProvider().provider, "mt5webapi");
  eq("trailing slash trimmed", bridge.webApiConfig().baseUrl, "https://webapi.example.com");

  resetBridgeEnv();
  process.env.MT5_BRIDGE_PROVIDER = "nonsense";
  process.env.METAAPI_TOKEN = "metaapi-token";
  const forced = bridge.resolveBridgeProvider();
  eq("explicit provider wins", forced.provider, "nonsense");
  eq("unsupported provider is not configured", forced.configured, false);
});

await test("bridge: MetaApi deal fetch signs with auth-token and pages", async () => {
  const fetchImpl = fakeFetch([
    [
      "/history-deals/time/",
      ({ url }) => ({ body: url.includes("offset=2") ? [METAAPI_DEALS[2]] : [METAAPI_DEALS[0], METAAPI_DEALS[1]] }),
    ],
  ]);
  const result = await bridge.fetchDealsMetaApi({
    accountId: "acct-1",
    since: "2026-10-01T00:00:00Z",
    until: "2026-10-06T00:00:00Z",
    token: "tok",
    pageSize: 2,
    fetchImpl,
  });
  eq("all pages collected", result.deals.length, 3);
  eq("provider", result.provider, "metaapi");
  eq("request count", fetchImpl.calls.length, 2);
  eq("auth-token header", fetchImpl.calls[0].options.headers["auth-token"], "tok");
  check("history-deals path used", /history-deals\/time\//.test(fetchImpl.calls[0].url), fetchImpl.calls[0].url);
  check("account id in the path", fetchImpl.calls[0].url.includes("/accounts/acct-1/"), fetchImpl.calls[0].url);
  check("ISO window in the path", fetchImpl.calls[0].url.includes("2026-10-01T00:00:00.000Z"), fetchImpl.calls[0].url);
  eq("offset paging advanced", fetchImpl.calls[1].url.includes("offset=2"), true);
});

await test("bridge: MetaApi provisioning reuses an existing account", async () => {
  const existingFetch = fakeFetch([
    ["/users/current/accounts", { body: [{ _id: "acct-1", login: "1001", server: "Demo" }] }],
  ]);
  const existing = await bridge.ensureMetaApiAccount({
    login: "1001",
    server: "Demo",
    password: "pw",
    token: "tok",
    fetchImpl: existingFetch,
  });
  eq("reused", existing.created, false);
  eq("account id", existing.account._id, "acct-1");
  eq("no POST issued", existingFetch.calls.some((call) => call.options?.method === "POST"), false);
});

await test("bridge: MetaApi provisioning creates the cloud terminal", async () => {
  const createFetch = fakeFetch([
    [
      "/users/current/accounts",
      ({ options }) => (options?.method === "POST" ? { body: { _id: "new-acct", state: "DEPLOYED" } } : { body: [] }),
    ],
  ]);
  const created = await bridge.ensureMetaApiAccount({
    login: "1002",
    server: "Demo-Server",
    password: "pw",
    token: "tok",
    region: "london",
    name: "kingsbalfx-1002",
    fetchImpl: createFetch,
  });
  eq("created", created.created, true);
  eq("account id", created.account._id, "new-acct");
  const postCall = createFetch.calls.find((call) => call.options?.method === "POST");
  const body = JSON.parse(postCall.options.body);
  eq("login posted", body.login, "1002");
  eq("server posted", body.server, "Demo-Server");
  eq("platform posted", body.platform, "mt5");
  eq("region posted", body.region, "london");
});

await test("bridge: MetaApi provisioning refuses without credentials", async () => {
  resetBridgeEnv();
  await bridge
    .ensureMetaApiAccount({ login: "1003", server: "Demo", token: "", fetchImpl: fakeFetch([]) })
    .then(
      () => check("must refuse", false, "expected METAAPI_TOKEN error"),
      (error) => check("token error", /METAAPI_TOKEN/.test(error.message), error.message),
    );
});

await test("bridge: WebAPI manager session answers the MD5 challenge and pages deals", async () => {
  resetBridgeEnv();
  process.env.MT5_WEBAPI_URL = "https://webapi.example.com";
  process.env.MT5_WEBAPI_LOGIN = "mgr";
  process.env.MT5_WEBAPI_PASSWORD = "mgr-pass";
  const password = "mgr-pass";
  const webFetch = fakeFetch([
    ["/api/auth/start", { body: { srv_rand: "aabbccdd" } }],
    [
      "/api/auth/answer",
      ({ options }) => {
        const body = JSON.parse(options.body);
        return { body: { cli_rand_answer: md5(md5(password) + body.cli_rand) } };
      },
    ],
    ["/api/deal/get_total", { body: { answer: { total: 2 } } }],
    ["/api/deal/get_page", { body: { answer: WEBAPI_DEALS } }],
  ]);
  const result = await bridge.fetchDealsWebApi({
    login: "2002",
    since: "2025-01-01T00:00:00Z",
    until: "2026-12-31T00:00:00Z",
    fetchImpl: webFetch,
  });
  eq("deals inside the window", result.deals.length, 2);
  eq("provider", result.provider, "mt5webapi");
  const startBody = JSON.parse(webFetch.calls[0].options.body);
  eq("manager login sent", startBody.login, "mgr");
  eq("manager session type", startBody.type, "manager");
  check("get_page requested", webFetch.calls.some((call) => call.url.includes("/api/deal/get_page")), "no get_page call");
});

await test("bridge: relay bridge posts the token header and the dispatcher picks it", async () => {
  resetBridgeEnv();
  process.env.MT5_RELAY_URL = "https://bot.example.com/";
  process.env.MT5_RELAY_TOKEN = "relay-token";
  const relayFetch = fakeFetch([
    ["/mt5/history/deals", ({ options }) => ({ body: { deals: METAAPI_DEALS, meta: { source: options.method } } })],
  ]);
  const relay = await bridge.fetchDealsRelay({
    login: "1001",
    server: "Demo",
    since: "2026-09-01T00:00:00Z",
    until: "2026-10-06T00:00:00Z",
    fetchImpl: relayFetch,
  });
  eq("deals unwrapped", relay.deals.length, METAAPI_DEALS.length);
  eq("provider", relay.provider, "relay");
  eq("token header", relayFetch.calls[0].options.headers["X-Bot-Token"], "relay-token");
  eq("iso window sent", JSON.parse(relayFetch.calls[0].options.body).since, "2026-09-01T00:00:00.000Z");

  resetBridgeEnv();
  process.env.MT5_BRIDGE_PROVIDER = "relay";
  process.env.BOT_API_URL = "https://bot.example.com";
  process.env.BOT_API_TOKEN = "relay-token";
  const dispatched = await bridge.fetchDealsForLink({
    link: { login: "1001" },
    since: "2026-09-01T00:00:00Z",
    until: "2026-10-06T00:00:00Z",
    fetchImpl: relayFetch,
  });
  eq("dispatcher picks the relay", dispatched.provider, "relay");
  eq("dedupeDealsById collapses repeats", bridge.dedupeDealsById([{ id: "a" }, { id: "a" }, { id: "b" }]).length, 2);
});

await test("bridge: errors and timeouts surface instead of hanging", async () => {
  const unauthorized = fakeFetch([["/history-deals/time/", { status: 401, body: { message: "invalid token" } }]]);
  await bridge
    .fetchDealsMetaApi({
      accountId: "acct-1",
      since: "2026-10-01T00:00:00Z",
      until: "2026-10-02T00:00:00Z",
      token: "bad",
      fetchImpl: unauthorized,
    })
    .then(
      () => check("401 must throw", false, "expected an error"),
      (error) => {
        eq("status attached", error.status, 401);
        check("message includes the status", /401/.test(error.message), error.message);
        check("message includes the bridge detail", /invalid token/.test(error.message), error.message);
      },
    );

  const hangingFetch = (url, options = {}) =>
    new Promise((resolve, reject) => {
      options.signal?.addEventListener("abort", () => {
        const error = new Error("aborted");
        error.name = "AbortError";
        reject(error);
      });
    });
  await bridge.requestJson("https://example.com/slow", { fetchImpl: hangingFetch, timeoutMs: 20 }).then(
    () => check("timeout must throw", false, "expected a timeout"),
    (error) => eq("timeout code", error.code, "BRIDGE_TIMEOUT"),
  );
});

// ---------------------------------------------------------------------------
// 5. Sync service end to end (fake Supabase + fake fetch)
// ---------------------------------------------------------------------------
function seedLink(overrides = {}) {
  return {
    id: "link-1",
    user_id: "user-1",
    email: "trader@example.com",
    login: "1001",
    server: "Demo",
    label: "Live",
    provider: "metaapi",
    bridge_account_id: "acct-1",
    bridge_region: null,
    provisioning_status: "ready",
    sync_enabled: true,
    sync_status: "idle",
    sync_error: null,
    last_synced_at: null,
    last_deal_time: null,
    last_sync_deals: 0,
    total_synced_deals: 0,
    sync_lookback_days: 120,
    password_last4: "1234",
    created_at: "2026-10-01T00:00:00.000Z",
    ...overrides,
  };
}

await test("sync: the window is a backfill first, then incremental with overlap", () => {
  const first = mt5Sync.computeSyncWindow({ link: seedLink(), now: new Date("2026-10-13T12:00:00Z") });
  eq("backfill mode", first.mode, "backfill");
  eq("backfill start", first.since.toISOString(), "2026-06-15T12:00:00.000Z");
  const next = mt5Sync.computeSyncWindow({
    link: seedLink({ last_deal_time: "2026-10-13T09:00:00.000Z" }),
    now: new Date("2026-10-13T12:00:00Z"),
  });
  eq("incremental mode", next.mode, "incremental");
  eq("cursor overlap applied", next.since.toISOString(), "2026-10-13T08:45:00.000Z");
  eq("lookback comes from the link row", mt5Sync.resolveLookbackDays(seedLink({ sync_lookback_days: 30 })), 30);
  eq("lookback default", mt5Sync.resolveLookbackDays({}), mt5Sync.DEFAULT_LOOKBACK_DAYS);
  eq("chunking", mt5Sync.chunk([1, 2, 3, 4, 5], 2).length, 3);
});

await test("sync: a manual run stores trades, rebuilds analytics and moves the cursor", async () => {
  resetBridgeEnv();
  process.env.METAAPI_TOKEN = "test-token";
  const supabase = createFakeSupabase({
    mt5_account_links: [seedLink()],
    trade_history: [],
    pair_analytics: [],
    mt5_sync_runs: [],
  });
  const fetchImpl = fakeFetch([["/history-deals/time/", { body: METAAPI_DEALS }]]);
  const result = await mt5Sync.syncLink({
    supabaseAdmin: supabase,
    link: seedLink(),
    trigger: "manual",
    provider: "metaapi",
    fetchImpl,
    now: new Date("2026-10-13T12:00:00Z"),
  });

  eq("run ok", result.ok, true);
  eq("run status", result.status, "success");
  eq("deals received", result.dealsReceived, 6);
  eq("trades inserted", result.tradesInserted, 2);
  eq("trades updated", result.tradesUpdated, 0);
  eq("deals collapsed into position rows", result.tradesSkipped, 4);
  eq("link provisioning resolved", supabase.rows("mt5_account_links")[0].provisioning_status, "ready");

  const trades = supabase.rows("trade_history");
  eq("stored trades", trades.length, 2);
  eq(
    "trades are scoped to the link owner",
    trades.every((row) => row.link_id === "link-1" && row.user_id === "user-1"),
    true,
  );
  const eurusd = trades.find((row) => row.symbol === "EURUSD");
  eq("exit reason stored", eurusd.exit_reason, "TP");
  eq("stable sync key stored", eurusd.deal_ticket, "position:501");
  close("net pnl stored", eurusd.net_pnl, 246.8);

  const analytics = supabase.rows("pair_analytics");
  check("all-time analytics built", analytics.some((row) => row.period === "all" && row.symbol === "EURUSD"));
  check("monthly analytics built", analytics.some((row) => row.period === "2026-10" && row.symbol === "GBPJPY"));
  const allTimeEur = analytics.find((row) => row.period === "all" && row.symbol === "EURUSD");
  eq("analytics trade count", allTimeEur.trades, 1);
  eq("analytics tp count", allTimeEur.tp_trades, 1);
  close("analytics net pnl", allTimeEur.net_pnl, 246.8);

  const link = supabase.rows("mt5_account_links")[0];
  eq("cursor advanced to the newest close", link.last_deal_time, "2026-10-03T09:15:00.000Z");
  eq("last sync deal count", link.last_sync_deals, 6);
  eq("total synced deals", link.total_synced_deals, 2);
  eq("link status", link.sync_status, "success");
  eq("link error cleared", link.sync_error, null);

  const runs = supabase.rows("mt5_sync_runs");
  eq("audit rows", runs.length, 1);
  eq("audit trigger", runs[0].trigger, "manual");
  eq("audit provider", runs[0].provider, "metaapi");
  eq("audit inserted", runs[0].trades_inserted, 2);
  eq("audit window mode", runs[0].context.windowMode, "backfill");
});

await test("sync: re-running is idempotent (updates instead of duplicates)", async () => {
  resetBridgeEnv();
  process.env.METAAPI_TOKEN = "test-token";
  const supabase = createFakeSupabase({
    mt5_account_links: [seedLink()],
    trade_history: [],
    pair_analytics: [],
    mt5_sync_runs: [],
  });
  const fetchImpl = fakeFetch([["/history-deals/time/", { body: METAAPI_DEALS }]]);
  const now = new Date("2026-10-13T12:00:00Z");

  await mt5Sync.syncLink({ supabaseAdmin: supabase, link: seedLink(), trigger: "cron", provider: "metaapi", fetchImpl, now });
  const second = await mt5Sync.syncLink({
    supabaseAdmin: supabase,
    link: { ...seedLink(), ...supabase.rows("mt5_account_links")[0] },
    trigger: "cron",
    provider: "metaapi",
    fetchImpl,
    now: new Date("2026-10-13T13:00:00Z"),
  });

  eq("still two trades", supabase.rows("trade_history").length, 2);
  eq("second run inserts nothing", second.tradesInserted, 0);
  eq("second run refreshes both rows", second.tradesUpdated, 2);
  eq("window became incremental", second.windowMode, "incremental");
  eq("analytics are not duplicated", supabase.rows("pair_analytics").length, 4);
  eq("two audit rows", supabase.rows("mt5_sync_runs").length, 2);
  eq("cumulative counter counts inserts only", supabase.rows("mt5_account_links")[0].total_synced_deals, 2);
});

await test("sync: bridge failures are recorded, never thrown", async () => {
  resetBridgeEnv();
  process.env.METAAPI_TOKEN = "test-token";
  const supabase = createFakeSupabase({
    mt5_account_links: [seedLink({ id: "link-9" })],
    trade_history: [],
    pair_analytics: [],
    mt5_sync_runs: [],
  });
  const failingFetch = fakeFetch([["/history-deals/time/", { status: 500, body: { message: "upstream exploded" } }]]);
  const result = await mt5Sync.syncLink({
    supabaseAdmin: supabase,
    link: seedLink({ id: "link-9" }),
    trigger: "cron",
    provider: "metaapi",
    fetchImpl: failingFetch,
    now: new Date("2026-10-13T12:00:00Z"),
  });

  eq("run failed", result.ok, false);
  eq("status", result.status, "error");
  check("error message kept", /upstream exploded/.test(result.error || ""), result.error);
  eq("no trades stored", supabase.rows("trade_history").length, 0);
  const link = supabase.rows("mt5_account_links")[0];
  eq("link flagged", link.sync_status, "error");
  check("link error stored", /upstream exploded/.test(link.sync_error || ""), link.sync_error);
  const run = supabase.rows("mt5_sync_runs")[0];
  eq("audit status", run.status, "error");
  eq("audit keeps the attempted provider", run.provider, "metaapi");
  eq("audit duration recorded", typeof run.duration_ms, "number");
});

await test("sync: syncAllLinks degrades when no bridge is configured", async () => {
  resetBridgeEnv();
  const supabase = createFakeSupabase({ mt5_account_links: [seedLink()], mt5_sync_runs: [] });
  const out = await mt5Sync.syncAllLinks({ supabaseAdmin: supabase, trigger: "cron" });
  eq("skipped", out.status, "skipped");
  eq("nothing processed", out.linksProcessed, 0);
  eq("reason surfaced", typeof out.reason, "string");
  eq("no audit noise", supabase.rows("mt5_sync_runs").length, 0);
});

await test("sync: syncAllLinks processes every enabled link", async () => {
  resetBridgeEnv();
  process.env.METAAPI_TOKEN = "test-token";
  const supabase = createFakeSupabase({
    mt5_account_links: [seedLink(), seedLink({ id: "link-2", login: "2002" })],
    trade_history: [],
    pair_analytics: [],
    mt5_sync_runs: [],
  });
  const fetchImpl = fakeFetch([["/history-deals/time/", { body: METAAPI_DEALS }]]);
  const out = await mt5Sync.syncAllLinks({
    supabaseAdmin: supabase,
    trigger: "cron",
    fetchImpl,
    now: new Date("2026-10-13T12:00:00Z"),
  });

  eq("links processed", out.linksProcessed, 2);
  eq("status", out.status, "success");
  eq("trades inserted across links", out.totals.tradesInserted, 4);
  eq("no failures", out.totals.failures, 0);
  eq("both accounts stored", supabase.rows("trade_history").length, 4);
});

await test("sync: the status snapshot never exposes credentials", async () => {
  const supabase = createFakeSupabase({
    mt5_account_links: [
      seedLink({ password_encrypted: "SECRET-CIPHER", password_iv: "SECRET-IV", password_tag: "SECRET-TAG" }),
      seedLink({ id: "link-2", login: "2002", sync_enabled: false, sync_status: "error" }),
    ],
    mt5_sync_runs: [],
  });
  const snapshot = await mt5Sync.getSyncSnapshot(supabase, { userId: "user-1", isAdmin: false });
  const serialized = JSON.stringify(snapshot);
  eq("links returned", snapshot.links.length, 2);
  eq("ciphertext is never exposed", serialized.includes("SECRET-CIPHER"), false);
  eq("iv is never exposed", serialized.includes("SECRET-IV"), false);
  eq("bridge health included", typeof snapshot.bridge.configured, "boolean");
  eq("enabled count", snapshot.totals.enabled, 1);
  eq("error count", snapshot.totals.errors, 1);
  eq("synced deal total", snapshot.totals.totalSyncedDeals, 0);

  const broken = createFakeSupabase({ mt5_account_links: [seedLink()] });
  broken.failTables.add("mt5_sync_runs");
  const degraded = await mt5Sync.getSyncSnapshot(broken, { userId: "user-1" });
  eq("missing tables degrade instead of throwing", degraded.setupRequired, true);
  eq("runs default to an empty list", degraded.runs.length, 0);
  eq("links still returned", degraded.links.length, 1);
  eq("missing relation detected", mt5Sync.isMissingRelationError({ code: "42P01", message: 'relation "public.x" does not exist' }), true);
});

// ---------------------------------------------------------------------------
// Summary
// ---------------------------------------------------------------------------
for (const key of BRIDGE_ENV_KEYS) {
  if (ORIGINAL_ENV[key] === undefined) delete process.env[key];
  else process.env[key] = ORIGINAL_ENV[key];
}

console.log("");
console.log(`MT5 trade-sync verification: ${passed} checks passed, ${failures.length} failed.`);
if (failures.length) {
  for (const failure of failures) {
    console.error(`  x ${failure.name}${failure.detail ? ` -- ${failure.detail}` : ""}`);
  }
  process.exit(1);
}
console.log("OK: metrics, exit reasons, deal pairing, bridge clients and the sync service are verified.");








