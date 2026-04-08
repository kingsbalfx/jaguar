import { useEffect, useMemo, useState } from "react";
import { createPagesServerClient } from "@supabase/auth-helpers-nextjs";
import { getSupabaseClient } from "../../lib/supabaseClient";

export const getServerSideProps = async (ctx) => {
  try {
    const supabase = createPagesServerClient(ctx);
    const {
      data: { session },
    } = await supabase.auth.getSession();

    if (!session || !session.user) return { redirect: { destination: "/login", permanent: false } };

    const supabaseAdmin = getSupabaseClient({ server: true });
    const userId = session.user.id;
    const { data: profile } = await supabaseAdmin.from("profiles").select("role").eq("id", userId).maybeSingle();
    const role = (profile?.role || "user").toLowerCase();
    if (role !== "admin") return { redirect: { destination: "/", permanent: false } };

    return { props: {} };
  } catch (e) {
    console.error(e);
    return { props: {} };
  }
};

export default function BotLogs() {
  const [logs, setLogs] = useState([]);
  const [signals, setSignals] = useState([]);
  const [signalsError, setSignalsError] = useState("");
  const [loading, setLoading] = useState(true);

  const edgeView = useMemo(() => {
    const blocked = logs.filter((log) =>
      ["profitability_guard_block", "signal_quota_blocked", "hybrid_trade_reject"].includes(log.event)
    );
    const pendingSignals = signals.filter((signal) => signal.status === "pending").length;
    const avgConfidence =
      signals.length > 0
        ? signals.reduce((sum, signal) => sum + Number(signal.confidence || 0), 0) / signals.length
        : 0;
    const symbolCounts = signals.reduce((acc, signal) => {
      const symbol = signal.symbol || "UNKNOWN";
      acc[symbol] = (acc[symbol] || 0) + 1;
      return acc;
    }, {});
    const blockReasons = blocked.reduce((acc, log) => {
      const reason = log.payload?.reason || log.payload?.message || log.event;
      acc[reason] = (acc[reason] || 0) + 1;
      return acc;
    }, {});
    const topSymbols = Object.entries(symbolCounts)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5);
    const topBlocks = Object.entries(blockReasons)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5);

    return {
      blockedCount: blocked.length,
      pendingSignals,
      avgConfidence,
      topSymbols,
      topBlocks,
    };
  }, [logs, signals]);

  useEffect(() => {
    (async () => {
      try {
        const resp = await fetch("/api/admin/bot-logs?limit=200&signalLimit=80");
        const data = await resp.json();
        setLogs(data.logs || []);
        setSignals(data.signals || []);
        setSignalsError(data.signalsError || "");
      } catch (e) {
        console.error("Failed to fetch logs:", e);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  if (loading) return <main className="container mx-auto p-6">Loading...</main>;

  return (
    <main className="container mx-auto p-6">
      <h1 className="text-2xl font-bold mb-4">Bot Logs</h1>
      <section id="market-edge" className="bg-white/5 rounded-lg p-4 mb-6">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
          <div>
            <h2 className="text-lg font-semibold">Market Edge View</h2>
            <div className="text-sm text-gray-400">
              Focus on blocked weak setups, active signal pressure, and symbol concentration.
            </div>
          </div>
          <div className="text-xs text-emerald-200">Profitability guard ready</div>
        </div>
        <div className="grid gap-3 md:grid-cols-4">
          <div className="rounded-md border border-white/10 bg-black/30 p-3">
            <div className="text-xs text-gray-400">Guard blocks</div>
            <div className="text-2xl font-semibold text-red-200">{edgeView.blockedCount}</div>
          </div>
          <div className="rounded-md border border-white/10 bg-black/30 p-3">
            <div className="text-xs text-gray-400">Pending signals</div>
            <div className="text-2xl font-semibold text-yellow-200">{edgeView.pendingSignals}</div>
          </div>
          <div className="rounded-md border border-white/10 bg-black/30 p-3">
            <div className="text-xs text-gray-400">Avg confidence</div>
            <div className="text-2xl font-semibold text-emerald-200">
              {edgeView.avgConfidence.toFixed(1)}
            </div>
          </div>
          <div className="rounded-md border border-white/10 bg-black/30 p-3">
            <div className="text-xs text-gray-400">Top symbols</div>
            <div className="mt-1 space-y-1 text-xs text-gray-200">
              {edgeView.topSymbols.length === 0 && <div>No signal data.</div>}
              {edgeView.topSymbols.map(([symbol, count]) => (
                <div key={symbol} className="flex justify-between gap-3">
                  <span>{symbol}</span>
                  <span>{count}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
        <div className="mt-4 rounded-md border border-white/10 bg-black/30 p-3">
          <div className="text-xs text-gray-400 mb-2">Top reject reasons</div>
          <div className="grid gap-2 md:grid-cols-2">
            {edgeView.topBlocks.length === 0 && (
              <div className="text-sm text-gray-400">No guard rejects in the latest logs.</div>
            )}
            {edgeView.topBlocks.map(([reason, count]) => (
              <div key={reason} className="flex justify-between gap-4 text-sm text-gray-200">
                <span>{reason}</span>
                <span>{count}</span>
              </div>
            ))}
          </div>
        </div>
      </section>
      <section className="overflow-x-auto bg-white/5 rounded-lg p-4 mb-6">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
          <div>
            <h2 className="text-lg font-semibold">Latest Signals</h2>
            <div className="text-gray-400 text-sm">SL and TP are visible for fast risk review.</div>
          </div>
          <div className="text-gray-400 text-sm">Total signals: {signals.length}</div>
        </div>
        {signalsError && <div className="mb-3 text-sm text-yellow-300">{signalsError}</div>}
        <table className="min-w-full text-left text-sm">
          <thead>
            <tr>
              <th className="px-2 py-1">Symbol</th>
              <th className="px-2 py-1">Side</th>
              <th className="px-2 py-1">Entry</th>
              <th className="px-2 py-1">SL</th>
              <th className="px-2 py-1">TP</th>
              <th className="px-2 py-1">Quality</th>
              <th className="px-2 py-1">Confidence</th>
              <th className="px-2 py-1">Status</th>
              <th className="px-2 py-1">Created</th>
            </tr>
          </thead>
          <tbody>
            {signals.map((signal) => (
              <tr key={signal.id} className="border-t border-white/5">
                <td className="px-2 py-2">{signal.symbol}</td>
                <td className="px-2 py-2 capitalize">{signal.direction}</td>
                <td className="px-2 py-2">{signal.entry_price}</td>
                <td className="px-2 py-2 text-red-200">{signal.stop_loss}</td>
                <td className="px-2 py-2 text-emerald-200">{signal.take_profit}</td>
                <td className="px-2 py-2">{signal.signal_quality}</td>
                <td className="px-2 py-2">{signal.confidence ?? "-"}</td>
                <td className="px-2 py-2">{signal.status}</td>
                <td className="px-2 py-2 text-xs">{new Date(signal.created_at).toLocaleString()}</td>
              </tr>
            ))}
            {signals.length === 0 && (
              <tr>
                <td className="px-2 py-3 text-gray-400" colSpan={9}>
                  No signals found.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </section>
      <div className="overflow-x-auto bg-white/5 rounded-lg p-4">
        <div className="text-gray-400 mb-3">Total logs: {logs.length}</div>
        <table className="min-w-full text-left text-sm">
          <thead>
            <tr>
              <th className="px-2 py-1">Event</th>
              <th className="px-2 py-1">Payload</th>
              <th className="px-2 py-1">Created</th>
            </tr>
          </thead>
          <tbody>
            {logs.map((log, i) => (
              <tr key={i} className="border-t border-white/5">
                <td className="px-2 py-2">{log.event}</td>
                <td className="px-2 py-2 text-xs font-mono">{JSON.stringify(log.payload || {}).substring(0, 100)}...</td>
                <td className="px-2 py-2 text-xs">{new Date(log.created_at).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </main>
  );
}
