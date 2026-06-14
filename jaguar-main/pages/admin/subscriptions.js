import { useEffect, useState } from "react";
import { PRICING_TIERS } from "../../lib/pricing-config";
import FeedbackMessage from "../../components/FeedbackMessage";

const planLabel = (plan) => PRICING_TIERS[String(plan || "").toUpperCase()]?.displayName || plan || "Unknown";

export default function Subscriptions() {
  const [subscriptions, setSubscriptions] = useState([]);
  const [repairable, setRepairable] = useState([]);
  const [smtpStatus, setSmtpStatus] = useState({ configured: false, provider: "Not configured", sender: null });
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    const response = await fetch("/api/admin/subscriptions");
    const data = await response.json();
    setSubscriptions(data.subscriptions || []);
    setRepairable(data.repairable || []);
    setSmtpStatus(data.smtpStatus || { configured: false, provider: "Not configured", sender: null });
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

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
    <main className="container mx-auto space-y-6 p-6 text-white">
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
              <thead><tr><th className="p-2">Email</th><th className="p-2">Plan</th><th className="p-2">Status</th><th className="p-2">Started</th><th className="p-2">Expires</th></tr></thead>
              <tbody>{subscriptions.map((item, index) => (
                <tr key={`${item.email}-${item.plan}-${item.started_at || index}`} className="border-t border-white/10">
                  <td className="p-2">{item.email}</td><td className="p-2">{planLabel(item.plan)}</td><td className="p-2">{item.status}</td>
                  <td className="p-2">{item.started_at ? new Date(item.started_at).toLocaleDateString() : "-"}</td>
                  <td className="p-2">{item.ended_at ? new Date(item.ended_at).toLocaleDateString() : "No expiry"}</td>
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
