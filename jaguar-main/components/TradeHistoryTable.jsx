import { useCallback, useEffect, useMemo, useState } from "react";
import FeedbackMessage from "./FeedbackMessage";
import PairPerformanceBreakdown, { formatMoney, formatNumber } from "./PairPerformanceBreakdown";

const EXIT_OPTIONS = [
  { value: "", label: "All exits" },
  { value: "TP", label: "Take profit" },
  { value: "SL", label: "Stop loss" },
  { value: "MANUAL", label: "Manual" },
  { value: "EA", label: "EA / Bot" },
  { value: "STOP_OUT", label: "Stop out" },
  { value: "ROLLOVER", label: "Rollover" },
  { value: "OTHER", label: "Other" },
];

const SORT_OPTIONS = [
  { value: "close_time", label: "Close time" },
  { value: "net_pnl", label: "Net P&L" },
  { value: "pips", label: "Pips" },
  { value: "volume", label: "Volume" },
  { value: "symbol", label: "Symbol" },
];

export function pnlClass(value) {
  const numeric = Number(value || 0);
  if (numeric > 0) return "text-emerald-200";
  if (numeric < 0) return "text-red-200";
  return "text-gray-300";
}

export function durationLabel(seconds) {
  const total = Number(seconds);
  if (!Number.isFinite(total) || total <= 0) return "-";
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  if (hours >= 24) return `${Math.floor(hours / 24)}d ${hours % 24}h`;
  if (hours > 0) return `${hours}h ${minutes}m`;
  return `${minutes}m`;
}

/**
 * Closed-trade history with summary cards, filters, pagination, per-pair and
 * per-exit-reason breakdowns. Data source: /api/user/trade-history.
 */
export default function TradeHistoryTable({ admin = false, currency = "USD", initialPeriod = "all", pageSize = 25 }) {
  const [filters, setFilters] = useState({
    period: initialPeriod,
    symbol: "",
    side: "",
    exitReason: "",
    sortBy: "close_time",
    sortDir: "desc",
    page: 1,
    pageSize,
    scope: admin ? "all" : "own",
  });
  const [state, setState] = useState({
    loading: true,
    error: "",
    setupRequired: false,
    trades: [],
    pagination: null,
    summary: null,
    pairs: [],
    exitReasons: [],
    periods: [],
    symbols: [],
  });

  const query = useMemo(() => {
    const params = new URLSearchParams();
    params.set("period", filters.period || "all");
    params.set("sortBy", filters.sortBy);
    params.set("sortDir", filters.sortDir);
    params.set("page", String(filters.page || 1));
    params.set("pageSize", String(filters.pageSize || pageSize));
    if (filters.symbol) params.set("symbol", filters.symbol);
    if (filters.side) params.set("side", filters.side);
    if (filters.exitReason) params.set("exitReason", filters.exitReason);
    if (filters.scope === "all") params.set("scope", "all");
    return params.toString();
  }, [filters, pageSize]);

  const load = useCallback(async () => {
    setState((prev) => ({ ...prev, loading: true, error: "" }));
    try {
      const res = await fetch(`/api/user/trade-history?${query}`);
      const data = await res.json();
      if (!res.ok) throw new Error(data?.error || "Failed to load trade history.");
      setState({
        loading: false,
        error: "",
        setupRequired: Boolean(data.setupRequired),
        trades: data.trades || [],
        pagination: data.pagination || null,
        summary: data.summary || null,
        pairs: data.pairs || [],
        exitReasons: data.exitReasons || [],
        periods: data.periods || [],
        symbols: data.symbols || [],
      });
    } catch (err) {
      setState((prev) => ({ ...prev, loading: false, error: err.message || "Failed to load trade history." }));
    }
  }, [query]);

  useEffect(() => {
    load();
  }, [load]);

  const update = (patch) => setFilters((prev) => ({ ...prev, page: 1, ...patch }));
  const summary = state.summary || {};
  const pagination = state.pagination || { page: 1, totalPages: 1 };

  return (
    <div className="space-y-4">
      <section className="glass-panel rounded-lg p-4">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <div className="text-xs text-emerald-200">{admin ? "Platform Trade History" : "My Trade History"}</div>
            <h3 className="text-lg font-semibold text-white">Closed Positions</h3>
            <p className="text-sm text-gray-400">Every synced close, with the exit reason MT5 reported.</p>
          </div>
          <button
            type="button"
            onClick={load}
            className="rounded-md border border-white/10 px-3 py-2 text-xs text-gray-200 hover:bg-white/10"
          >
            Refresh
          </button>
        </div>

        <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <label className="text-xs text-gray-400">
            Period
            <select
              value={filters.period}
              onChange={(event) => update({ period: event.target.value })}
              className="mt-1 w-full rounded-md border border-white/10 bg-black/40 px-2 py-2 text-sm text-white"
            >
              <option value="all">All time</option>
              {state.periods.map((period) => (
                <option key={period.value} value={period.value}>
                  {period.label}
                </option>
              ))}
            </select>
          </label>
          <label className="text-xs text-gray-400">
            Symbol
            <select
              value={filters.symbol}
              onChange={(event) => update({ symbol: event.target.value })}
              className="mt-1 w-full rounded-md border border-white/10 bg-black/40 px-2 py-2 text-sm text-white"
            >
              <option value="">All pairs</option>
              {state.symbols.map((symbol) => (
                <option key={symbol} value={symbol}>
                  {symbol}
                </option>
              ))}
            </select>
          </label>
          <label className="text-xs text-gray-400">
            Side
            <select
              value={filters.side}
              onChange={(event) => update({ side: event.target.value })}
              className="mt-1 w-full rounded-md border border-white/10 bg-black/40 px-2 py-2 text-sm text-white"
            >
              <option value="">Both</option>
              <option value="buy">Buy</option>
              <option value="sell">Sell</option>
            </select>
          </label>
          <label className="text-xs text-gray-400">
            Exit reason
            <select
              value={filters.exitReason}
              onChange={(event) => update({ exitReason: event.target.value })}
              className="mt-1 w-full rounded-md border border-white/10 bg-black/40 px-2 py-2 text-sm text-white"
            >
              {EXIT_OPTIONS.map((option) => (
                <option key={option.value || "all"} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
        </div>

        <div className="mt-3 flex flex-wrap items-center gap-3 text-xs text-gray-400">
          <label className="flex items-center gap-2">
            Sort
            <select
              value={filters.sortBy}
              onChange={(event) => update({ sortBy: event.target.value, sortDir: filters.sortDir })}
              className="rounded-md border border-white/10 bg-black/40 px-2 py-1 text-xs text-white"
            >
              {SORT_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <button
            type="button"
            onClick={() => setFilters((prev) => ({ ...prev, sortDir: prev.sortDir === "desc" ? "asc" : "desc" }))}
            className="rounded-md border border-white/10 px-2 py-1 hover:bg-white/10"
          >
            {filters.sortDir === "desc" ? "Descending" : "Ascending"}
          </button>
          {state.setupRequired && (
            <span className="text-amber-200">Run the MT5 sync migration to store trade history.</span>
          )}
        </div>

        <FeedbackMessage message={state.error} type="error" />
      </section>

      <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <div className="glass-panel rounded-lg p-4">
          <div className="text-xs text-gray-400">Net P&L</div>
          <div className={`text-2xl font-semibold ${pnlClass(summary.netPnl)}`}>
            {formatMoney(summary.netPnl || 0, currency)}
          </div>
          <div className="mt-1 text-xs text-gray-400">
            {summary.trades || 0} trades · {summary.wins || 0}W / {summary.losses || 0}L / {summary.breakeven || 0}BE
          </div>
        </div>
        <div className="glass-panel rounded-lg p-4">
          <div className="text-xs text-gray-400">Win rate</div>
          <div className="text-2xl font-semibold text-white">{formatNumber(summary.winRate, 2)}%</div>
          <div className="mt-1 text-xs text-gray-400">Avg trade {formatMoney(summary.avgTrade || 0, currency)}</div>
        </div>
        <div className="glass-panel rounded-lg p-4">
          <div className="text-xs text-gray-400">Profit factor</div>
          <div className="text-2xl font-semibold text-white">
            {summary.profitFactor === null || summary.profitFactor === undefined
              ? "∞"
              : formatNumber(summary.profitFactor, 2)}
          </div>
          <div className="mt-1 text-xs text-gray-400">
            Gross {formatMoney(summary.grossProfit || 0, currency)} / {formatMoney(summary.grossLoss || 0, currency)}
          </div>
        </div>
        <div className="glass-panel rounded-lg p-4">
          <div className="text-xs text-gray-400">Pips</div>
          <div className={`text-2xl font-semibold ${pnlClass(summary.pips)}`}>{formatNumber(summary.pips, 1)}</div>
          <div className="mt-1 text-xs text-gray-400">
            Volume {formatNumber(summary.volume, 2)} · Avg win {formatMoney(summary.avgWin || 0, currency)}
          </div>
        </div>
      </section>

      <section className="glass-panel rounded-lg p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-lg font-semibold text-white">Closed trades</h3>
          <div className="text-xs text-gray-400">
            {pagination.total || 0} trade(s) · page {pagination.page || 1} of {pagination.totalPages || 1}
            {pagination.truncated ? " · scan capped at 5,000 rows" : ""}
          </div>
        </div>

        {state.loading && <div className="mt-3 text-sm text-gray-400">Loading trade history...</div>}

        {!state.loading && (
          <div className="mt-3 overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead>
                <tr className="text-gray-400">
                  <th className="px-2 py-1">Closed</th>
                  <th className="px-2 py-1">Pair</th>
                  {admin && <th className="px-2 py-1">Account</th>}
                  <th className="px-2 py-1">Side</th>
                  <th className="px-2 py-1 text-right">Volume</th>
                  <th className="px-2 py-1 text-right">Open</th>
                  <th className="px-2 py-1 text-right">Close</th>
                  <th className="px-2 py-1 text-right">Pips</th>
                  <th className="px-2 py-1 text-right">Net P&L</th>
                  <th className="px-2 py-1">Exit</th>
                  <th className="px-2 py-1">Held</th>
                  <th className="px-2 py-1">Note</th>
                </tr>
              </thead>
              <tbody>
                {state.trades.map((trade) => (
                  <tr key={trade.id} className="border-t border-white/5">
                    <td className="px-2 py-2 text-xs text-gray-300">
                      {trade.close_time ? new Date(trade.close_time).toLocaleString() : "-"}
                    </td>
                    <td className="px-2 py-2 font-semibold text-white">{trade.symbol}</td>
                    {admin && <td className="px-2 py-2 text-xs text-gray-400">{trade.account_login || "-"}</td>}
                    <td className="px-2 py-2">
                      <span className={trade.side === "buy" ? "text-emerald-200" : "text-red-200"}>
                        {String(trade.side || "").toUpperCase()}
                      </span>
                    </td>
                    <td className="px-2 py-2 text-right">{formatNumber(trade.volume, 2)}</td>
                    <td className="px-2 py-2 text-right">
                      {trade.open_price === null ? "-" : formatNumber(trade.open_price, 5)}
                    </td>
                    <td className="px-2 py-2 text-right">
                      {trade.close_price === null ? "-" : formatNumber(trade.close_price, 5)}
                    </td>
                    <td className={`px-2 py-2 text-right ${pnlClass(trade.pips)}`}>
                      {trade.pips === null ? "-" : formatNumber(trade.pips, 1)}
                    </td>
                    <td className={`px-2 py-2 text-right font-semibold ${pnlClass(trade.net_pnl)}`}>
                      {formatMoney(trade.net_pnl || 0, currency)}
                    </td>
                    <td className="px-2 py-2">
                      <span
                        className="rounded border border-white/10 bg-black/30 px-1.5 py-0.5 text-[11px] text-gray-300"
                        title={`classified from: ${trade.exit_source || "unknown"}`}
                      >
                        {trade.exit_reason || "OTHER"}
                      </span>
                    </td>
                    <td className="px-2 py-2 text-xs text-gray-400">{durationLabel(trade.duration_seconds)}</td>
                    <td
                      className="max-w-[180px] truncate px-2 py-2 text-xs text-gray-400"
                      title={trade.comment || trade.broker_comment || ""}
                    >
                      {trade.comment || trade.broker_comment || "-"}
                    </td>
                  </tr>
                ))}
                {state.trades.length === 0 && (
                  <tr>
                    <td className="px-2 py-3 text-gray-400" colSpan={admin ? 12 : 11}>
                      No closed trades for this filter yet.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}

        {pagination.totalPages > 1 && (
          <div className="mt-3 flex items-center justify-between text-xs text-gray-400">
            <button
              type="button"
              disabled={pagination.page <= 1}
              onClick={() => setFilters((prev) => ({ ...prev, page: Math.max(1, (prev.page || 1) - 1) }))}
              className="rounded-md border border-white/10 px-3 py-1 hover:bg-white/10 disabled:opacity-40"
            >
              Previous
            </button>
            <span>
              Page {pagination.page} of {pagination.totalPages}
            </span>
            <button
              type="button"
              disabled={!pagination.hasMore}
              onClick={() => setFilters((prev) => ({ ...prev, page: (prev.page || 1) + 1 }))}
              className="rounded-md border border-white/10 px-3 py-1 hover:bg-white/10 disabled:opacity-40"
            >
              Next
            </button>
          </div>
        )}
      </section>

      <PairPerformanceBreakdown
        pairs={state.pairs}
        currency={currency}
        title={admin ? "Platform Pair Performance" : "My Pair Performance"}
        subtitle="Net P&L, win rate and exit mix per instrument for the current filter."
      />

      {state.exitReasons.length > 0 && (
        <section className="glass-panel rounded-lg p-4">
          <h3 className="text-lg font-semibold text-white">Exit reason mix</h3>
          <p className="text-sm text-gray-400">
            How positions were closed, derived from the MT5 deal reason and broker comment.
          </p>
          <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {state.exitReasons.map((bucket) => (
              <div key={bucket.reason} className="rounded-md border border-white/10 bg-black/30 p-3">
                <div className="text-xs text-gray-400">{bucket.label || bucket.reason}</div>
                <div className="text-xl font-semibold text-white">{bucket.trades}</div>
                <div className="mt-1 text-xs text-gray-400">
                  Win {formatNumber(bucket.winRate, 1)}% · Net {formatMoney(bucket.netPnl, currency)}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
