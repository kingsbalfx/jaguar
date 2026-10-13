import { authenticateRequest } from "../../../lib/api-auth";
import { computePairMetrics, listRecentPeriods, normalizePeriodFilter, periodLabel } from "../../../lib/mt5-metrics";

const ANALYTICS_COLUMNS =
  "link_id,user_id,account_login,period,symbol,trades,wins,losses,breakeven,win_rate,volume,gross_profit,gross_loss,net_pnl,profit_factor,pips,avg_win,avg_loss,best_trade,worst_trade,tp_trades,sl_trades,manual_trades,ea_trades,stop_out_trades,other_trades,first_trade_at,last_trade_at,updated_at";
const TRADE_COLUMNS = "link_id,symbol,volume,pips,net_pnl,exit_reason,close_time,period";
const MAX_FALLBACK_TRADES = 5000;

function isMissingRelation(error) {
  const code = String(error?.code || "");
  return code === "42P01" || code === "PGRST205" || /does not exist/i.test(String(error?.message || ""));
}

function num(value, fallback = 0) {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : fallback;
}

/** Normalise a stored pair_analytics row and a computed metric row into one shape. */
function toPairRow(row = {}) {
  const exitReasons = {
    TP: num(row.tp_trades),
    SL: num(row.sl_trades),
    MANUAL: num(row.manual_trades),
    EA: num(row.ea_trades),
    STOP_OUT: num(row.stop_out_trades),
    OTHER: num(row.other_trades),
  };
  return {
    symbol: row.symbol || "UNKNOWN",
    period: row.period || "all",
    linkId: row.link_id || null,
    trades: num(row.trades),
    wins: num(row.wins),
    losses: num(row.losses),
    breakeven: num(row.breakeven),
    winRate: num(row.win_rate ?? row.winRate),
    volume: num(row.volume),
    grossProfit: num(row.gross_profit ?? row.grossProfit),
    grossLoss: num(row.gross_loss ?? row.grossLoss),
    netPnl: num(row.net_pnl ?? row.netPnl),
    profitFactor:
      row.profit_factor === null || row.profit_factor === undefined
        ? row.profitFactor ?? null
        : num(row.profit_factor),
    pips: num(row.pips),
    avgWin: num(row.avg_win ?? row.avgWin),
    avgLoss: num(row.avg_loss ?? row.avgLoss),
    bestTrade: num(row.best_trade ?? row.bestTrade),
    worstTrade: num(row.worst_trade ?? row.worstTrade),
    exitReasons,
    exitReasonCounts: exitReasons,
    sharePct: row.sharePct === undefined ? null : row.sharePct,
    netContributionPct: row.netContributionPct === undefined ? null : row.netContributionPct,
    firstTradeAt: row.first_trade_at || row.firstTradeAt || null,
    lastTradeAt: row.last_trade_at || row.lastTradeAt || null,
    updatedAt: row.updated_at || null,
  };
}

function sumRows(rows = []) {
  const totals = { trades: 0, wins: 0, losses: 0, breakeven: 0, volume: 0, netPnl: 0, pips: 0 };
  for (const row of rows) {
    totals.trades += num(row.trades);
    totals.wins += num(row.wins);
    totals.losses += num(row.losses);
    totals.breakeven += num(row.breakeven);
    totals.volume += num(row.volume);
    totals.netPnl += num(row.netPnl);
    totals.pips += num(row.pips);
  }
  totals.volume = Number(totals.volume.toFixed(4));
  totals.netPnl = Number(totals.netPnl.toFixed(2));
  totals.pips = Number(totals.pips.toFixed(2));
  totals.winRate = totals.trades ? Number(((totals.wins / totals.trades) * 100).toFixed(2)) : 0;
  return totals;
}

/**
 * Per-pair performance for the signed-in trader. Reads the pre-aggregated
 * pair_analytics table and falls back to computing from trade_history when the
 * analytics rows have not been built yet.
 */
export default async function handler(req, res) {
  if (req.method !== "GET") return res.status(405).json({ error: "Method not allowed" });

  const auth = await authenticateRequest(req, res);
  if (!auth.ok) return res.status(auth.status).json({ error: auth.error });
  const { supabaseAdmin } = auth;

  try {
    const scopeAll = auth.isAdmin && String(req.query.scope || "").toLowerCase() === "all";
    const period = normalizePeriodFilter(req.query.period);
    const linkId = String(req.query.linkId || "").trim();

    let query = supabaseAdmin
      .from("pair_analytics")
      .select(ANALYTICS_COLUMNS)
      .order("net_pnl", { ascending: false })
      .limit(500);
    if (!scopeAll) query = query.eq("user_id", auth.session.user.id);
    if (period !== "all") query = query.eq("period", period);
    if (linkId) query = query.eq("link_id", linkId);

    const { data, error } = await query;
    if (error && !isMissingRelation(error)) return res.status(500).json({ error: error.message });

    let pairs = (error ? [] : data || []).map(toPairRow);
    let computed = false;

    if (!pairs.length && !error) {
      let tradeQuery = supabaseAdmin
        .from("trade_history")
        .select(TRADE_COLUMNS)
        .order("close_time", { ascending: false })
        .limit(MAX_FALLBACK_TRADES);
      if (!scopeAll) tradeQuery = tradeQuery.eq("user_id", auth.session.user.id);
      if (period !== "all") tradeQuery = tradeQuery.eq("period", period);
      if (linkId) tradeQuery = tradeQuery.eq("link_id", linkId);
      const tradesResult = await tradeQuery;
      if (tradesResult.error && !isMissingRelation(tradesResult.error)) {
        return res.status(500).json({ error: tradesResult.error.message });
      }
      const trades = tradesResult.error ? [] : tradesResult.data || [];
      pairs = computePairMetrics(trades).map((row) => toPairRow({ ...row, period }));
      computed = pairs.length > 0;
    }

    return res.status(200).json({
      ok: true,
      scope: scopeAll ? "all" : "own",
      period,
      periodLabel: periodLabel(period),
      periods: listRecentPeriods(12).map((value) => ({ value, label: periodLabel(value) })),
      computed,
      setupRequired: Boolean(error),
      pairs,
      totals: sumRows(pairs),
      bestPair: pairs[0] || null,
      worstPair: pairs.length ? pairs[pairs.length - 1] : null,
    });
  } catch (err) {
    console.error("pair performance failed:", err);
    return res.status(500).json({ error: err?.message || "failed to load pair performance" });
  }
}
