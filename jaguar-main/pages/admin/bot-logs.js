import { useEffect, useMemo, useState } from "react";
import { createPagesServerClient } from "@supabase/auth-helpers-nextjs";
import { getSupabaseClient } from "../../lib/supabaseClient";
import { PRICING_TIERS } from "../../lib/pricing-config";
import FeedbackMessage from "../../components/FeedbackMessage";

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
  const [sendingSignal, setSendingSignal] = useState(false);
  const [signalStatus, setSignalStatus] = useState("");
  const [signalGate, setSignalGate] = useState({ paused: false, resume_at: "", message: "" });
  const [signalGateActive, setSignalGateActive] = useState(false);
  const [signalGateSaving, setSignalGateSaving] = useState(false);
  const [signalGateStatus, setSignalGateStatus] = useState("");
  const [signalDraft, setSignalDraft] = useState({
    symbol: "",
    direction: "BUY",
    entryPrice: "",
    stopLoss: "",
    takeProfit: "",
    confidence: "",
    timeframe: "",
    note: "",
    executeMt5: false,
    targetPlans: ["premium", "vip", "pro"],
  });

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

  const toDatetimeLocal = (value) => {
    if (!value) return "";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "";
    const offset = date.getTimezoneOffset();
    return new Date(date.getTime() - offset * 60 * 1000).toISOString().slice(0, 16);
  };

  const fromDatetimeLocal = (value) => {
    if (!value) return null;
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? null : date.toISOString();
  };

  const loadSignalGate = async () => {
    const response = await fetch("/api/admin/signal-gate", { cache: "no-store" });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Unable to load signal pause status.");
    setSignalGate({
      paused: Boolean(data.gate?.paused),
      resume_at: toDatetimeLocal(data.gate?.resume_at),
      message: data.gate?.message || "",
    });
    setSignalGateActive(Boolean(data.active));
    if (data.missingTable) setSignalGateStatus("Run jaguar-main/sql/2026-07-02_signal_delivery.sql in Supabase to enable signal pause.");
  };

  useEffect(() => {
    loadSignalGate().catch((error) => setSignalGateStatus(error.message || "Unable to load signal pause status."));
  }, []);

  const saveSignalGate = async (event) => {
    event.preventDefault();
    setSignalGateSaving(true);
    setSignalGateStatus("");
    try {
      const response = await fetch("/api/admin/signal-gate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          paused: signalGate.paused,
          resumeAt: fromDatetimeLocal(signalGate.resume_at),
          message: signalGate.message,
        }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Unable to save signal pause status.");
      setSignalGate({
        paused: Boolean(data.gate?.paused),
        resume_at: toDatetimeLocal(data.gate?.resume_at),
        message: data.gate?.message || "",
      });
      setSignalGateActive(Boolean(data.active));
      setSignalGateStatus(data.active ? "Bot signal delivery is paused. No signal emails or dashboard alerts will be sent." : "Bot signal delivery is active.");
    } catch (error) {
      setSignalGateStatus(error.message || "Unable to save signal pause status.");
    } finally {
      setSignalGateSaving(false);
    }
  };

  const toggleSignalPlan = (plan) => {
    setSignalDraft((current) => {
      const exists = current.targetPlans.includes(plan);
      const targetPlans = exists
        ? current.targetPlans.filter((item) => item !== plan)
        : [...current.targetPlans, plan];
      return { ...current, targetPlans };
    });
  };

  const sendSignal = async (event) => {
    event.preventDefault();
    setSendingSignal(true);
    setSignalStatus("");
    try {
      const response = await fetch("/api/admin/signals/deliver", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(signalDraft),
      });
      const data = await response.json();
      if (!response.ok) {
        if (data.paused) setSignalGateActive(true);
        throw new Error(data.error || "Unable to deliver signal.");
      }
      const mt5Text = data.mt5Execution?.attempted
        ? data.mt5Execution.ok ? " MT5 execution forwarded." : ` MT5 execution failed: ${data.mt5Execution.reason || "bot unavailable"}.`
        : "";
      setSignalStatus(`Signal delivered. Audience ${data.audience}; ${data.emailed} email${data.emailed === 1 ? "" : "s"} sent; ${data.notified} dashboard alert${data.notified === 1 ? "" : "s"} created; ${data.skippedQuota} skipped by daily quota.${mt5Text}`);
      setSignalDraft((current) => ({ ...current, symbol: "", entryPrice: "", stopLoss: "", takeProfit: "", confidence: "", note: "" }));
      const refreshed = await fetch("/api/admin/bot-logs?limit=200&signalLimit=80");
      const refreshedData = await refreshed.json();
      setSignals(refreshedData.signals || []);
      setLogs(refreshedData.logs || []);
    } catch (error) {
      setSignalStatus(error.message || "Unable to deliver signal.");
    } finally {
      setSendingSignal(false);
    }
  };

  if (loading) return <main className="container mx-auto p-4 sm:p-6">Loading...</main>;

  return (
    <main className="container mx-auto p-4 sm:p-6">
      <h1 className="text-2xl font-bold mb-4">Bot Logs</h1>
      <section className={`rounded-lg p-4 mb-6 border ${signalGateActive ? "border-red-300/30 bg-red-500/10" : "border-emerald-300/20 bg-emerald-500/10"}`}>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="text-xs uppercase tracking-widest text-emerald-200">Bot Signal Control</div>
            <h2 className="text-lg font-semibold">Pause signal delivery</h2>
            <p className="text-sm text-gray-300">When paused, manual dashboard signals and bot API signals are saved from being sent. No email or dashboard alert is delivered.</p>
          </div>
          <span className={`rounded-full px-3 py-1 text-xs font-bold ${signalGateActive ? "bg-red-500/20 text-red-100" : "bg-emerald-500/20 text-emerald-100"}`}>
            {signalGateActive ? "Paused" : "Active"}
          </span>
        </div>
        <form onSubmit={saveSignalGate} className="mt-4 grid gap-3 lg:grid-cols-[1fr_1fr_auto]">
          <label className="flex items-start gap-3 rounded-xl border border-white/10 bg-black/20 p-3 text-sm text-gray-200 lg:col-span-3">
            <input
              type="checkbox"
              checked={signalGate.paused}
              onChange={(event) => setSignalGate((current) => ({ ...current, paused: event.target.checked }))}
              className="mt-1"
            />
            <span>
              <span className="block font-semibold text-white">Pause all bot signal sending</span>
              <span className="text-gray-300">Use this when you do not want any plan or user to receive signal emails/screenshots yet.</span>
            </span>
          </label>
          <input
            type="datetime-local"
            value={signalGate.resume_at}
            onChange={(event) => setSignalGate((current) => ({ ...current, resume_at: event.target.value }))}
            className="rounded bg-black/40 p-2 text-sm"
          />
          <input
            value={signalGate.message}
            onChange={(event) => setSignalGate((current) => ({ ...current, message: event.target.value }))}
            placeholder="Pause message"
            className="rounded bg-black/40 p-2 text-sm"
          />
          <button disabled={signalGateSaving} className="rounded bg-amber-500 px-4 py-2 text-sm font-semibold text-black disabled:opacity-60">
            {signalGateSaving ? "Saving..." : signalGate.paused ? "Save pause" : "Resume signals"}
          </button>
        </form>
        <FeedbackMessage message={signalGateStatus} type={/unable|failed|missing|run/i.test(signalGateStatus) ? "error" : "success"} />
      </section>
      <section className="bg-white/5 rounded-lg p-4 mb-6">
        <div className="mb-4">
          <div className="text-xs uppercase tracking-widest text-emerald-200">Signal Delivery</div>
          <h2 className="text-lg font-semibold">Send branded signal image by tier</h2>
          <p className="text-sm text-gray-400">This saves the signal, generates a KINGSBALFX image, and sends it only to users inside their tier daily quota.</p>
        </div>
        <form onSubmit={sendSignal} className="grid gap-3 lg:grid-cols-6">
          <input value={signalDraft.symbol} onChange={(e) => setSignalDraft((current) => ({ ...current, symbol: e.target.value }))} required placeholder="Symbol e.g. XAUUSD" className="rounded bg-black/40 p-2 text-sm lg:col-span-1" />
          <select value={signalDraft.direction} onChange={(e) => setSignalDraft((current) => ({ ...current, direction: e.target.value }))} className="rounded bg-black/40 p-2 text-sm">
            <option value="BUY">BUY</option>
            <option value="SELL">SELL</option>
          </select>
          <input value={signalDraft.entryPrice} onChange={(e) => setSignalDraft((current) => ({ ...current, entryPrice: e.target.value }))} placeholder="Entry" className="rounded bg-black/40 p-2 text-sm" />
          <input value={signalDraft.stopLoss} onChange={(e) => setSignalDraft((current) => ({ ...current, stopLoss: e.target.value }))} placeholder="Stop loss" className="rounded bg-black/40 p-2 text-sm" />
          <input value={signalDraft.takeProfit} onChange={(e) => setSignalDraft((current) => ({ ...current, takeProfit: e.target.value }))} placeholder="Take profit" className="rounded bg-black/40 p-2 text-sm" />
          <input value={signalDraft.confidence} onChange={(e) => setSignalDraft((current) => ({ ...current, confidence: e.target.value }))} placeholder="Confidence %" className="rounded bg-black/40 p-2 text-sm" />
          <input value={signalDraft.timeframe} onChange={(e) => setSignalDraft((current) => ({ ...current, timeframe: e.target.value }))} placeholder="Timeframe e.g. M15" className="rounded bg-black/40 p-2 text-sm lg:col-span-1" />
          <input value={signalDraft.note} onChange={(e) => setSignalDraft((current) => ({ ...current, note: e.target.value }))} placeholder="Signal note" className="rounded bg-black/40 p-2 text-sm lg:col-span-3" />
          <label className="flex items-center gap-2 rounded bg-black/30 p-2 text-xs text-gray-200">
            <input
              type="checkbox"
              checked={signalDraft.executeMt5}
              onChange={(e) => setSignalDraft((current) => ({ ...current, executeMt5: e.target.checked }))}
            />
            Execute on MT5 bot
          </label>
          <div className="flex flex-wrap gap-2 rounded bg-black/30 p-2 lg:col-span-1">
            {Object.values(PRICING_TIERS).filter((tier) => tier.features?.signals).map((tier) => (
              <label key={tier.id} className="flex items-center gap-1 rounded bg-white/5 px-2 py-1 text-xs">
                <input type="checkbox" checked={signalDraft.targetPlans.includes(tier.id)} onChange={() => toggleSignalPlan(tier.id)} />
                {tier.displayName}
              </label>
            ))}
          </div>
          <button disabled={sendingSignal || signalDraft.targetPlans.length === 0 || signalGateActive} className="rounded bg-emerald-600 px-4 py-2 text-sm font-semibold disabled:opacity-60 lg:col-span-6">
            {signalGateActive ? "Signals paused" : sendingSignal ? "Sending signal..." : "Send signal to selected tiers"}
          </button>
        </form>
        <FeedbackMessage message={signalStatus} type={/unable|failed|error|not installed/i.test(signalStatus) ? "error" : "success"} />
      </section>
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
