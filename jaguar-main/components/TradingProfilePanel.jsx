import { useEffect, useMemo, useState } from "react";

const PROFILE_OPTIONS = [
  { value: "aggressive", label: "Aggressive" },
  { value: "balanced", label: "Balanced" },
  { value: "conservative", label: "Conservative" },
];

function buildWebhookUrl(token) {
  if (typeof window === "undefined") return null;
  if (!token) return null;
  return `${window.location.origin}/api/webhook/tradingview?token=${encodeURIComponent(token)}`;
}

export default function TradingProfilePanel() {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [status, setStatus] = useState({ type: "", message: "" });
  const [profile, setProfile] = useState("balanced");
  const [token, setToken] = useState(null);

  const webhookUrl = useMemo(() => buildWebhookUrl(token), [token]);

  async function load() {
    setLoading(true);
    setStatus({ type: "", message: "" });
    try {
      const res = await fetch("/api/user/trading-profile");
      const data = await res.json();
      if (!res.ok) throw new Error(data?.error || "Failed to load trading profile");
      setProfile(data?.tradingProfile || "balanced");
      setToken(data?.token || null);
      if (data?.columnsMissing) {
        setStatus({
          type: "warning",
          message: "Trading profile columns are missing in Supabase. Run migration 006 to enable this feature.",
        });
      }
    } catch (err) {
      setStatus({ type: "error", message: err.message || "Failed to load profile" });
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function saveProfile() {
    setSaving(true);
    setStatus({ type: "", message: "" });
    try {
      const res = await fetch("/api/user/trading-profile", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tradingProfile: profile }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.error || "Failed to save trading profile");
      setProfile(data?.tradingProfile || profile);
      setToken(data?.token || token);
      setStatus({ type: "success", message: "Trading profile saved." });
    } catch (err) {
      setStatus({ type: "error", message: err.message || "Failed to save profile" });
    } finally {
      setSaving(false);
    }
  }

  async function generateToken() {
    setGenerating(true);
    setStatus({ type: "", message: "" });
    try {
      const res = await fetch("/api/user/trading-profile", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ generateToken: true }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.error || "Failed to generate token");
      setProfile(data?.tradingProfile || profile);
      setToken(data?.token || null);
      setStatus({ type: "success", message: "Webhook token generated." });
    } catch (err) {
      setStatus({ type: "error", message: err.message || "Failed to generate token" });
    } finally {
      setGenerating(false);
    }
  }

  return (
    <div className="bg-black/30 rounded-lg p-4 border border-white/5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-xs uppercase tracking-widest text-emerald-200">Bot Risk Profile</div>
          <h4 className="text-base font-semibold text-white mt-1">Execution style</h4>
          <p className="text-sm text-gray-300 mt-1">
            Choose how strict the bot should be (trade frequency vs safety). Changes apply on the next bot loop.
          </p>
        </div>
        <button
          onClick={saveProfile}
          disabled={saving || loading}
          className="px-4 py-2 rounded-md bg-emerald-600 text-sm text-white disabled:opacity-60"
        >
          {saving ? "Saving..." : "Save"}
        </button>
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <label className="text-xs text-gray-400">
          Profile
          <select
            className="mt-1 w-full rounded-md bg-black/40 border border-white/10 px-3 py-2 text-sm text-white"
            value={profile}
            onChange={(e) => setProfile(e.target.value)}
            disabled={loading}
          >
            {PROFILE_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </label>
        <div className="text-xs text-gray-400">
          TradingView Webhook
          <div className="mt-1 flex items-center gap-2">
            <input
              className="w-full rounded-md bg-black/40 border border-white/10 px-3 py-2 text-sm text-white"
              readOnly
              value={webhookUrl || "Generate a token to get your webhook URL"}
            />
            <button
              onClick={generateToken}
              disabled={generating || loading}
              className="px-3 py-2 rounded-md bg-white/10 text-sm text-white disabled:opacity-60"
            >
              {generating ? "..." : token ? "Regenerate" : "Generate"}
            </button>
          </div>
          <p className="mt-2 text-[11px] text-gray-400">
            TradingView alert JSON example:
            <span className="block mt-1 font-mono text-gray-300">
              {`{ "symbol": "EURUSD", "direction": "BUY", "strategy": "breakout" }`}
            </span>
          </p>
        </div>
      </div>

      {status?.message && (
        <div
          className={`mt-3 text-sm ${
            status.type === "success"
              ? "text-emerald-200"
              : status.type === "warning"
                ? "text-yellow-200"
                : "text-rose-200"
          }`}
        >
          {status.message}
        </div>
      )}
    </div>
  );
}

