/**
 * Cloud MT5 bridge clients (provider-agnostic).
 *
 * There is no local terminal / Docker here: the sync worker runs on a Vercel cron
 * and talks to a hosted REST bridge. Three providers are supported, selected in order:
 *
 *   1. MT5_BRIDGE_PROVIDER (explicit override: metaapi | relay | mt5webapi)
 *   2. "metaapi"    when METAAPI_TOKEN is set (hosted MetaApi cloud terminal)
 *   3. "relay"      when BOT_API_URL + BOT_API_TOKEN are set (this project's own
 *                   bot host, which owns a live MT5 terminal)
 *   4. "mt5webapi"  when MT5_WEBAPI_URL + manager credentials are set (broker WebAPI)
 *
 * Endpoints (every base URL is env-overridable, so a bridge upgrade never needs a
 * code change). MetaApi authenticates with an `auth-token` header:
 *
 *   MetaApi  provisioning : GET/POST {METAAPI_PROVISIONING_BASE_URL}/users/current/accounts
 *   MetaApi  client       : GET {METAAPI_CLIENT_BASE_URL}/users/current/accounts/{id}
 *                               /history-deals/time/{start}/{end}
 *   MT5 WebAPI manager    : POST {base}/api/auth/start
 *                           GET  {base}/api/deal/get_total?login=..
 *                           GET  {base}/api/deal/get_page?login=..&offset=..&total=..
 *   Relay (this project)  : POST {base}{MT5_RELAY_DEALS_PATH}  (X-Bot-Token: <token>)
 *
 * Clients return raw deal payloads; normalisation lives in lib/mt5-normalize.js so
 * the aggregation layer stays bridge independent.
 */
import crypto from "crypto";

const DEFAULT_TIMEOUT_MS = 15000;

function envValue(name, fallback = "") {
  const value = process.env[name];
  return value === undefined || value === null ? fallback : String(value).trim();
}

function toInt(value, fallback) {
  const numeric = Number.parseInt(String(value ?? ""), 10);
  return Number.isFinite(numeric) ? numeric : fallback;
}

/** Timeout (ms) for every bridge HTTP call. */
export function bridgeTimeoutMs() {
  return toInt(envValue("MT5_BRIDGE_TIMEOUT_MS", String(DEFAULT_TIMEOUT_MS)), DEFAULT_TIMEOUT_MS);
}

export const BRIDGE_PROVIDERS = ["metaapi", "relay", "mt5webapi"];

function metaApiHosts(region) {
  const zone = region ? `.${region}` : "";
  return {
    clientBase: envValue("METAAPI_CLIENT_BASE_URL") || `https://mt-client-api-v1${zone}.agiliumtrade.ai`,
    provisioningBase:
      envValue("METAAPI_PROVISIONING_BASE_URL") || `https://mt-provisioning-api-v1${zone}.agiliumtrade.ai`,
  };
}

export function metaApiConfig() {
  const token = envValue("METAAPI_TOKEN");
  const region = envValue("METAAPI_REGION");
  return { token, region, ...metaApiHosts(region) };
}

export function webApiConfig() {
  return {
    baseUrl: envValue("MT5_WEBAPI_URL").replace(/\/+$/, ""),
    login: envValue("MT5_WEBAPI_LOGIN"),
    password: envValue("MT5_WEBAPI_PASSWORD"),
    server: envValue("MT5_WEBAPI_SERVER"),
  };
}

export function relayConfig() {
  return {
    baseUrl: (envValue("MT5_RELAY_URL") || envValue("BOT_API_INTERNAL") || envValue("BOT_API_URL")).replace(/\/+$/, ""),
    token: envValue("MT5_RELAY_TOKEN") || envValue("BOT_API_TOKEN") || envValue("BOT_SIGNAL_SECRET"),
    path: envValue("MT5_RELAY_DEALS_PATH", "/mt5/history/deals"),
  };
}

export function providerAvailability(provider) {
  if (provider === "metaapi") {
    return metaApiConfig().token
      ? { configured: true, reason: null }
      : { configured: false, reason: "METAAPI_TOKEN is not set" };
  }
  if (provider === "relay") {
    const { baseUrl, token } = relayConfig();
    if (!baseUrl) return { configured: false, reason: "MT5_RELAY_URL / BOT_API_URL is not set" };
    if (!token) return { configured: false, reason: "MT5_RELAY_TOKEN / BOT_API_TOKEN is not set" };
    return { configured: true, reason: null };
  }
  if (provider === "mt5webapi") {
    const { baseUrl, login, password } = webApiConfig();
    if (!baseUrl) return { configured: false, reason: "MT5_WEBAPI_URL is not set" };
    if (!login || !password) {
      return { configured: false, reason: "MT5_WEBAPI_LOGIN / MT5_WEBAPI_PASSWORD are not set" };
    }
    return { configured: true, reason: null };
  }
  return { configured: false, reason: `unknown provider "${provider}"` };
}

/** Which provider should be used, and why (secrets never returned). */
export function resolveBridgeProvider(explicitProvider) {
  const explicit = String(explicitProvider || envValue("MT5_BRIDGE_PROVIDER")).trim().toLowerCase();
  if (explicit) {
    if (!BRIDGE_PROVIDERS.includes(explicit)) {
      return { provider: explicit, configured: false, reason: `unsupported provider "${explicit}"`, forced: true };
    }
    const availability = providerAvailability(explicit);
    return { provider: explicit, configured: availability.configured, reason: availability.reason, forced: true };
  }
  for (const provider of BRIDGE_PROVIDERS) {
    const availability = providerAvailability(provider);
    if (availability.configured) return { provider, configured: true, reason: null, forced: false };
  }
  return {
    provider: null,
    configured: false,
    reason: "no MT5 bridge configured (set METAAPI_TOKEN, BOT_API_URL+BOT_API_TOKEN, or MT5_WEBAPI_URL)",
    forced: false,
  };
}

/** Public, safe-to-expose health snapshot for the sync status panel. */
export function getBridgeHealth() {
  const resolved = resolveBridgeProvider();
  const metaApi = metaApiConfig();
  const relay = relayConfig();
  const webApi = webApiConfig();
  return {
    provider: resolved.provider,
    configured: resolved.configured,
    reason: resolved.reason,
    forced: Boolean(resolved.forced),
    requestTimeoutMs: bridgeTimeoutMs(),
    providers: BRIDGE_PROVIDERS.map((provider) => ({ provider, ...providerAvailability(provider) })),
    metaApi: { region: metaApi.region || null, clientBase: metaApi.clientBase, tokenPresent: Boolean(metaApi.token) },
    relay: { baseUrl: relay.baseUrl || null, path: relay.path, tokenPresent: Boolean(relay.token) },
    webApi: { baseUrl: webApi.baseUrl || null, login: webApi.login || null, passwordPresent: Boolean(webApi.password) },
  };
}

function resolveFetch(fetchImpl) {
  const impl = fetchImpl || globalThis.fetch;
  if (typeof impl !== "function") throw new Error("no fetch implementation available (Node 18+ required)");
  return impl;
}

/** JSON HTTP helper with a hard timeout; throws with status/data attached on failure. */
export async function requestJson(url, { method = "GET", headers = {}, body = null, timeoutMs, fetchImpl } = {}) {
  const effectiveTimeout = timeoutMs || bridgeTimeoutMs();
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), effectiveTimeout);
  try {
    const response = await resolveFetch(fetchImpl)(url, {
      method,
      headers: {
        accept: "application/json",
        ...(body ? { "content-type": "application/json" } : {}),
        ...headers,
      },
      body: body ? JSON.stringify(body) : undefined,
      signal: controller.signal,
      cache: "no-store",
    });
    const text = await response.text();
    let data = null;
    if (text) {
      try {
        data = JSON.parse(text);
      } catch {
        data = text;
      }
    }
    if (!response.ok) {
      const message = typeof data === "string" ? data : data?.message || data?.error || response.statusText;
      const error = new Error(`bridge request failed (${response.status}): ${message}`);
      error.status = response.status;
      error.data = data;
      throw error;
    }
    return data;
  } catch (error) {
    if (error?.name === "AbortError") {
      const timeoutError = new Error(`bridge request timed out after ${effectiveTimeout}ms`);
      timeoutError.code = "BRIDGE_TIMEOUT";
      throw timeoutError;
    }
    throw error;
  } finally {
    clearTimeout(timer);
  }
}

/** ISO-8601 timestamp, accepting Date / epoch seconds / epoch millis / ISO strings. */
export function toIsoTimestamp(value) {
  if (value === null || value === undefined || value === "") return new Date().toISOString();
  if (value instanceof Date) return value.toISOString();
  const numeric = typeof value === "number" ? value : /^\d+$/.test(String(value)) ? Number(value) : null;
  if (numeric !== null) return new Date(numeric < 1e12 ? numeric * 1000 : numeric).toISOString();
  const date = new Date(String(value));
  return Number.isNaN(date.getTime()) ? new Date().toISOString() : date.toISOString();
}

/**
 * De-dupe raw deals by their bridge id. Protects the sync from bridges that
 * re-send pages (or ignore offset paging) instead of trusting them to be correct.
 */
export function dedupeDealsById(deals = []) {
  const seen = new Set();
  const unique = [];
  for (const deal of deals || []) {
    const key = String(
      deal?.id ??
        deal?.ticket ??
        deal?.Deal ??
        deal?.dealId ??
        `${deal?.positionId || deal?.PositionID || ""}:${deal?.time || deal?.Time || ""}`,
    );
    if (seen.has(key)) continue;
    seen.add(key);
    unique.push(deal);
  }
  return unique;
}

/**
 * MetaApi: closed deals for an account between two instants.
 * GET {client}/users/current/accounts/{accountId}/history-deals/time/{start}/{end}
 */
export async function fetchDealsMetaApi({
  accountId,
  since,
  until,
  token,
  region,
  fetchImpl,
  pageSize = 1000,
  maxPages = 50,
} = {}) {
  const config = metaApiConfig();
  const authToken = token || config.token;
  if (!authToken) throw new Error("METAAPI_TOKEN is not set");
  if (!accountId) throw new Error("MetaApi account id is required");

  const base = `${metaApiHosts(region || config.region).clientBase}/users/current/accounts/${encodeURIComponent(accountId)}/history-deals/time/${toIsoTimestamp(since)}/${toIsoTimestamp(until)}`;
  const collected = [];
  let offset = 0;
  let pages = 0;
  for (let page = 0; page < maxPages; page += 1) {
    const payload = await requestJson(`${base}?limit=${pageSize}&offset=${offset}`, {
      headers: { "auth-token": authToken },
      fetchImpl,
    });
    const batch = Array.isArray(payload) ? payload : payload?.deals || payload?.items || [];
    collected.push(...batch);
    pages += 1;
    if (batch.length < pageSize) break;
    offset += pageSize;
  }
  return {
    deals: dedupeDealsById(collected),
    provider: "metaapi",
    meta: { accountId, since: toIsoTimestamp(since), until: toIsoTimestamp(until), pages, truncated: pages >= maxPages },
  };
}

/**
 * MetaApi: find (or create) the cloud terminal for an MT5 account.
 * The MT5 credentials travel only to MetaApi; the database keeps them encrypted.
 */
export async function ensureMetaApiAccount({
  login,
  password,
  server,
  region,
  accountId,
  name,
  token,
  fetchImpl,
} = {}) {
  const config = metaApiConfig();
  const authToken = token || config.token;
  if (!authToken) throw new Error("METAAPI_TOKEN is not set");
  const hosts = metaApiHosts(region || config.region);
  const headers = { "auth-token": authToken };

  const accounts = await requestJson(`${hosts.provisioningBase}/users/current/accounts`, { headers, fetchImpl });
  const list = Array.isArray(accounts) ? accounts : accounts?.items || [];
  const existing = list.find(
    (account) =>
      (accountId && account?._id === accountId) ||
      (String(account?.login || "") === String(login || "") && String(account?.server || "") === String(server || "")),
  );
  if (existing) return { account: existing, created: false, provider: "metaapi" };

  if (!login || !password || !server) {
    throw new Error("login, password and server are required to provision a MetaApi account");
  }
  const account = await requestJson(`${hosts.provisioningBase}/users/current/accounts`, {
    method: "POST",
    headers,
    fetchImpl,
    body: {
      login: String(login),
      password: String(password),
      name: name || `kingsbalfx-${login}`,
      server: String(server),
      platform: "mt5",
      magic: 0,
      ...(region ? { region } : {}),
    },
  });
  return { account, created: true, provider: "metaapi" };
}

/**
 * MT5 WebAPI manager session: auth/start issues an srv_rand challenge, auth/answer
 * replies with md5(md5(password) + srv_rand) and validates the platform's answer.
 */
async function connectWebApi({ baseUrl, login, password, fetchImpl } = {}) {
  const md5 = (value) => crypto.createHash("md5").update(String(value)).digest("hex");
  const start = await requestJson(`${baseUrl}/api/auth/start`, {
    method: "POST",
    fetchImpl,
    body: { version: "3.16", agent: "kingsbalfx-sync", login: String(login), type: "manager" },
  });
  const srvRand = start?.srv_rand;
  if (!srvRand) throw new Error("MT5 WebAPI did not return srv_rand");

  const cliRand = crypto.randomBytes(16).toString("hex");
  const answer = await requestJson(`${baseUrl}/api/auth/answer`, {
    method: "POST",
    fetchImpl,
    body: { srv_rand_answer: md5(md5(password) + srvRand), cli_rand: cliRand },
  });
  const cliRandAnswer = answer?.cli_rand_answer;
  if (!cliRandAnswer) throw new Error("MT5 WebAPI authentication failed");
  if (String(cliRandAnswer).toLowerCase() !== md5(md5(password) + cliRand)) {
    throw new Error("MT5 WebAPI authentication failed (manager password mismatch)");
  }
  return { authenticated: true };
}

/**
 * MT5 WebAPI: deal history for one client login.
 * The manager session authenticates once; get_total sizes the get_page loop and
 * the time window is applied client side (get_page has no time filter).
 */
export async function fetchDealsWebApi({
  login,
  since,
  until,
  baseUrl,
  managerLogin,
  managerPassword,
  fetchImpl,
  pageSize = 500,
  maxPages = 60,
} = {}) {
  const config = webApiConfig();
  const base = String(baseUrl || config.baseUrl || "").replace(/\/+$/, "");
  const mgrLogin = managerLogin || config.login;
  const mgrPassword = managerPassword || config.password;
  if (!base) throw new Error("MT5_WEBAPI_URL is not set");
  if (!mgrLogin || !mgrPassword) throw new Error("MT5_WEBAPI_LOGIN / MT5_WEBAPI_PASSWORD are not set");
  if (!login) throw new Error("client login is required");

  await connectWebApi({ baseUrl: base, login: mgrLogin, password: mgrPassword, fetchImpl });

  const totalPayload = await requestJson(`${base}/api/deal/get_total?login=${encodeURIComponent(login)}`, { fetchImpl });
  const total = Number(totalPayload?.answer?.total ?? totalPayload?.total ?? 0) || 0;
  const sinceMs = new Date(toIsoTimestamp(since)).getTime();
  const untilMs = new Date(toIsoTimestamp(until)).getTime();

  const collected = [];
  let offset = 0;
  let pages = 0;
  while (offset < total && pages < maxPages) {
    const payload = await requestJson(
      `${base}/api/deal/get_page?login=${encodeURIComponent(login)}&offset=${offset}&total=${pageSize}`,
      { fetchImpl },
    );
    const batch = Array.isArray(payload?.answer) ? payload.answer : [];
    if (!batch.length) break;
    collected.push(...batch);
    pages += 1;
    offset += batch.length;
  }

  const deals = dedupeDealsById(collected).filter((deal) => {
    const ms = new Date(toIsoTimestamp(deal?.Time ?? deal?.time ?? sinceMs)).getTime();
    return ms >= sinceMs && ms <= untilMs;
  });

  return {
    deals,
    provider: "mt5webapi",
    meta: {
      login: String(login),
      total,
      pages,
      truncated: pages >= maxPages && offset < total,
      since: new Date(sinceMs).toISOString(),
      until: new Date(untilMs).toISOString(),
    },
  };
}

/**
 * Relay: the project's own bot host exposes closed deals it reads from its MT5
 * terminal. Contract is documented in MT5_TRADE_SYNC.md and the bot repo; the
 * response may be a bare array or { deals | data | trades: [...] }.
 */
export async function fetchDealsRelay({ login, server, since, until, fetchImpl, limit = 5000, path } = {}) {
  const config = relayConfig();
  const base = String(config.baseUrl || "").replace(/\/+$/, "");
  if (!base) throw new Error("MT5_RELAY_URL / BOT_API_URL is not set");
  if (!config.token) throw new Error("MT5_RELAY_TOKEN / BOT_API_TOKEN is not set");
  if (!login) throw new Error("login is required for the relay bridge");

  const payload = await requestJson(`${base}${path || config.path}`, {
    method: "POST",
    headers: { "X-Bot-Token": config.token, "x-api-key": config.token },
    fetchImpl,
    body: {
      login: String(login),
      server: server ? String(server) : undefined,
      since: toIsoTimestamp(since),
      until: toIsoTimestamp(until),
      limit,
    },
  });
  const deals = Array.isArray(payload) ? payload : payload?.deals || payload?.data || payload?.trades || [];
  return {
    deals: dedupeDealsById(deals),
    provider: "relay",
    meta: {
      login: String(login),
      since: toIsoTimestamp(since),
      until: toIsoTimestamp(until),
      returned: deals.length,
      upstream: payload?.meta || null,
    },
  };
}

/**
 * Single entry point used by services/mt5Sync.js: picks the configured provider and
 * returns raw deals plus metadata. Throws with code BRIDGE_NOT_CONFIGURED when no
 * bridge is available so callers can degrade gracefully instead of crashing a cron.
 */
export async function fetchDealsForLink({ link = {}, since, until, provider, fetchImpl, pageSize, maxPages } = {}) {
  const resolved = resolveBridgeProvider(provider);
  if (!resolved.configured) {
    const error = new Error(resolved.reason || "MT5 bridge is not configured");
    error.code = "BRIDGE_NOT_CONFIGURED";
    throw error;
  }
  if (resolved.provider === "metaapi") {
    return fetchDealsMetaApi({
      accountId: link.bridge_account_id || link.bridgeAccountId || link.accountId,
      since,
      until,
      fetchImpl,
      pageSize,
      maxPages,
    });
  }
  if (resolved.provider === "mt5webapi") {
    return fetchDealsWebApi({ login: link.login, since, until, fetchImpl, pageSize, maxPages });
  }
  return fetchDealsRelay({ login: link.login, server: link.server, since, until, fetchImpl });
}





