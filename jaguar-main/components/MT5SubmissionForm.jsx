import { useState } from "react";

export default function MT5SubmissionForm({ disabled = false }) {
  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const [server, setServer] = useState("");
  const [status, setStatus] = useState({ type: "", message: "" });
  const [loading, setLoading] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    if (disabled) return;
    setStatus({ type: "", message: "" });
    if (!login || !password || !server) {
      setStatus({ type: "error", message: "Login, password, and server are required." });
      return;
    }

    setLoading(true);
    try {
      const res = await fetch("/api/user/mt5-credentials", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ login, password, server }),
      });
      const json = await res.json();
      if (!res.ok) {
        throw new Error(json?.error || "Failed to submit MT5 credentials.");
      }
      setLogin("");
      setPassword("");
      setServer("");
      setStatus({ type: "success", message: "Submitted to admin. We will activate it shortly." });
    } catch (err) {
      setStatus({ type: "error", message: err.message || "Submission failed." });
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={submit} className="space-y-3">
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
        <label className="block text-xs text-gray-300 mb-1">MT5 Password</label>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Enter your MT5 password"
          className="w-full rounded bg-black/30 border border-white/10 px-3 py-2 text-white"
          disabled={disabled}
        />
      </div>
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
        disabled={loading || disabled}
        className="px-4 py-2 rounded bg-emerald-600 text-white hover:bg-emerald-500 disabled:opacity-60"
      >
        {loading ? "Submitting..." : "Send to Admin"}
      </button>
    </form>
  );
}
