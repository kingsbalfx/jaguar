import { requireAdmin, toPositiveInt } from "../../../lib/api-auth";
import { aggregateMacroPerformance, listRecentPeriods, normalizePeriodFilter, periodLabel } from "../../../lib/mt5-metrics";
import { EXIT_REASON_ORDER, exitReasonBreakdown, exitReasonLabel } from "../../../lib/mt5-exit-reason";
import { MAX_LINKS_PER_RUN, getSyncSnapshot, syncAllLinks, syncLink } from "../../../services/mt5Sync";

const TRADE_COLUMNS = "link_id,user_id,account_login,symbol,side,volume,pips,net_pnl,exit_reason,close_time,period";
const MAX_SCAN_ROWS = 5000;

function isMissingRelation(error) {
  const code = String(error?.code || "");
  return code === "42P01" || code === "PGRST205" || /does not exist/i.test(String(error?.message || ""));
}

/**
 * Admin macro performance overview: platform roll-up, per-account and per-pair
 * breakdowns, exit-reason mix, sync health and recent sync runs.
 * POST body { linkId?, all?, reset?, lookbackDays? } triggers a sync.
 */
export default async function handler(req, res) {
  if (req.method !== "GET" && req.method !== "POST") {
    return res.status(405).json({ error: "Method not allowed" });
  }

  const auth = await requireAdmin(req, res);
  if (!auth.ok) return res.status(auth.status).json({ error: auth.error });
  const { supabaseAdmin } = auth;

  try {
    if (req.method === "POST") {
      const body = req.body || {};
      const linkId = String(body.linkId || "").trim();
      const trigger = "admin";

      if (linkId && body.reset) {
        await supabaseAdmin
          .from("mt5_account_links")
          .update({ last_deal_time: null, last_synced_at: null, updated_at: new Date().toISOString() })
          .eq("id", linkId);
      }

      if (!linkId || body.all) {
        const result = await syncAllLinks({
          supabaseAdmin,
          trigger,
          limit: toPositiveInt(body.limit, MAX_LINKS_PER_RUN, { min: 1, max: MAX_LINKS_PER_RUN }),
          linkIds: linkId ? [linkId] : null,
        });
        return res.status(result.status === "skipped" ? 200 : result.ok ? 200 : 207).json(result);
      }

      const { data: link, error } = await supabaseAdmin
        .from("mt5_account_links")
        .select(
          "id,user_id,login,server,label,provider,bridge_account_id,bridge_region,sync_enabled,sync_status,last_synced_at,last_deal_time,sync_lookback_days,total_synced_deals",
        )
        .eq("id", linkId)
        .maybeSingle();
      if (error) return res.status(500).json({ error: error.message });
      if (!link) return res.status(404).json({ error: "account link not found" });

      const result = await syncLink({
        supabaseAdmin,
        link,
        trigger,
        provider: body.provider || undefined,
        lookbackDays: body.lookbackDays ? Number(body.lookbackDays) : undefined,
      });
      return res.status(result.ok ? 200 : result.status === "partial" ? 207 : 502).json(result);
    }

    const period = normalizePeriodFilter(req.query.period);
    const userId = String(req.query.userId || req.query.user_id || "").trim();
    const linkId = String(req.query.linkId || "").trim();

    let tradeQuery = supabaseAdmin
      .from("trade_history")
      .select(TRADE_COLUMNS)
      .order("close_time", { ascending: false })
      .limit(toPositiveInt(req.query.limit, MAX_SCAN_ROWS, { min: 1, max: MAX_SCAN_ROWS }));
    if (period !== "all") tradeQuery = tradeQuery.eq("period", period);
    if (userId) tradeQuery = tradeQuery.eq("user_id", userId);
    if (linkId) tradeQuery = tradeQuery.eq("link_id", linkId);

    const [tradeResult, linkResult] = await Promise.all([
      tradeQuery,
      supabaseAdmin
        .from("mt5_account_links")
        .select("id,user_id,email,login,server,label,sync_enabled,sync_status,sync_error,last_synced_at,last_deal_time,total_synced_deals")
        .order("last_synced_at", { ascending: false, nullsFirst: false })
        .limit(200),
    ]);

    const missingTrades = isMissingRelation(tradeResult.error);
    if (tradeResult.error && !missingTrades) return res.status(500).json({ error: tradeResult.error.message });
    if (linkResult.error && !isMissingRelation(linkResult.error)) {
      return res.status(500).json({ error: linkResult.error.message });
    }

    const trades = missingTrades ? [] : tradeResult.data || [];
    const links = linkResult.error ? [] : linkResult.data || [];
    const macro = aggregateMacroPerformance({ trades, links });
    const snapshot = await getSyncSnapshot(supabaseAdmin, { isAdmin: true, limit: 20 });

    return res.status(200).json({
      ok: true,
      period,
      periodLabel: periodLabel(period),
      periods: listRecentPeriods(12).map((value) => ({ value, label: periodLabel(value) })),
      filters: { userId: userId || null, linkId: linkId || null, scanned: trades.length },
      setupRequired: Boolean(missingTrades),
      bridge: snapshot.bridge,
      runs: snapshot.runs,
      links,
      accounts: macro.accounts,
      pairs: macro.pairs,
      totals: macro.totals,
      topPair: macro.topPair,
      worstPair: macro.worstPair,
      activeAccounts: macro.activeAccounts,
      linkedAccounts: macro.linkedAccounts,
      exitReasons: exitReasonBreakdown(trades).map((bucket) => ({
        ...bucket,
        label: exitReasonLabel(bucket.reason),
        order: EXIT_REASON_ORDER.indexOf(bucket.reason),
      })),
    });
  } catch (error) {
    console.error("admin mt5 performance failed:", error);
    return res.status(500).json({ error: error?.message || "failed to load MT5 performance" });
  }
}
