import { useEffect, useMemo, useState } from "react";
import { PRICING_TIERS } from "../../lib/pricing-config";
import FeedbackMessage from "../../components/FeedbackMessage";

const planLabel = (plan) => PRICING_TIERS[String(plan || "").toUpperCase()]?.displayName || plan || "Unknown";
const STATUS_OPTIONS = ["active", "expired", "cancelled", "revoked", "inactive", "pending"];

function formatDateTimeLocal(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const offset = date.getTimezoneOffset();
  const local = new Date(date.getTime() - offset * 60 * 1000);
  return local.toISOString().slice(0, 16);
}

function expiryTone(item) {
  if (!item.ended_at) return "text-emerald-300";
  const diff = new Date(item.ended_at).getTime() - Date.now();
  if (diff <= 0) return "text-red-300";
  if (diff <= 7 * 24 * 60 * 60 * 1000) return "text-amber-300";
  return "text-emerald-300";
}

export default function Subscriptions() {
  const [subscriptions, setSubscriptions] = useState([]);
  const [drafts, setDrafts] = useState({});
  const [repairable, setRepairable] = useState([]);
  const [smtpStatus, setSmtpStatus] = useState({ configured: false, provider: "Not configured", sender: null });
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(true);
  const [savingKey, setSavingKey] = useState("");

  const load = async () => {
    setLoading(true);
    const response = await fetch("/api/admin/subscriptions");
    const data = await response.json();
    setSubscriptions(data.subscriptions || []);
    setDrafts({});
    setRepairable(data.repairable || []);
    setSmtpStatus(data.smtpStatus || { configured: false, provider: "Not configured", sender: null });
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const summary = useMemo(() => {
    const now = Date.now();
    return subscriptions.reduce(
      (acc, item) => {
        const status = String(item.status || "").toLowerCase();
        const endedAt = item.ended_at ? new Date(item.ended_at).getTime() : null;
        acc.total += 1;
        if (status === "active" && (!endedAt || endedAt > now)) acc.active += 1;
        if (status === "active" && endedAt && endedAt > now && endedAt <= now + 7 * 24 * 60 * 60 * 1000) acc.expiringSoon += 1;
        if (status === "expired" || (endedAt && endedAt <= now)) acc.expired += 1;
        if (!endedAt) acc.noExpiry += 1;
        return acc;
      },
      { total: 0, active: 0, expiringSoon: 0, expired: 0, noExpiry: 0 }
    );
  }, [subscriptions]);

  const subscriptionKey = (item, index) => `${item.email}-${item.plan}-${item.started_at || index}`;

  const getDraft = (item, index) => {
    const key = subscriptionKey(item, index);
    return drafts[key] || {
      status: item.status || "active",
      endedAt: formatDateTimeLocal(item.ended_at),
    };
  };

  const patchDraft = (item, index, patch) => {
    const key = subscriptionKey(item, index);
    setDrafts((prev) => ({
      ...prev,
      [key]: {
        ...getDraft(item, index),
        ...patch,
      },
    }));
  };

  const saveSubscription = async (item, index) => {
    const key = subscriptionKey(item, index);
    const draft = getDraft(item, index);
    setSavingKey(key);
    setMessage("Saving subscription expiration...");
    const response = await fetch("/api/admin/subscriptions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        action: "update_expiration",
        email: item.email,
        plan: item.plan,
        status: draft.status,
        endedAt: draft.endedAt || null,
      }),
    });
    const data = await response.json();
    setSavingKey("");
    setMessage(response.ok ? "Subscription expiration updated." : data.error || "Update failed.");
    if (response.ok) await load();
  };

  const repair = async (reference) => {
    setMessage("Repairing subscription...");
    const response = await fetch("/api/admin/subscriptions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reference }),
    });
    const data = await response.json();
    setMessage(response.ok ? "Subscription repaired and activated." : data.error || "Repair failed.");
    if (response.ok) await load();
  };

  const testEmail = async () => {
    setMessage("Testing Gmail SMTP...");
    const response = await fetch("/api/admin/subscriptions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action: "test_email" }),
    });
    const data = await response.json();
    const diagnostic = data.diagnostic
      ? ` ${JSON.stringify(data.diagnostic)}`
      : "";
    setMessage(`${data.message || data.error || "Gmail SMTP test failed."}${diagnostic}`);
  };

  return (
    <main className="container mx-auto space-y-6 p-4 text-white sm:p-6">
      <div>
        <h1 className="text-2xl font-bold">Subscription Management</h1>
        <p className="mt-1 text-sm text-gray-300">Review active, expired, and repairable verified subscriptions.</p>
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <span className={`inline-flex rounded-full px-3 py-1 text-xs font-semibold ${smtpStatus.configured ? "bg-emerald-500/20 text-emerald-200" : "bg-amber-500/20 text-amber-200"}`}>
            {smtpStatus.provider}: {smtpStatus.configured ? "Configured" : "Not configured"}
            {smtpStatus.sender ? ` (${smtpStatus.sender})` : ""}
          </span>
          {smtpStatus.configured && !smtpStatus.appPasswordLengthValid && (
            <span className="rounded-full bg-red-500/20 px-3 py-1 text-xs font-semibold text-red-200">
              Gmail App Password loaded as {smtpStatus.appPasswordLength} characters; expected 16
            </span>
          )}
          <button type="button" onClick={testEmail} disabled={!smtpStatus.configured} className="rounded bg-indigo-600 px-3 py-1 text-xs font-semibold disabled:cursor-not-allowed disabled:opacity-40">
            Send Gmail test email
          </button>
        </div>
      </div>
      {loading ? <p className="text-gray-400">Loading subscriptions...</p> : (
        <>
          <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            {[
              ["Total", summary.total, "Subscriptions tracked"],
              ["Active", summary.active, "Current access"],
              ["Expiring soon", summary.expiringSoon, "Within 7 days"],
              ["Expired", summary.expired, "Past expiry date"],
              ["No expiry", summary.noExpiry, "Lifetime/manual access"],
            ].map(([label, value, hint]) => (
              <div key={label} className="rounded-2xl border border-white/10 bg-white/[0.04] p-4">
                <div className="text-xs uppercase tracking-wide text-gray-400">{label}</div>
                <div className="mt-2 text-2xl font-bold">{value}</div>
                <div className="mt-1 text-xs text-gray-500">{hint}</div>
              </div>
            ))}
          </section>

          <section className="glass-panel rounded-2xl p-5">
            <h2 className="text-lg font-semibold">Verified payments needing repair</h2>
            <div className="mt-3 space-y-2">
              {repairable.map((payment) => (
                <div key={payment.id || payment.reference} className="flex flex-wrap items-center justify-between gap-3 rounded bg-black/30 p-3 text-sm">
                  <div><strong>{payment.customer_email}</strong> · {planLabel(payment.plan)} · {payment.reference}</div>
                  <button onClick={() => repair(payment.reference)} className="rounded bg-emerald-600 px-3 py-2">Activate verified payment</button>
                </div>
              ))}
              {repairable.length === 0 && <p className="text-sm text-gray-400">No verified payments require repair.</p>}
            </div>
          </section>
          <section className="glass-panel overflow-x-auto rounded-2xl p-5">
            <table className="min-w-full text-left text-sm">
              <thead><tr><th className="p-2">Email</th><th className="p-2">Plan</th><th className="p-2">Status</th><th className="p-2">Started</th><th className="p-2">Expiration day</th><th className="p-2">Action</th></tr></thead>
              <tbody>{subscriptions.map((item, index) => (
                <tr key={subscriptionKey(item, index)} className="border-t border-white/10">
                  <td className="p-2">{item.email}</td><td className="p-2">{planLabel(item.plan)}</td>
                  <td className="p-2">
                    <select
                      className="w-full min-w-[130px] rounded-md border border-white/10 bg-black/40 px-2 py-2 text-white"
                      value={getDraft(item, index).status}
                      onChange={(event) => patchDraft(item, index, { status: event.target.value })}
                    >
                      {STATUS_OPTIONS.map((status) => (
                        <option key={status} value={status}>{status.toUpperCase()}</option>
                      ))}
                    </select>
                  </td>
                  <td className="p-2">{item.started_at ? new Date(item.started_at).toLocaleDateString() : "-"}</td>
                  <td className="p-2">
                    <input
                      type="datetime-local"
                      className={`w-full min-w-[210px] rounded-md border border-white/10 bg-black/40 px-2 py-2 ${expiryTone(item)}`}
                      value={getDraft(item, index).endedAt}
                      onChange={(event) => patchDraft(item, index, { endedAt: event.target.value })}
                    />
                    <div className={`mt-1 text-xs ${expiryTone(item)}`}>
                      Current: {item.ended_at ? new Date(item.ended_at).toLocaleString() : "No expiry"}
                    </div>
                  </td>
                  <td className="p-2">
                    <button
                      type="button"
                      onClick={() => saveSubscription(item, index)}
                      disabled={savingKey === subscriptionKey(item, index)}
                      className="rounded bg-emerald-600 px-3 py-2 text-xs font-semibold text-white disabled:opacity-60"
                    >
                      {savingKey === subscriptionKey(item, index) ? "Saving..." : "Save expiry"}
                    </button>
                  </td>
                </tr>
              ))}</tbody>
            </table>
          </section>
        </>
      )}
      <FeedbackMessage
        message={message}
        type={/failed|error|not configured|connection/i.test(message) ? "error" : /repairing|testing/i.test(message) ? "info" : "success"}
      />
    </main>
  );
}
