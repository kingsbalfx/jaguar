import { useEffect, useState } from "react";
import { createPagesServerClient } from "@supabase/auth-helpers-nextjs";
import { getSupabaseClient } from "../../lib/supabaseClient";

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
    if (role !== "admin") {
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

  useEffect(() => {
    let active = true;
    fetch("/api/admin/mt5-credentials")
      .then((res) => res.json())
      .then((data) => {
        if (!active || !data?.credentials) return;
        setLogin(data.credentials.login || "");
        setServer(data.credentials.server || "");
        setUpdatedAt(data.credentials.updated_at || null);
        setHasPassword(Boolean(data.credentials.hasPassword));
      })
      .catch(() => {
        if (!active) return;
        setStatus({ type: "error", message: "Failed to load MT5 credentials." });
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;
    fetch("/api/admin/mt5-submissions")
      .then((res) => res.json())
      .then((data) => {
        if (!active) return;
        if (data?.submissions) {
          setSubmissions(data.submissions);
        }
      })
      .catch(() => {
        if (!active) return;
        setSubmissionsStatus({ type: "error", message: "Failed to load MT5 submissions." });
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
      setSubmissionsStatus({ type: "success", message: "Submission activated and set as current bot credentials." });
      const refreshed = await fetch("/api/admin/mt5-submissions").then((r) => r.json());
      setSubmissions(refreshed?.submissions || []);
    } catch (err) {
      setSubmissionsStatus({ type: "error", message: err.message || "Activation failed." });
    } finally {
      setActivatingId(null);
    }
  };

  const submit = async (e) => {
    e.preventDefault();
    setStatus({ type: "", message: "" });

    if (!login || !password || !server) {
      setStatus({ type: "error", message: "Login, password, and server are required." });
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
      setPassword("");
      setHasPassword(true);
      setUpdatedAt(new Date().toISOString());
      setStatus({ type: "success", message: "MT5 credentials saved. Restart the bot to reconnect." });
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
      setRestartStatus({ type: "success", message: "Restart requested. Bot will reconnect shortly." });
    } catch (err) {
      setRestartStatus({ type: "error", message: err.message || "Failed to restart bot." });
    } finally {
      setRestarting(false);
    }
  };

  return (
    <div className="p-6 max-w-3xl">
      <h2 className="text-2xl font-bold mb-2">Admin Settings</h2>
      <p className="text-gray-300 mb-6">
        Enter MT5 login details once. The bot will fetch these from Supabase and auto-connect on
        startup. MT5 still must be running on a Windows machine with the broker account logged in.
      </p>

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
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder={hasPassword ? "******** (enter new to update)" : "Enter MT5 password"}
              className="w-full rounded bg-black/40 border border-white/10 px-3 py-2 text-white"
            />
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

          {status?.message && (
            <div
              className={`text-sm ${
                status.type === "success" ? "text-green-400" : "text-red-400"
              }`}
            >
              {status.message}
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

          {restartStatus?.message && (
            <div
              className={`mt-2 text-sm ${
                restartStatus.type === "success" ? "text-green-400" : "text-red-400"
              }`}
            >
              {restartStatus.message}
            </div>
          )}
        </div>
      </div>

      <div className="mt-8 bg-black/30 rounded-lg p-5 border border-white/5">
        <h3 className="text-lg font-semibold mb-4">User MT5 Submissions</h3>
        {submissionsStatus?.message && (
          <div
            className={`text-sm mb-3 ${
              submissionsStatus.type === "success" ? "text-green-400" : "text-red-400"
            }`}
          >
            {submissionsStatus.message}
          </div>
        )}
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
    </div>
  );
}

