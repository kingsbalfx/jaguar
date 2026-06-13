import { useState } from "react";
import RiskDisclaimer from "./RiskDisclaimer";

export default function MT5SubmissionForm({ disabled = false }) {
  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const [server, setServer] = useState("");
  const [status, setStatus] = useState({ type: "", message: "" });
  const [loading, setLoading] = useState(false);
  const [consentAccepted, setConsentAccepted] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    if (disabled) return;
    setStatus({ type: "", message: "" });
    if (!login || !password || !server) {
      setStatus({ type: "error", message: "Login, password, and server are required." });
      return;
    }
    if (!consentAccepted) {
      setStatus({ type: "error", message: "You must accept the account and risk notice before submitting." });
      return;
    }

    setLoading(true);
    try {
      const res = await fetch("/api/user/mt5-credentials", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ login, password, server, consentAccepted }),
      });
      const json = await res.json();
      if (!res.ok) {
        throw new Error(json?.error || "Failed to submit MT5 credentials.");
      }
      setLogin("");
      setPassword("");
      setServer("");
      setConsentAccepted(false);
      setStatus({ type: "success", message: "Submitted to admin. We will activate it shortly." });
    } catch (err) {
      setStatus({ type: "error", message: err.message || "Submission failed." });
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={submit} className="space-y-3">
      <div className="rounded-lg border border-red-400/40 bg-red-400/10 p-3 text-sm text-red-100">
        Only submit demo account details or a dedicated low-risk account. Do not submit your main trading account password.
      </div>
      <RiskDisclaimer />
      <div>
        <label className="block text-xs text-gray-300 mb-1">MT5 Login</label>
        <input
          type="text"
          value={login}
          onChange={(e) => setLogin(e.target.value)}
          placeholder="e.g. 12345678"
          className="w-full rounded bg-black/30 border border-white/10 px-3 py-2 text-white"
          disabled={disabled}
        />
      </div>
      <div>
        <label className="block text-xs text-gray-300 mb-1">MT5 Investor/Read-only Password or Dedicated Account Password</label>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Enter your MT5 password"
          className="w-full rounded bg-black/30 border border-white/10 px-3 py-2 text-white"
          disabled={disabled}
        />
        <p className="mt-1 text-xs text-gray-400">Prefer investor/read-only password where supported by your broker.</p>
      </div>
      <label className="flex items-start gap-2 text-xs text-gray-200">
        <input
          type="checkbox"
          className="mt-1"
          checked={consentAccepted}
          onChange={(e) => setConsentAccepted(e.target.checked)}
          required
          disabled={disabled}
        />
        <span>I understand KINGSBALFX is not responsible for trading losses and I am submitting a demo/dedicated account for activation review.</span>
      </label>
      <div>
        <label className="block text-xs text-gray-300 mb-1">MT5 Server</label>
        <input
          type="text"
          value={server}
          onChange={(e) => setServer(e.target.value)}
          placeholder="e.g. Broker-ServerName"
          className="w-full rounded bg-black/30 border border-white/10 px-3 py-2 text-white"
          disabled={disabled}
        />
      </div>

      {status?.message && (
        <div className={`text-xs ${status.type === "success" ? "text-green-400" : "text-red-400"}`}>
          {status.message}
        </div>
      )}

      <button
        type="submit"
        disabled={loading || disabled || !consentAccepted}
        className="px-4 py-2 rounded bg-emerald-600 text-white hover:bg-emerald-500 disabled:opacity-60"
      >
        {loading ? "Submitting..." : "Send to Admin"}
      </button>
    </form>
  );
}
