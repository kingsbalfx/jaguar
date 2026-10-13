const EXIT_LABELS = {
  TP: "TP",
  SL: "SL",
  MANUAL: "Manual",
  EA: "EA",
  STOP_OUT: "Stop out",
  ROLLOVER: "Rollover",
  OTHER: "Other",
};

export function formatMoney(value, currency = "USD") {
  const numeric = Number(value || 0);
  try {
    return new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: currency || "USD",
      maximumFractionDigits: 2,
    }).format(numeric);
  } catch {
    return `${numeric.toFixed(2)} ${currency || ""}`.trim();
  }
}

export function formatNumber(value, digits = 2) {
  const numeric = Number(value || 0);
  if (!Number.isFinite(numeric)) return "-";
  return numeric.toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

function pnlClass(value) {
  const numeric = Number(value || 0);
  if (numeric > 0) return "text-emerald-200";
  if (numeric < 0) return "text-red-200";
  return "text-gray-300";
}

function factorLabel(value) {
  if (value === null || value === undefined) return "∞";
  return formatNumber(value, 2);
}

/**
 * Per-symbol performance table with an optional exit-reason mix per pair.
 * Presentational only: pass rows from /api/user/pair-performance or /api/admin/mt5-performance.
 */
export default function PairPerformanceBreakdown({
  pairs = [],
  currency = "USD",
  title = "Pair Performance",
  subtitle = "Net P&L, win rate and exit mix per instrument.",
  showExitMix = true,
  emptyMessage = "No closed trades for this filter yet.",
}) {
  const maxAbs = pairs.reduce((max, row) => Math.max(max, Math.abs(Number(row.netPnl || 0))), 0);

  return (
    <section className="glass-panel rounded-lg p-4">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h3 className="text-lg font-semibold text-white">{title}</h3>
          <p className="text-sm text-gray-400">{subtitle}</p>
        </div>
        <div className="text-xs text-gray-400">{pairs.length} instrument{pairs.length === 1 ? "" : "s"}</div>
      </div>

      {pairs.length === 0 ? (
        <p className="mt-3 text-sm text-gray-400">{emptyMessage}</p>
      ) : (
        <div className="mt-4 overflow-x-auto">
          <table className="min-w-full text-left text-sm">
            <thead>
              <tr className="text-gray-400">
                <th className="px-2 py-1">Pair</th>
                <th className="px-2 py-1 text-right">Trades</th>
                <th className="px-2 py-1 text-right">Win %</th>
                <th className="px-2 py-1 text-right">Net P&L</th>
                <th className="px-2 py-1 text-right">PF</th>
                <th className="px-2 py-1 text-right">Pips</th>
                <th className="px-2 py-1 text-right">Volume</th>
                <th className="px-2 py-1 text-right">Best</th>
                <th className="px-2 py-1 text-right">Worst</th>
                {showExitMix && <th className="px-2 py-1">Exit mix</th>}
              </tr>
            </thead>
            <tbody>
              {pairs.map((row) => {
                const net = Number(row.netPnl || 0);
                const width = maxAbs > 0 ? Math.max(2, Math.round((Math.abs(net) / maxAbs) * 100)) : 0;
                return (
                  <tr key={`${row.symbol}-${row.period || "all"}`} className="border-t border-white/5 align-top">
                    <td className="px-2 py-2">
                      <div className="font-semibold text-white">{row.symbol}</div>
                      <div className="mt-1 h-1 w-24 rounded bg-white/10">
                        <div
                          className={`h-1 rounded ${net >= 0 ? "bg-emerald-400/70" : "bg-red-400/70"}`}
                          style={{ width: `${width}%` }}
                        />
                      </div>
                    </td>
                    <td className="px-2 py-2 text-right">{row.trades || 0}</td>
                    <td className="px-2 py-2 text-right">{formatNumber(row.winRate ?? row.win_rate, 2)}</td>
                    <td className={`px-2 py-2 text-right font-semibold ${pnlClass(net)}`}>{formatMoney(net, currency)}</td>
                    <td className="px-2 py-2 text-right">{factorLabel(row.profitFactor)}</td>
                    <td className={`px-2 py-2 text-right ${pnlClass(row.pips)}`}>{formatNumber(row.pips, 1)}</td>
                    <td className="px-2 py-2 text-right">{formatNumber(row.volume, 2)}</td>
                    <td className="px-2 py-2 text-right text-emerald-200">{formatMoney(row.bestTrade, currency)}</td>
                    <td className="px-2 py-2 text-right text-red-200">{formatMoney(row.worstTrade, currency)}</td>
                    {showExitMix && (
                      <td className="px-2 py-2">
                        <div className="flex flex-wrap gap-1 text-[11px]">
                          {Object.entries(row.exitReasons || {})
                            .filter(([, count]) => Number(count) > 0)
                            .map(([reason, count]) => (
                              <span key={reason} className="rounded border border-white/10 bg-black/30 px-1.5 py-0.5 text-gray-300">
                                {EXIT_LABELS[reason] || reason}: {count}
                              </span>
                            ))}
                          {Object.values(row.exitReasons || {}).every((count) => !Number(count)) && (
                            <span className="text-gray-500">-</span>
                          )}
                        </div>
                      </td>
                    )}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
