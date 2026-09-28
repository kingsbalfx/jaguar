import { useEffect, useState } from "react";
import { createPagesServerClient } from "@supabase/auth-helpers-nextjs";
import { getSupabaseClient } from "../../lib/supabaseClient";
import FeedbackMessage from "../../components/FeedbackMessage";

export const getServerSideProps = async (ctx) => {
  try {
    const supabase = createPagesServerClient(ctx);
    const {
      data: { session },
    } = await supabase.auth.getSession();

    if (!session?.user) return { redirect: { destination: "/login", permanent: false } };

    const supabaseAdmin = getSupabaseClient({ server: true });
    const { data: profile } = await supabaseAdmin
      .from("profiles")
      .select("role")
      .eq("id", session.user.id)
      .maybeSingle();

    if (String(profile?.role || "user").toLowerCase() !== "admin") {
      return { redirect: { destination: "/", permanent: false } };
    }

    return { props: {} };
  } catch (error) {
    console.error("signal health page error:", error);
    return { redirect: { destination: "/login", permanent: false } };
  }
};

const REASON_LABELS = {
  missing_email: "No email on profile",
  role_fallback_disabled: "Role fallback disabled (BOT_SIGNAL_ROLE_FALLBACK=false)",
  muted_by_profile: "Signals muted on the profile (bot_signals_muted)",
  admin_without_paid_plan: "Admin without a paid plan",
  plan_not_targeted: "Plan not in the targeted list",
  unknown_plan: "Unknown plan id",
  plan_has_no_signals: "Plan does not include signals",
  daily_limit_zero: "Daily signal limit is 0",
};

const formatAge = (hours) => {
  if (hours === null || hours === undefined) return "never";
  if (hours < 1) return `${Math.round(hours * 60)} min ago`;
  if (hours < 48) return `${hours} h ago`;
  return `${Math.round(hours / 24)} d ago`;
};

export default function SignalHealth() {
  const [data, setData] = useState(null);
  const [plansInput, setPlansInput] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState({ type: "", message: "" });
  const [draft, setDraft] = useState({ symbol: "EURUSD", direction: "BUY", note: "Admin test signal" });

  const load = async (plans) => {
    setLoading(true);
    try {
      const query = plans ? `?plans=${encodeURIComponent(plans)}` : "";
      const response = await fetch(`/api/admin/signal-health${query}`);
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || "Unable to load signal health");
      setData(payload);
      setPlansInput((payload.targetPlans || []).join(","));
      setFeedback({ type: "", message: "" });
    } catch (error) {
      setFeedback({ type: "error", message: error.message || String(error) });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const toggleGate = async () => {
    if (!data) return;
    setBusy(true);
    try {
      const response = await fetch("/api/admin/signal-gate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ paused: !data.gate?.paused, resumeAt: null, message: "" }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || "Unable to update the pause switch");
      setFeedback({
        type: "success",
        message: payload.active ? "Signal delivery paused." : "Signal delivery resumed.",
      });
      await load(plansInput);
    } catch (error) {
      setFeedback({ type: "error", message: error.message || String(error) });
    } finally {
      setBusy(false);
    }
  };

  const sendTestSignal = async () => {
    setBusy(true);
    try {
      const response = await fetch("/api/admin/signals/deliver", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          symbol: draft.symbol,
          direction: draft.direction,
          note: draft.note,
          targetPlans: (data?.targetPlans || []).join(","),
        }),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || "Unable to send the test signal");
      setFeedback({
        type: "success",
        message: `Signal saved. Audience ${payload.audience ?? 0}, emailed ${payload.emailed ?? 0}, in-app ${payload.notified ?? 0}.`,
      });
      await load(plansInput);
    } catch (error) {
      setFeedback({ type: "error", message: error.message || String(error) });
    } finally {
      setBusy(false);
    }
  };

  const gate = data?.gate || {};

  return (
    <main className="container mx-auto px-4 py-6 sm:px-6 sm:py-8 text-white">
      <h1 className="text-2xl font-bold mb-1">Signal Health &amp; Audience</h1>
      <p className="text-sm text-gray-400 mb-4">
        Explains why the bot&apos;s signals do or do not reach subscribers, and lets you test delivery.
      </p>

      <FeedbackMessage type={feedback.type} message={feedback.message} />

      {(data?.warnings || []).length > 0 && (
        <div className="mt-4 rounded border border-yellow-500/40 bg-yellow-500/10 p-4">
          <div className="text-sm font-semibold mb-2">Attention</div>
          <ul className="list-disc ml-5 space-y-1 text-sm text-yellow-100">
            {(data.warnings || []).map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <input
          value={plansInput}
          onChange={(event) => setPlansInput(event.target.value)}
          className="px-3 py-2 rounded bg-white/10 text-sm w-64"
          placeholder="premium,vip,pro,lifetime"
        />
        <button
          type="button"
          onClick={() => load(plansInput)}
          className="px-4 py-2 rounded bg-indigo-600 text-sm"
          disabled={loading || busy}
        >
          Recalculate audience
        </button>
        <button
          type="button"
          onClick={toggleGate}
          className={`px-4 py-2 rounded text-sm ${gate.paused ? "bg-green-600" : "bg-red-600"}`}
          disabled={busy}
        >
          {gate.paused ? "Resume delivery" : "Pause delivery"}
        </button>
      </div>
      {loading && <div className="mt-4 text-sm text-gray-400">Loading…</div>}

      {data && (
        <SignalHealthBody
          data={data}
          draft={draft}
          setDraft={setDraft}
          busy={busy}
          onSendTest={sendTestSignal}
        />
      )}
    </main>
  );
}

function SignalHealthBody({ data, draft, setDraft, busy, onSendTest }) {
  return (
    <>
      <div className="mt-5 grid grid-cols-1 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        <Stat
          label="Bot API"
          value={data.bot?.reachable ? "reachable" : "offline"}
          tone={data.bot?.reachable ? "good" : "bad"}
        />
        <Stat
          label="Last master signal"
          value={formatAge(data.lastSignalAgeHours)}
          tone={data.lastSignalAgeHours !== null && data.lastSignalAgeHours < 24 ? "good" : "bad"}
        />
        <Stat label="Deliveries today" value={String(data.deliveriesToday || 0)} />
        <Stat label="Signal gate" value={data.gateActive ? "paused" : "open"} tone={data.gateActive ? "bad" : "good"} />
        <Stat
          label="SMTP"
          value={data.smtp?.configured ? data.smtp.provider || "configured" : "not configured"}
          tone={data.smtp?.configured ? "good" : "warn"}
        />
      </div>

      <section className="mt-6">
        <h2 className="text-lg font-semibold mb-2">Send a test signal</h2>
        <div className="flex flex-wrap items-center gap-3">
          <input
            value={draft.symbol}
            onChange={(event) => setDraft({ ...draft, symbol: event.target.value })}
            className="px-3 py-2 rounded bg-white/10 text-sm w-32"
            placeholder="EURUSD"
          />
          <select
            value={draft.direction}
            onChange={(event) => setDraft({ ...draft, direction: event.target.value })}
            className="px-3 py-2 rounded bg-white/10 text-sm"
          >
            <option value="BUY">BUY</option>
            <option value="SELL">SELL</option>
          </select>
          <input
            value={draft.note}
            onChange={(event) => setDraft({ ...draft, note: event.target.value })}
            className="px-3 py-2 rounded bg-white/10 text-sm flex-1 min-w-[12rem]"
            placeholder="note"
          />
          <button type="button" onClick={onSendTest} className="px-4 py-2 rounded bg-green-600 text-sm" disabled={busy}>
            Deliver now
          </button>
        </div>
      </section>

      <AudienceTable data={data} />
      <ExcludedTable data={data} />
      <RecentLists data={data} />
    </>
  );
}

function Stat({ label, value, tone = "neutral" }) {
  const toneClass =
    tone === "good"
      ? "text-green-300"
      : tone === "bad"
        ? "text-red-300"
        : tone === "warn"
          ? "text-yellow-300"
          : "text-white";
  return (
    <div className="rounded border border-white/10 bg-white/5 p-3">
      <div className="text-xs uppercase tracking-wide text-gray-400">{label}</div>
      <div className={`mt-1 text-sm font-semibold ${toneClass}`}>{value}</div>
    </div>
  );
}

function AudienceTable({ data }) {
  return (
    <section className="mt-6">
      <h2 className="text-lg font-semibold mb-2">
        Audience — {(data.audience || []).length} subscriber(s) of {data.counts?.profiles ?? 0} profiles
      </h2>
      <div className="overflow-x-auto rounded border border-white/10">
        <table className="min-w-full text-sm">
          <thead className="bg-white/5 text-left text-gray-300">
            <tr>
              <th className="px-3 py-2">Email</th>
              <th className="px-3 py-2">Plan</th>
              <th className="px-3 py-2">Source</th>
              <th className="px-3 py-2">Signals/day</th>
              <th className="px-3 py-2">Quality</th>
            </tr>
          </thead>
          <tbody>
            {(data.audience || []).map((user) => (
              <tr key={user.id || user.email} className="border-t border-white/5">
                <td className="px-3 py-2">{user.email}</td>
                <td className="px-3 py-2 capitalize">{user.plan}</td>
                <td className="px-3 py-2 text-gray-400">
                  {user.planSource}
                  {user.subscriptionExpired ? " (lapsed subscription)" : ""}
                </td>
                <td className="px-3 py-2">{user.dailyLimit}</td>
                <td className="px-3 py-2 text-gray-400">{user.signalQuality}</td>
              </tr>
            ))}
            {!(data.audience || []).length && (
              <tr>
                <td className="px-3 py-2 text-gray-400" colSpan={5}>
                  Nobody is eligible — check the skipped list below.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function ExcludedTable({ data }) {
  return (
    <section className="mt-6">
      <h2 className="text-lg font-semibold mb-2">Skipped ({(data.excluded || []).length})</h2>
      <div className="text-xs text-gray-400 mb-2">
        {Object.entries(data.excludedSummary?.byReason || {})
          .map(([reason, count]) => `${REASON_LABELS[reason] || reason} ×${count}`)
          .join(" · ") || "none"}
      </div>
      <div className="overflow-x-auto rounded border border-white/10">
        <table className="min-w-full text-sm">
          <thead className="bg-white/5 text-left text-gray-300">
            <tr>
              <th className="px-3 py-2">Email</th>
              <th className="px-3 py-2">Plan</th>
              <th className="px-3 py-2">Source</th>
              <th className="px-3 py-2">Reason</th>
            </tr>
          </thead>
          <tbody>
            {(data.excluded || []).slice(0, 40).map((user) => (
              <tr key={user.id || user.email} className="border-t border-white/5">
                <td className="px-3 py-2">{user.email || "—"}</td>
                <td className="px-3 py-2 capitalize">{user.plan}</td>
                <td className="px-3 py-2 text-gray-400">{user.planSource}</td>
                <td className="px-3 py-2 text-yellow-200">{REASON_LABELS[user.reason] || user.reason}</td>
              </tr>
            ))}
            {!(data.excluded || []).length && (
              <tr>
                <td className="px-3 py-2 text-gray-400" colSpan={4}>
                  No skips recorded.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}




function RecentLists({ data }) {
  return (
    <section className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
      <div>
        <h2 className="text-lg font-semibold mb-2">Recent signals</h2>
        <ul className="text-sm space-y-1">
          {(data.recentSignals || []).map((signal) => (
            <li key={signal.id} className="flex justify-between gap-3 border-b border-white/5 py-1">
              <span>
                {signal.symbol} {signal.direction}
                <span className="text-gray-400"> · {signal.signal_quality}</span>
              </span>
              <span className="text-gray-500">{new Date(signal.created_at).toLocaleString("en-NG")}</span>
            </li>
          ))}
          {!(data.recentSignals || []).length && <li className="text-gray-400">No signals recorded yet.</li>}
        </ul>
      </div>
      <div>
        <h2 className="text-lg font-semibold mb-2">Recent deliveries</h2>
        <ul className="text-sm space-y-1">
          {(data.recentDeliveries || []).map((delivery) => (
            <li key={delivery.id} className="flex justify-between gap-3 border-b border-white/5 py-1">
              <span>
                {delivery.email}
                <span className="text-gray-400"> · {delivery.plan}</span>
              </span>
              <span className="text-gray-500">
                {delivery.status} · {new Date(delivery.delivered_at).toLocaleString("en-NG")}
              </span>
            </li>
          ))}
          {!(data.recentDeliveries || []).length && <li className="text-gray-400">No deliveries recorded yet.</li>}
        </ul>
      </div>
      <div className="lg:col-span-2">
        <h2 className="text-lg font-semibold mb-2">Delivery runs (bot logs)</h2>
        <ul className="text-sm space-y-1">
          {(data.recentDeliveryLogs || []).map((log, index) => (
            <li
              key={`${log.created_at}-${index}`}
              className="flex flex-wrap justify-between gap-3 border-b border-white/5 py-1"
            >
              <span>
                audience {log.payload?.audience ?? 0} · emailed {log.payload?.emailed ?? 0} · in-app{" "}
                {log.payload?.notified ?? 0} · skipped {log.payload?.excluded?.total ?? 0}
              </span>
              <span className="text-gray-500">{new Date(log.created_at).toLocaleString("en-NG")}</span>
            </li>
          ))}
          {!(data.recentDeliveryLogs || []).length && (
            <li className="text-gray-400">No delivery runs logged yet.</li>
          )}
        </ul>
      </div>
    </section>
  );
}
