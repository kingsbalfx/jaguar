/**
 * MT5 trade-history sync service.
 *
 * Flow: Vercel cron (or a user/admin API call) -> list syncable mt5_account_links ->
 * fetch closed deals from the configured cloud bridge -> pair IN/OUT deals into
 * closed positions (lib/mt5-normalize.js) -> upsert trade_history -> rebuild
 * pair_analytics -> update the link cursor -> write an mt5_sync_runs audit row.
 *
 * The service never throws out of syncAllLinks(): per-link failures are recorded on
 * the link row and in mt5_sync_runs so one broken account cannot stop the cron.
 */
import { fetchDealsForLink, getBridgeHealth } from "../lib/mt5-bridge.js";
import { dedupeTradeRows, toTradeRows } from "../lib/mt5-normalize.js";
import { buildPairAnalyticsRows, listRecentPeriods } from "../lib/mt5-metrics.js";

export const DEFAULT_LOOKBACK_DAYS = 120;
export const OVERLAP_MINUTES = 15;
export const MAX_TRADES_PER_RUN = 2000;
export const ANALYTICS_TRADE_LIMIT = 5000;
export const MAX_LINKS_PER_RUN = 50;
export const ANALYTICS_PERIODS = 12;

function envInt(name, fallback) {
  const value = Number.parseInt(String(process.env[name] ?? ""), 10);
  return Number.isFinite(value) && value > 0 ? value : fallback;
}

function toDate(value, fallback = null) {
  if (!value) return fallback;
  const date = value instanceof Date ? value : new Date(value);
  return Number.isNaN(date.getTime()) ? fallback : date;
}

export function chunk(items = [], size = 200) {
  const safeSize = Math.max(1, size);
  const chunks = [];
  for (let index = 0; index < (items || []).length; index += safeSize) {
    chunks.push(items.slice(index, index + safeSize));
  }
  return chunks;
}

/** Supabase/PostgREST errors raised before the migration has been applied. */
export function isMissingRelationError(error) {
  const code = String(error?.code || "");
  if (code === "42P01" || code === "PGRST205") return true;
  const message = String(error?.message || "").toLowerCase();
  return message.includes("does not exist") && (message.includes("relation") || message.includes("table"));
}

export function resolveLookbackDays(link = {}) {
  const fromLink = Number(link.sync_lookback_days);
  if (Number.isFinite(fromLink) && fromLink > 0) return Math.min(fromLink, 3650);
  return envInt("MT5_SYNC_LOOKBACK_DAYS", DEFAULT_LOOKBACK_DAYS);
}

/**
 * Sync window: start from the link cursor (minus a small overlap so deals that
 * settle late are not missed), or fall back to the lookback window on first run.
 */
export function computeSyncWindow({ link = {}, now = new Date(), lookbackDays, overlapMinutes = OVERLAP_MINUTES } = {}) {
  const until = toDate(now, new Date());
  const cursor = toDate(link.last_deal_time) || toDate(link.last_synced_at);
  const days = Number.isFinite(Number(lookbackDays)) ? Number(lookbackDays) : resolveLookbackDays(link);
  if (cursor) {
    const since = new Date(cursor.getTime() - overlapMinutes * 60 * 1000);
    return { since, until, mode: "incremental" };
  }
  return { since: new Date(until.getTime() - days * 24 * 60 * 60 * 1000), until, mode: "backfill" };
}

/** Account links the worker should process, newest activity first. */
export async function listSyncableLinks(supabaseAdmin, { linkIds = null, limit = MAX_LINKS_PER_RUN } = {}) {
  let query = supabaseAdmin
    .from("mt5_account_links")
    .select("id,user_id,email,login,server,label,provider,bridge_account_id,bridge_region,provisioning_status,sync_enabled,sync_status,sync_error,last_synced_at,last_deal_time,sync_lookback_days,password_encrypted,password_iv,password_tag,password_last4,created_at")
    .eq("sync_enabled", true)
    .order("last_synced_at", { ascending: true, nullsFirst: true })
    .limit(Math.min(Number(limit) || MAX_LINKS_PER_RUN, MAX_LINKS_PER_RUN));

  if (Array.isArray(linkIds) && linkIds.length) query = query.in("id", linkIds);
  const { data, error } = await query;
  if (error) throw error;
  return data || [];
}

/**
 * Upsert paired trades. Reports inserted vs refreshed so the run audit is meaningful.
 */
export async function storeTrades(supabaseAdmin, rows = []) {
  const unique = dedupeTradeRows(rows)
    .filter((row) => row?.link_id && row?.deal_ticket)
    .slice(0, MAX_TRADES_PER_RUN);
  if (!unique.length) return { inserted: 0, updated: 0, rows: [] };

  let inserted = 0;
  let updated = 0;
  for (const batch of chunk(unique, 200)) {
    const { data: existing, error: readError } = await supabaseAdmin
      .from("trade_history")
      .select("deal_ticket")
      .eq("link_id", batch[0].link_id)
      .in("deal_ticket", batch.map((row) => row.deal_ticket));
    if (readError) throw readError;
    const known = new Set((existing || []).map((row) => String(row.deal_ticket)));

    const { error } = await supabaseAdmin
      .from("trade_history")
      .upsert(batch, { onConflict: "link_id,deal_ticket" });
    if (error) throw error;

    for (const row of batch) {
      if (known.has(String(row.deal_ticket))) updated += 1;
      else inserted += 1;
    }
  }
  return { inserted, updated, rows: unique };
}

/** Read stored trades for one link (paged, capped) for analytics rebuilds. */
export async function readTradesForLink(supabaseAdmin, linkId, { limit = ANALYTICS_TRADE_LIMIT } = {}) {
  const pageSize = 1000;
  const rows = [];
  for (let offset = 0; offset < limit; offset += pageSize) {
    const { data, error } = await supabaseAdmin
      .from("trade_history")
      .select("link_id,user_id,account_login,symbol,side,volume,pips,profit,commission,swap,storage,net_pnl,exit_reason,open_time,close_time,period")
      .eq("link_id", linkId)
      .order("close_time", { ascending: true })
      .range(offset, offset + pageSize - 1);
    if (error) throw error;
    rows.push(...(data || []));
    if ((data || []).length < pageSize) break;
  }
  return rows;
}

/** Period buckets the analytics rebuild keeps in sync: all-time + recent months. */
export function analyticsPeriodsFor(trades = [], { periods = ANALYTICS_PERIODS, now = new Date() } = {}) {
  const allowed = new Set(["all", ...listRecentPeriods(periods, now)]);
  for (const trade of trades || []) {
    const period = String(trade?.period || "");
    if (period && allowed.has(period)) allowed.add(period);
  }
  return Array.from(allowed);
}

/**
 * Rebuild pair_analytics for a link: delete the periods we own, then re-insert
 * aggregated rows so removed/renamed symbols can never linger as stale data.
 */
export async function rebuildPairAnalytics(supabaseAdmin, { link, trades } = {}) {
  if (!link?.id) return { rows: 0, periods: [] };
  const source = trades || (await readTradesForLink(supabaseAdmin, link.id));
  const periods = analyticsPeriodsFor(source);
  const analytics = [];

  for (const period of periods) {
    const scoped = period === "all" ? source : source.filter((trade) => String(trade.period) === period);
    if (!scoped.length && period !== "all") continue;
    analytics.push(...buildPairAnalyticsRows({ trades: scoped, link, period }));
  }

  const { error: deleteError } = await supabaseAdmin.from("pair_analytics").delete().eq("link_id", link.id).in("period", periods);
  if (deleteError) throw deleteError;

  if (analytics.length) {
    for (const batch of chunk(analytics, 200)) {
      const { error } = await supabaseAdmin.from("pair_analytics").upsert(batch, { onConflict: "link_id,period,symbol" });
      if (error) throw error;
    }
  }
  return { rows: analytics.length, periods };
}

/**
 * Audit row for a sync attempt. Auditing never breaks a run: failures are logged.
 */
export async function recordSyncRun(supabaseAdmin, payload = {}) {
  try {
    const { data, error } = await supabaseAdmin
      .from("mt5_sync_runs")
      .insert({
        link_id: payload.linkId || null,
        user_id: payload.userId || null,
        account_login: payload.accountLogin || null,
        trigger: payload.trigger || "cron",
        status: payload.status || "success",
        provider: payload.provider || null,
        window_from: payload.windowFrom || null,
        window_to: payload.windowTo || null,
        deals_received: payload.dealsReceived || 0,
        trades_inserted: payload.tradesInserted || 0,
        trades_updated: payload.tradesUpdated || 0,
        trades_skipped: payload.tradesSkipped || 0,
        analytics_rows: payload.analyticsRows || 0,
        duration_ms: payload.durationMs ?? null,
        error: payload.error || null,
        context: payload.context || null,
        created_at: new Date().toISOString(),
      })
      .select("id")
      .maybeSingle();
    if (error) {
      if (!isMissingRelationError(error)) console.error("mt5 sync run audit failed:", error.message);
      return { recorded: false, id: null };
    }
    return { recorded: true, id: data?.id || null };
  } catch (error) {
    console.error("mt5 sync run audit failed:", error?.message || error);
    return { recorded: false, id: null };
  }
}

/** Persist the sync cursor / status on the link row. */
export async function updateLinkStatus(supabaseAdmin, linkId, patch = {}) {
  const { error } = await supabaseAdmin
    .from("mt5_account_links")
    .update({ ...patch, updated_at: new Date().toISOString() })
    .eq("id", linkId);
  if (error && !isMissingRelationError(error)) throw error;
  return !error;
}

/**
 * Sync one account link end to end. Never throws: bridge / database failures are
 * recorded on the link row and in mt5_sync_runs, and returned in the result.
 */
export async function syncLink({
  supabaseAdmin,
  link,
  trigger = "cron",
  now = new Date(),
  provider,
  fetchImpl,
  lookbackDays,
  overlapMinutes,
} = {}) {
  if (!supabaseAdmin) throw new Error("Supabase admin client is required");
  if (!link?.id) throw new Error("link is required");

  const startedAt = Date.now();
  const window = computeSyncWindow({ link, now, lookbackDays, overlapMinutes });
  const base = {
    linkId: link.id,
    userId: link.user_id || null,
    accountLogin: link.login || null,
    trigger,
    windowFrom: window.since.toISOString(),
    windowTo: window.until.toISOString(),
  };

  try {
    const { deals, provider: usedProvider, meta } = await fetchDealsForLink({
      link,
      since: window.since,
      until: window.until,
      provider,
      fetchImpl,
    });

    const rows = toTradeRows(deals, { link, source: usedProvider });
    const { inserted, updated } = await storeTrades(supabaseAdmin, rows);
    const skipped = Math.max(deals.length - rows.length, 0);

    let analyticsRows = 0;
    if (rows.length > 0 || !Number(link.total_synced_deals || 0)) {
      const trades = await readTradesForLink(supabaseAdmin, link.id);
      const analytics = await rebuildPairAnalytics(supabaseAdmin, { link, trades });
      analyticsRows = analytics.rows;
    }

    const lastDealTime = rows.reduce((latest, row) => {
      if (!row.close_time) return latest;
      if (!latest) return row.close_time;
      return new Date(row.close_time) > new Date(latest) ? row.close_time : latest;
    }, null);

    const truncated = Boolean(meta?.truncated);
    await updateLinkStatus(supabaseAdmin, link.id, {
      sync_status: truncated ? "partial" : "success",
      sync_error: truncated ? "bridge window truncated: run again to continue backfill" : null,
      provider: usedProvider,
      provisioning_status: "ready",
      provisioning_error: null,
      bridge_account_id: meta?.accountId || link.bridge_account_id || null,
      last_synced_at: new Date().toISOString(),
      last_deal_time: lastDealTime || link.last_deal_time || null,
      last_sync_deals: deals.length,
      total_synced_deals: Number(link.total_synced_deals || 0) + inserted,
    });

    await recordSyncRun(supabaseAdmin, {
      ...base,
      status: truncated ? "partial" : "success",
      provider: usedProvider,
      dealsReceived: deals.length,
      tradesInserted: inserted,
      tradesUpdated: updated,
      tradesSkipped: skipped,
      analyticsRows,
      durationMs: Date.now() - startedAt,
      context: { bridge: meta || null, windowMode: window.mode },
    });

    return {
      ok: !truncated,
      status: truncated ? "partial" : "success",
      linkId: link.id,
      login: link.login || null,
      provider: usedProvider,
      dealsReceived: deals.length,
      tradesInserted: inserted,
      tradesUpdated: updated,
      tradesSkipped: skipped,
      analyticsRows,
      windowMode: window.mode,
      windowFrom: base.windowFrom,
      windowTo: base.windowTo,
      lastDealTime,
      durationMs: Date.now() - startedAt,
      truncated,
    };
  } catch (error) {
    const message = error?.message || String(error);
    const durationMs = Date.now() - startedAt;
    await updateLinkStatus(supabaseAdmin, link.id, {
      sync_status: "error",
      sync_error: message.slice(0, 500),
    });
    await recordSyncRun(supabaseAdmin, {
      ...base,
      status: "error",
      provider: provider || null,
      durationMs,
      error: message.slice(0, 500),
      context: { code: error?.code || null, status: error?.status || null },
    });
    return {
      ok: false,
      status: "error",
      linkId: link.id,
      login: link.login || null,
      error: message,
      code: error?.code || null,
      durationMs,
    };
  }
}

/**
 * Process every syncable link sequentially: kind to the bridge and safe inside the
 * Vercel function budget. Returns a per-link summary plus totals.
 */
export async function syncAllLinks({
  supabaseAdmin,
  trigger = "cron",
  linkIds = null,
  limit = MAX_LINKS_PER_RUN,
  now = new Date(),
  provider,
  fetchImpl,
  lookbackDays,
  overlapMinutes,
} = {}) {
  if (!supabaseAdmin) throw new Error("Supabase admin client is required");
  const bridge = getBridgeHealth();
  if (!bridge.configured) {
    return {
      ok: false,
      status: "skipped",
      reason: bridge.reason,
      bridge,
      linksProcessed: 0,
      results: [],
      totals: { links: 0, dealsReceived: 0, tradesInserted: 0, tradesUpdated: 0, failures: 0, durationMs: 0 },
    };
  }

  const startedAt = Date.now();
  const links = await listSyncableLinks(supabaseAdmin, { linkIds, limit });
  const results = [];
  for (const link of links) {
    results.push(await syncLink({ supabaseAdmin, link, trigger, now, provider, fetchImpl, lookbackDays, overlapMinutes }));
  }

  const totals = { links: links.length, dealsReceived: 0, tradesInserted: 0, tradesUpdated: 0, failures: 0 };
  for (const result of results) {
    totals.dealsReceived += result.dealsReceived || 0;
    totals.tradesInserted += result.tradesInserted || 0;
    totals.tradesUpdated += result.tradesUpdated || 0;
    if (!result.ok) totals.failures += 1;
  }

  return {
    ok: totals.failures === 0,
    status: totals.failures ? "partial" : "success",
    bridge,
    linksProcessed: links.length,
    results,
    totals: { ...totals, durationMs: Date.now() - startedAt },
  };
}

/**
 * Status payload for the sync panels: bridge health, link rows (never credentials)
 * and the most recent sync runs, scoped to the caller unless they are an admin.
 */
export async function getSyncSnapshot(supabaseAdmin, { userId, isAdmin = false, linkIds = null, limit = 20 } = {}) {
  const safeLimit = Math.min(Math.max(Number(limit) || 20, 1), 100);
  const linkColumns =
    "id,user_id,email,login,server,label,currency,leverage,provider,bridge_account_id,bridge_region,provisioning_status,provisioning_error,sync_enabled,sync_status,sync_error,last_synced_at,last_deal_time,last_sync_deals,total_synced_deals,password_last4,created_at,updated_at";

  let linkQuery = supabaseAdmin
    .from("mt5_account_links")
    .select(linkColumns)
    .order("created_at", { ascending: false })
    .limit(safeLimit);
  if (!isAdmin && userId) linkQuery = linkQuery.eq("user_id", userId);
  if (isAdmin && Array.isArray(linkIds) && linkIds.length) linkQuery = linkQuery.in("id", linkIds);

  const linkResult = await linkQuery;
  if (linkResult.error && !isMissingRelationError(linkResult.error)) throw linkResult.error;
  const links = linkResult.error ? [] : linkResult.data || [];

  const runQuery = supabaseAdmin
    .from("mt5_sync_runs")
    .select("id,link_id,user_id,account_login,trigger,status,provider,deals_received,trades_inserted,trades_updated,trades_skipped,analytics_rows,duration_ms,error,created_at")
    .order("created_at", { ascending: false })
    .limit(safeLimit);
  const scopedRunQuery = !isAdmin && userId ? runQuery.eq("user_id", userId) : runQuery;
  const runResult = await scopedRunQuery;
  if (runResult.error && !isMissingRelationError(runResult.error)) throw runResult.error;
  const runs = runResult.error ? [] : runResult.data || [];

  let statusQuery = supabaseAdmin.from("mt5_account_links").select("sync_status").limit(1000);
  if (!isAdmin && userId) statusQuery = statusQuery.eq("user_id", userId);
  const statusResult = await statusQuery;
  const statuses = statusResult.error ? [] : statusResult.data || [];

  return {
    bridge: getBridgeHealth(),
    links,
    runs,
    setupRequired: Boolean(linkResult.error || runResult.error),
    totals: {
      links: links.length,
      enabled: links.filter((link) => link.sync_enabled).length,
      errors: links.filter((link) => link.sync_status === "error").length,
      totalSyncedDeals: links.reduce((sum, link) => sum + Number(link.total_synced_deals || 0), 0),
      statuses: statuses.reduce((buckets, row) => {
        const key = String(row.sync_status || "unknown");
        buckets[key] = (buckets[key] || 0) + 1;
        return buckets;
      }, {}),
    },
  };
}



