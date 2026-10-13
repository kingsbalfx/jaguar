import { authenticateRequest, toPositiveInt } from "../../../lib/api-auth";
import {
  aggregateTrades,
  computePairMetrics,
  listRecentPeriods,
  normalizePeriodFilter,
  paginate,
  periodLabel,
  sortTrades,
} from "../../../lib/mt5-metrics";
import { EXIT_REASON_ORDER, exitReasonBreakdown, exitReasonLabel } from "../../../lib/mt5-exit-reason";

const TRADE_COLUMNS =
  "id,link_id,user_id,account_login,server,symbol,side,volume,open_price,close_price,open_time,close_time,duration_seconds,pips,profit,commission,swap,net_pnl,exit_reason,exit_source,magic,comment,broker_comment,source,period,created_at";
const MAX_ROWS = 5000;

function parseDate(value) {
  if (!value) return null;
  const date = new Date(String(value));
  return Number.isNaN(date.getTime()) ? null : date.toISOString();
}

function isMissingRelation(error) {
  const code = String(error?.code || "");
  return code === "42P01" || code === "PGRST205" || /does not exist/i.test(String(error?.message || ""));
}

/**
 * Closed-trade history for the signed-in trader (or every account for an admin
 * passing ?scope=all). Returns the paged rows plus the summary, per-pair and
 * per-exit-reason breakdowns computed from the same filtered set.
 */
export default async function handler(req, res) {
  if (req.method !== "GET") return res.status(405).json({ error: "Method not allowed" });

  const auth = await authenticateRequest(req, res);
  if (!auth.ok) return res.status(auth.status).json({ error: auth.error });
  const { supabaseAdmin } = auth;

  try {
    const scopeAll = auth.isAdmin && String(req.query.scope || "").toLowerCase() === "all";
    const period = normalizePeriodFilter(req.query.period);
    const symbol = String(req.query.symbol || "").trim().toUpperCase();
    const exitReason = String(req.query.exitReason || req.query.exit_reason || "").trim().toUpperCase();
    const side = String(req.query.side || "").trim().toLowerCase();
    const linkId = String(req.query.linkId || "").trim();
    const from = parseDate(req.query.from);
    const to = parseDate(req.query.to);

    let query = supabaseAdmin
      .from("trade_history")
      .select(TRADE_COLUMNS)
      .order("close_time", { ascending: false })
      .limit(MAX_ROWS);

    if (!scopeAll) query = query.eq("user_id", auth.session.user.id);
    if (period !== "all") query = query.eq("period", period);
    if (symbol) query = query.eq("symbol", symbol);
    if (exitReason && EXIT_REASON_ORDER.includes(exitReason)) query = query.eq("exit_reason", exitReason);
    if (side === "buy" || side === "sell") query = query.eq("side", side);
    if (linkId) query = query.eq("link_id", linkId);
    if (from) query = query.gte("close_time", from);
    if (to) query = query.lte("close_time", to);

    const { data, error } = await query;
    if (error && !isMissingRelation(error)) return res.status(500).json({ error: error.message });

    const rows = error ? [] : data || [];
    const sorted = sortTrades(rows, {
      sortBy: req.query.sortBy || "close_time",
      direction: req.query.sortDir || req.query.direction || "desc",
    });
    const page = paginate(sorted, {
      page: toPositiveInt(req.query.page, 1),
      pageSize: toPositiveInt(req.query.pageSize, 25, { min: 1, max: 200 }),
    });

    return res.status(200).json({
      ok: true,
      scope: scopeAll ? "all" : "own",
      setupRequired: Boolean(error),
      filters: { period, symbol: symbol || null, exitReason: exitReason || null, side: side || null, linkId: linkId || null, from, to },
      periodLabel: periodLabel(period),
      periods: listRecentPeriods(12).map((value) => ({ value, label: periodLabel(value) })),
      trades: page.items,
      pagination: {
        page: page.page,
        pageSize: page.pageSize,
        total: page.total,
        totalPages: page.totalPages,
        hasMore: page.hasMore,
        truncated: rows.length >= MAX_ROWS,
      },
      symbols: Array.from(new Set(rows.map((row) => row.symbol).filter(Boolean))).sort(),
      summary: aggregateTrades(rows),
      pairs: computePairMetrics(rows),
      exitReasons: exitReasonBreakdown(rows).map((bucket) => ({ ...bucket, label: exitReasonLabel(bucket.reason) })),
    });
  } catch (error) {
    console.error("trade history failed:", error);
    return res.status(500).json({ error: error?.message || "failed to load trade history" });
  }
}
