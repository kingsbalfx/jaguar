import { useEffect, useState } from "react";
import { createPagesServerClient } from "@supabase/auth-helpers-nextjs";
import { getSupabaseClient } from "../../lib/supabaseClient";
import AccountFloatPanel from "../../components/AccountFloatPanel";
import FeedbackMessage from "../../components/FeedbackMessage";

export const getServerSideProps = async (ctx) => {
  try {
    const supabase = createPagesServerClient(ctx);
    const {
      data: { session },
    } = await supabase.auth.getSession();

    if (!session?.user) {
      return { redirect: { destination: "/login", permanent: false } };
    }

    const supabaseAdmin = getSupabaseClient({ server: true });
    const userId = session.user.id;
    const { data: profile } = await supabaseAdmin
      .from("profiles")
      .select("role")
      .eq("id", userId)
      .maybeSingle();

    const role = (profile?.role || "user").toLowerCase();
    const adminEmail = (process.env.NEXT_PUBLIC_ADMIN_EMAIL || process.env.SUPER_ADMIN_EMAIL || "").toLowerCase();
    const userEmail = (session.user.email || "").toLowerCase();
    const isAdminEmail = adminEmail && userEmail === adminEmail;

    if (isAdminEmail && role !== "admin") {
      try {
        await supabaseAdmin.from("profiles").update({ role: "admin" }).eq("id", userId);
      } catch (e) {
        // non-blocking: allow admin email override even if profile update fails
      }
    }

    if (role !== "admin" && !isAdminEmail) {
      return { redirect: { destination: "/", permanent: false } };
    }

    return { props: {} };
  } catch (err) {
    console.error("Admin settings auth error:", err);
    return { redirect: { destination: "/login", permanent: false } };
  }
};

export default function Settings() {
  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [server, setServer] = useState("");
  const [updatedAt, setUpdatedAt] = useState(null);
  const [hasPassword, setHasPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState({ type: "", message: "" });
  const [restarting, setRestarting] = useState(false);
  const [restartStatus, setRestartStatus] = useState({ type: "", message: "" });
  const [submissions, setSubmissions] = useState([]);
  const [submissionsStatus, setSubmissionsStatus] = useState({ type: "", message: "" });
  const [activatingId, setActivatingId] = useState(null);
  const [botStatus, setBotStatus] = useState(null);
  const [botStatusError, setBotStatusError] = useState("");
  const [registrationGate, setRegistrationGate] = useState({
    paused: false,
    reopen_at: "",
    message: "",
  });
  const [registrationGateLoading, setRegistrationGateLoading] = useState(false);
  const [registrationGateStatus, setRegistrationGateStatus] = useState({ type: "", message: "" });

  const toDatetimeLocal = (value) => {
    if (!value) return "";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "";
    const offset = date.getTimezoneOffset();
    const local = new Date(date.getTime() - offset * 60 * 1000);
    return local.toISOString().slice(0, 16);
  };

  const fromDatetimeLocal = (value) => {
    if (!value) return null;
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? null : date.toISOString();
  };

  const loadCredentials = async () => {
    const res = await fetch("/api/admin/mt5-credentials");
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data?.error || "Failed to load MT5 credentials.");
    }
    if (!data?.credentials) return;
    setLogin(data.credentials.login || "");
    setServer(data.credentials.server || "");
    setUpdatedAt(data.credentials.updated_at || null);
    setHasPassword(Boolean(data.credentials.hasPassword));
  };

  const loadSubmissions = async () => {
    const res = await fetch("/api/admin/mt5-submissions");
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data?.error || "Failed to load MT5 submissions.");
    }
    setSubmissions(data?.submissions || []);
  };

  const loadBotStatus = async () => {
    const res = await fetch("/api/admin/bot-status");
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data?.error || "Failed to load bot status.");
    }
    setBotStatus(data);
    setBotStatusError("");
  };

  const loadRegistrationGate = async () => {
    const res = await fetch("/api/admin/registration-gate", { cache: "no-store" });
    const data = await res.json();
    if (!res.ok) throw new Error(data?.error || "Failed to load registration gate.");
    setRegistrationGate({
      paused: Boolean(data.gate?.paused),
      reopen_at: toDatetimeLocal(data.gate?.reopen_at),
      message: data.gate?.message || "",
    });
    if (data.missingTable) {
      setRegistrationGateStatus({
        type: "error",
        message: "Run sql/2026-06-19_registration_gate.sql in Supabase to enable paid registration pause.",
      });
    }
  };

  useEffect(() => {
    let active = true;
    loadCredentials()
      .then(() => {
        if (!active) return;
      })
      .catch((err) => {
        if (!active) return;
        setStatus({
          type: "error",
          message: err.message || "Failed to load MT5 credentials.",
        });
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;
    loadRegistrationGate().catch((err) => {
      if (!active) return;
      setRegistrationGateStatus({ type: "error", message: err.message || "Failed to load registration pause settings." });
    });
    return () => {
      active = false;
    };
  }, []);

  const saveRegistrationGate = async (event) => {
    event.preventDefault();
    setRegistrationGateLoading(true);
    setRegistrationGateStatus({ type: "", message: "" });
    try {
      const res = await fetch("/api/admin/registration-gate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          paused: registrationGate.paused,
          reopenAt: fromDatetimeLocal(registrationGate.reopen_at),
          message: registrationGate.message,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.error || "Unable to save registration pause.");
      setRegistrationGate({
        paused: Boolean(data.gate?.paused),
        reopen_at: toDatetimeLocal(data.gate?.reopen_at),
        message: data.gate?.message || "",
      });
      setRegistrationGateStatus({
        type: "success",
        message: data.active ? "Paid registration and upgrades are paused. Free tier registration remains open." : "Paid registration and upgrades are open.",
      });
    } catch (err) {
      setRegistrationGateStatus({ type: "error", message: err.message || "Unable to save registration pause." });
    } finally {
      setRegistrationGateLoading(false);
    }
  };

  useEffect(() => {
    let active = true;

    const run = async () => {
      try {
        const res = await fetch("/api/admin/bot-status");
        const data = await res.json();
        if (!active) return;
        if (!res.ok) {
          throw new Error(data?.error || "Failed to load bot status.");
        }
        setBotStatus(data);
        setBotStatusError("");
      } catch (err) {
        if (!active) return;
        setBotStatusError(err.message || "Failed to load bot status.");
      }
    };

    run();
    const timer = setInterval(run, 10000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, []);

  useEffect(() => {
    let active = true;
    loadSubmissions()
      .then(() => {
        if (!active) return;
      })
      .catch((err) => {
        if (!active) return;
        setSubmissionsStatus({
          type: "error",
          message: err.message || "Failed to load MT5 submissions.",
        });
      });
    return () => {
      active = false;
    };
  }, []);

  const activateSubmission = async (id) => {
    setSubmissionsStatus({ type: "", message: "" });
    setActivatingId(id);
    try {
      const res = await fetch("/api/admin/mt5-submissions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.error || "Failed to activate submission.");
      await Promise.all([loadCredentials(), loadSubmissions(), loadBotStatus()]);
      setPassword("");
      setSubmissionsStatus({
        type: "success",
        message: "Submission activated. Bot credentials updated; the bot should auto-reconnect within ~15 seconds.",
      });
    } catch (err) {
      setSubmissionsStatus({ type: "error", message: err.message || "Activation failed." });
    } finally {
      setActivatingId(null);
    }
  };

  const submit = async (e) => {
    e.preventDefault();
    setStatus({ type: "", message: "" });

    if (!login || !server) {
      setStatus({ type: "error", message: "Login and server are required." });
      return;
    }

    setLoading(true);
    try {
      const res = await fetch("/api/admin/mt5-credentials", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ login, password, server }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data?.error || "Failed to save credentials.");
      }
      await Promise.all([loadCredentials(), loadBotStatus()]);
      setPassword("");
      setHasPassword(true);
      setStatus({
        type: "success",
        message: "MT5 credentials saved. Bot will auto-reconnect within ~15 seconds (or use Restart Bot).",
      });
    } catch (err) {
      setStatus({ type: "error", message: err.message || "Failed to save credentials." });
    } finally {
      setLoading(false);
    }
  };

  const restartBot = async () => {
    setRestartStatus({ type: "", message: "" });
    setRestarting(true);
    try {
      const res = await fetch("/api/admin/restart-bot", { method: "POST" });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data?.error || "Failed to restart bot.");
      }
      await loadBotStatus();
      setRestartStatus({ type: "success", message: "Restart requested. Bot will reconnect shortly." });
    } catch (err) {
      setRestartStatus({ type: "error", message: err.message || "Failed to restart bot." });
    } finally {
      setRestarting(false);
    }
  };

  return (
    <div className="max-w-3xl p-4 sm:p-6">
      <h2 className="text-2xl font-bold mb-2">Admin Settings</h2>
      <p className="text-gray-300 mb-6">
        Enter MT5 login details once. The bot will fetch these from Supabase and auto-connect on
        startup. MT5 still must be running on a Windows machine with the broker account logged in.
      </p>

      <div className="mb-8 rounded-2xl border border-amber-300/20 bg-amber-500/10 p-5 shadow-xl">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="text-xs uppercase tracking-[0.22em] text-amber-200">Paid Registration Control</div>
            <h3 className="mt-1 text-lg font-semibold">Pause paid applications and upgrades</h3>
            <p className="mt-1 text-sm text-gray-300">
              Free tier account creation stays open. Paid checkout, reactivation, and upgrades are blocked while this is active.
            </p>
          </div>
          <span className={`rounded-full px-3 py-1 text-xs font-semibold ${registrationGate.paused ? "bg-red-500/20 text-red-200" : "bg-emerald-500/20 text-emerald-200"}`}>
            {registrationGate.paused ? "Paused" : "Open"}
          </span>
        </div>
        <form onSubmit={saveRegistrationGate} className="mt-4 grid gap-4">
          <label className="flex items-start gap-3 rounded-xl border border-white/10 bg-black/20 p-3 text-sm text-gray-200">
            <input
              type="checkbox"
              checked={registrationGate.paused}
              onChange={(event) => setRegistrationGate((current) => ({ ...current, paused: event.target.checked }))}
              className="mt-1"
            />
            <span>
              <span className="block font-semibold text-white">Close paid applications temporarily</span>
              <span className="text-gray-300">Users may still create a free account, but cannot pay for Academy, VIP, Pro, or Lifetime until reopened.</span>
            </span>
          </label>
          <label className="text-sm text-gray-300">
            Reopening date and time
            <input
              type="datetime-local"
              value={registrationGate.reopen_at}
              onChange={(event) => setRegistrationGate((current) => ({ ...current, reopen_at: event.target.value }))}
              className="mt-1 w-full rounded bg-black/40 border border-white/10 px-3 py-2 text-white"
            />
          </label>
          <label className="text-sm text-gray-300">
            Message shown to users
            <textarea
              value={registrationGate.message}
              onChange={(event) => setRegistrationGate((current) => ({ ...current, message: event.target.value }))}
              rows={3}
              className="mt-1 w-full rounded bg-black/40 border border-white/10 px-3 py-2 text-white"
              placeholder="Application has been closed. A class is already going on. Please wait until the reopening date."
            />
          </label>
          <button
            type="submit"
            disabled={registrationGateLoading}
            className="w-full rounded bg-amber-500 px-4 py-2 font-semibold text-black disabled:opacity-60 sm:w-auto"
          >
            {registrationGateLoading ? "Saving..." : registrationGate.paused ? "Save Pause Settings" : "Open Paid Registration"}
          </button>
        </form>
      </div>

      <div className="bg-black/30 rounded-lg p-5 border border-white/5">
        <h3 className="text-lg font-semibold mb-4">MT5 Credentials</h3>
        <form onSubmit={submit} className="space-y-4">
          <div>
            <label className="block text-sm text-gray-300 mb-1">MT5 Login</label>
            <input
              type="text"
              value={login}
              onChange={(e) => setLogin(e.target.value)}
              placeholder="e.g. 12345678"
              className="w-full rounded bg-black/40 border border-white/10 px-3 py-2 text-white"
            />
          </div>

          <div>
            <label className="block text-sm text-gray-300 mb-1">MT5 Password</label>
            <div className="flex items-center gap-2">
              <input
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder={hasPassword ? "******** (leave empty to keep current)" : "Enter MT5 password"}
                className="w-full rounded bg-black/40 border border-white/10 px-3 py-2 text-white"
              />
              <button
                type="button"
                onClick={() => setShowPassword((v) => !v)}
                className="px-3 py-2 rounded border border-white/20 text-xs text-gray-200 hover:bg-white/10"
              >
                {showPassword ? "Hide" : "Show"}
              </button>
            </div>
          </div>

          <div>
            <label className="block text-sm text-gray-300 mb-1">MT5 Server</label>
            <input
              type="text"
              value={server}
              onChange={(e) => setServer(e.target.value)}
              placeholder="e.g. Broker-ServerName"
              className="w-full rounded bg-black/40 border border-white/10 px-3 py-2 text-white"
            />
          </div>

          {updatedAt && (
            <div className="text-xs text-gray-400">
              Last updated: {new Date(updatedAt).toLocaleString()}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="px-4 py-2 rounded bg-indigo-600 text-white hover:bg-indigo-500 disabled:opacity-60"
          >
            {loading ? "Saving..." : "Save Credentials"}
          </button>
        </form>

        <div className="mt-6 border-t border-white/5 pt-4">
          <h4 className="text-sm font-semibold mb-2">Bot Controls</h4>
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={restartBot}
              disabled={restarting}
              className="px-4 py-2 rounded bg-emerald-600 text-white hover:bg-emerald-500 disabled:opacity-60"
            >
              {restarting ? "Restarting..." : "Restart Bot"}
            </button>
            <span className="text-xs text-gray-400">
              Reloads MT5 credentials and reconnects.
            </span>
          </div>

        </div>
      </div>

      <div className="mt-8 bg-black/30 rounded-lg p-5 border border-white/5">
        <div className="flex items-center justify-between gap-3 mb-4">
          <div>
            <h3 className="text-lg font-semibold">Bot Monitor</h3>
            <div className="text-xs text-gray-400">
              Live Windows bot connection, floating profit, open trades, and recent bot activity.
            </div>
          </div>
          <button
            type="button"
            onClick={() => loadBotStatus().catch((err) => setBotStatusError(err.message || "Failed to load bot status."))}
            className="px-3 py-2 rounded border border-white/20 text-xs text-gray-200 hover:bg-white/10"
          >
            Refresh
          </button>
        </div>

        <div className="grid gap-3 md:grid-cols-2">
          <div className="rounded border border-white/10 p-3">
            <div className="text-xs uppercase tracking-wide text-gray-400">Bot Health</div>
            <div className="mt-1 text-sm text-white">
              Running: {botStatus?.bot?.running ? "Yes" : "No"}
            </div>
            <div className="text-sm text-white">
              MT5 Connected: {botStatus?.bot?.connected ? "Yes" : "No"}
            </div>
            <div className="text-sm text-white">
              Last heartbeat: {botStatus?.bot?.last_heartbeat ? new Date(botStatus.bot.last_heartbeat).toLocaleString() : "—"}
            </div>
            <div className="text-sm text-white">
              Last error: {botStatus?.bot?.last_error || "None"}
            </div>
          </div>

          <div className="rounded border border-white/10 p-3">
            <div className="text-xs uppercase tracking-wide text-gray-400">Account</div>
            <div className="mt-1 text-sm text-white">
              Login: {botStatus?.bot?.account?.login || "—"}
            </div>
            <div className="text-sm text-white">
              Server: {botStatus?.bot?.account?.server || "—"}
            </div>
            <div className="text-sm text-white">
              Balance: {botStatus?.bot?.account?.balance ?? "—"}
            </div>
            <div className="text-sm text-white">
              Equity: {botStatus?.bot?.account?.equity ?? "—"}
            </div>
          </div>

          <div className="rounded border border-white/10 p-3">
            <div className="text-xs uppercase tracking-wide text-gray-400">Floating Money</div>
            <div className="mt-1 text-sm text-white">
              Floating P/L: {botStatus?.bot?.metrics?.floating_profit ?? "—"}
            </div>
            <div className="text-sm text-white">
              Open positions: {botStatus?.bot?.metrics?.open_positions ?? "—"}
            </div>
            <div className="text-sm text-white">
              Free margin: {botStatus?.bot?.metrics?.margin_free ?? "—"}
            </div>
          </div>

          <div className="rounded border border-white/10 p-3">
            <div className="text-xs uppercase tracking-wide text-gray-400">Symbols</div>
            <div className="mt-1 text-sm text-white break-words">
              {(botStatus?.bot?.metrics?.symbols || []).join(", ") || "—"}
            </div>
          </div>
        </div>

        <div className="mt-4">
          <div className="text-xs uppercase tracking-wide text-gray-400 mb-2">Recent Bot Events</div>
          {!(botStatus?.bot?.recent_logs?.length || botStatus?.recentLogs?.length) ? (
            <div className="text-sm text-gray-400">No bot events yet.</div>
          ) : (
            <div className="space-y-2">
              {(botStatus?.bot?.recent_logs || botStatus?.recentLogs || []).slice(0, 8).map((item, index) => (
                <div key={`${item.created_at || index}-${item.event || index}`} className="rounded border border-white/10 p-3">
                  <div className="flex items-center justify-between gap-3">
                    <div className="text-sm text-white">{item.message || item.event}</div>
                    <div className="text-xs text-gray-400">
                      {item.created_at ? new Date(item.created_at).toLocaleString() : "—"}
                    </div>
                  </div>
                  {item.payload && (
                    <div className="mt-2 text-xs text-gray-400 break-words">
                      {JSON.stringify(item.payload)}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="mt-8">
        <AccountFloatPanel admin />
      </div>

      <div className="mt-8 bg-black/30 rounded-lg p-5 border border-white/5">
        <h3 className="text-lg font-semibold mb-4">User MT5 Submissions</h3>
        {submissions.length === 0 ? (
          <div className="text-sm text-gray-400">No submissions yet.</div>
        ) : (
          <div className="space-y-3">
            {submissions.map((item) => (
              <div key={item.id} className="rounded border border-white/10 p-3">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="text-sm text-white">{item.login}</div>
                    <div className="text-xs text-gray-400">
                      {item.server} • {item.email || "no email"}
                    </div>
                  </div>
                  <div className="text-xs text-gray-400 capitalize">{item.status || "pending"}</div>
                </div>
                <div className="mt-2 flex items-center gap-3">
                  <button
                    onClick={() => activateSubmission(item.id)}
                    disabled={activatingId === item.id}
                    className="px-3 py-1 rounded bg-emerald-600 text-white text-xs disabled:opacity-60"
                  >
                    {activatingId === item.id ? "Activating..." : "Use for Bot"}
                  </button>
                  {item.created_at && (
                    <span className="text-xs text-gray-500">
                      {new Date(item.created_at).toLocaleString()}
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
      <FeedbackMessage
        message={registrationGateStatus.message || status.message || restartStatus.message || botStatusError || submissionsStatus.message}
        type={
          registrationGateStatus.message ? registrationGateStatus.type :
          status.message ? status.type :
          restartStatus.message ? restartStatus.type :
          botStatusError ? "error" :
          submissionsStatus.type || "info"
        }
      />
    </div>
  );
}
