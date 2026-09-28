import { useCallback, useEffect, useMemo, useState } from "react";
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
    console.error("admin accounts page error:", error);
    return { redirect: { destination: "/login", permanent: false } };
  }
};

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
      <div className={`mt-1 text-lg font-semibold ${toneClass}`}>{value}</div>
    </div>
  );
}

function StatusPill({ account }) {
  if (!account.enabled) {
    return (
      <span className="rounded-full bg-red-500/20 px-2 py-0.5 text-xs text-red-200">
        disabled{account.disabledReason ? ` (${account.disabledReason})` : ""}
      </span>
    );
  }
  if (account.running) {
    return <span className="rounded-full bg-green-500/20 px-2 py-0.5 text-xs text-green-200">running</span>;
  }
  return <span className="rounded-full bg-yellow-500/20 px-2 py-0.5 text-xs text-yellow-200">stopped</span>;
}


export default function AdminAccounts() {
  const [accounts, setAccounts] = useState([]);
  const [submissions, setSubmissions] = useState([]);
  const [summary, setSummary] = useState(null);
  const [bot, setBot] = useState(null);
  const [warnings, setWarnings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState("");
  const [filter, setFilter] = useState("all");
  const [feedback, setFeedback] = useState({ type: "", message: "" });
  const [draft, setDraft] = useState({
    login: "",
    password: "",
    server: "Headway-Demo",
    apiPort: "",
    botId: "",
    symbols: "",
  });

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const response = await fetch("/api/admin/accounts");
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || "Unable to load accounts");
      setAccounts(payload.accounts || []);
      setSubmissions(payload.submissions || []);
      setSummary(payload.summary || null);
      setBot(payload.bot || null);
      setWarnings(payload.warnings || []);
    } catch (error) {
      setFeedback({ type: "error", message: error.message || String(error) });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const run = async (label, body) => {
    setBusy(label);
    try {
      const response = await fetch("/api/admin/accounts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || "Request failed");
      setFeedback({
        type: "success",
        message: payload.warning || `${label} completed${payload.via ? ` (${payload.via})` : ""}.`,
      });
      await load();
    } catch (error) {
      setFeedback({ type: "error", message: error.message || String(error) });
    } finally {
      setBusy("");
    }
  };

  const visibleAccounts = useMemo(() => {
    if (filter === "running") return accounts.filter((account) => account.running);
    if (filter === "disabled") return accounts.filter((account) => !account.enabled);
    if (filter === "stopped") return accounts.filter((account) => !account.running && account.enabled);
    return accounts;
  }, [accounts, filter]);

  const pendingSubmissions = useMemo(
    () => submissions.filter((item) => String(item.status || "").toLowerCase() === "pending"),
    [submissions],
  );

  return (
    <main className="container mx-auto px-4 py-6 sm:px-6 sm:py-8 text-white">
      <h1 className="text-2xl font-bold mb-1">All MT5 Accounts</h1>
      <p className="text-sm text-gray-400 mb-4">
        Every login the bot knows about — locally configured, saved by the desktop admin API, and
        submitted through the website.
      </p>

      <FeedbackMessage type={feedback.type} message={feedback.message} />

      {warnings.length > 0 && (
        <div className="mt-4 rounded border border-yellow-500/40 bg-yellow-500/10 p-4 text-sm text-yellow-100">
          <div className="font-semibold mb-1">Attention</div>
          <ul className="list-disc ml-5 space-y-1">
            {warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="mt-4 grid grid-cols-2 gap-3 lg:grid-cols-5">
        <Stat label="Total logins" value={summary?.total ?? "—"} />
        <Stat label="Running now" value={summary?.running ?? "—"} tone="good" />
        <Stat label="Disabled" value={summary?.disabled ?? "—"} tone="bad" />
        <Stat label="Pending submissions" value={summary?.pendingSubmissions ?? "—"} tone="warn" />
        <Stat
          label="Bot API"
          value={bot?.reachable ? "reachable" : "offline"}
          tone={bot?.reachable ? "good" : "bad"}
        />
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <button type="button" onClick={load} className="px-4 py-2 rounded bg-indigo-600 text-sm" disabled={loading}>
          Refresh
        </button>
        <button
          type="button"
          onClick={() => run("Sync", { action: "sync" })}
          className="px-4 py-2 rounded bg-white/10 text-sm"
          disabled={Boolean(busy)}
        >
          Sync from bot
        </button>
        <div className="flex items-center gap-1 text-xs">
          {["all", "running", "stopped", "disabled"].map((option) => (
            <button
              key={option}
              type="button"
              onClick={() => setFilter(option)}
              className={`px-3 py-1 rounded-full capitalize ${
                filter === option ? "bg-indigo-600" : "bg-white/10 text-gray-300"
              }`}
            >
              {option}
            </button>
          ))}
        </div>
      </div>

      <section className="mt-6 rounded border border-white/10 bg-white/5 p-4">
        <h2 className="text-lg font-semibold mb-3">Add or update an account</h2>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-3 lg:grid-cols-6">
          <Field label="Login" value={draft.login} onChange={(value) => setDraft({ ...draft, login: value })} placeholder="5941472" />
          <Field label="Password" value={draft.password} onChange={(value) => setDraft({ ...draft, password: value })} type="password" placeholder="••••••" />
          <Field label="Server" value={draft.server} onChange={(value) => setDraft({ ...draft, server: value })} placeholder="Headway-Demo" />
          <Field label="API port" value={draft.apiPort} onChange={(value) => setDraft({ ...draft, apiPort: value })} placeholder="8003" />
          <Field label="Bot id" value={draft.botId} onChange={(value) => setDraft({ ...draft, botId: value })} placeholder="bot_acc_3" />
          <Field label="Symbols" value={draft.symbols} onChange={(value) => setDraft({ ...draft, symbols: value })} placeholder="EURUSD,XAUUSD" />
        </div>
        <div className="mt-3 flex items-center gap-3">
          <button
            type="button"
            className="px-4 py-2 rounded bg-green-600 text-sm"
            disabled={Boolean(busy)}
            onClick={async () => {
              await run("Add account", { action: "add", ...draft });
              setDraft({ ...draft, login: "", password: "" });
            }}
          >
            {busy === "Add account" ? "Saving…" : "Save account"}
          </button>
          <span className="text-xs text-gray-400">
            Saved to the bot when it is reachable, otherwise stored in Supabase for the next restart.
          </span>
        </div>
      </section>

      <section className="mt-6">
        <h2 className="text-lg font-semibold mb-2">Accounts ({visibleAccounts.length})</h2>
        <div className="overflow-x-auto rounded border border-white/10">
          <table className="min-w-full text-sm">
            <thead className="bg-white/5 text-left text-gray-300">
              <tr>
                <th className="px-3 py-2">Login</th>
                <th className="px-3 py-2">Server</th>
                <th className="px-3 py-2">Status</th>
                <th className="px-3 py-2">Sources</th>
                <th className="px-3 py-2">Port</th>
                <th className="px-3 py-2">Terminal</th>
                <th className="px-3 py-2">Owner</th>
                <th className="px-3 py-2">Actions</th>
              </tr>
            </thead>
            <tbody>
              {visibleAccounts.map((account) => (
                <tr key={account.login} className="border-t border-white/5">
                  <td className="px-3 py-2 font-mono">{account.login}</td>
                  <td className="px-3 py-2">{account.server || "—"}</td>
                  <td className="px-3 py-2">
                    <StatusPill account={account} />
                  </td>
                  <td className="px-3 py-2 text-gray-400">{(account.sources || []).join(", ")}</td>
                  <td className="px-3 py-2">{account.apiPort || "—"}</td>
                  <td className="px-3 py-2 text-gray-400">
                    {account.terminalOk ? "ok" : account.terminalReason || "unknown"}
                  </td>
                  <td className="px-3 py-2 text-gray-400">{account.email || account.userId || "—"}</td>
                  <td className="px-3 py-2">
                    <div className="flex flex-wrap gap-2">
                      {account.enabled && (
                        <button
                          type="button"
                          className="rounded bg-red-600/80 px-2 py-1 text-xs"
                          disabled={Boolean(busy)}
                          onClick={() => run("Disable", { action: "disable", login: account.login })}
                        >
                          Disable
                        </button>
                      )}
                      <button
                        type="button"
                        className="rounded bg-white/10 px-2 py-1 text-xs"
                        disabled={Boolean(busy)}
                        onClick={() => run("Remove", { action: "delete", login: account.login })}
                      >
                        Remove
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
              {visibleAccounts.length === 0 && (
                <tr>
                  <td className="px-3 py-2 text-gray-400" colSpan={8}>
                    {loading ? "Loading…" : "No account matches this filter."}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section className="mt-6">
        <h2 className="text-lg font-semibold mb-2">
          Website submissions ({pendingSubmissions.length} pending of {submissions.length})
        </h2>
        <ul className="text-sm space-y-1">
          {submissions.slice(0, 15).map((submission) => (
            <li
              key={`${submission.login}-${submission.created_at}`}
              className="flex flex-wrap justify-between gap-3 border-b border-white/5 py-1"
            >
              <span className="font-mono">{submission.login}</span>
              <span className="text-gray-400">{submission.server || "—"}</span>
              <span className="text-gray-400">{submission.email || "—"}</span>
              <span className="text-gray-300">{submission.status || "pending"}</span>
              <span className="text-gray-500">
                {submission.created_at ? new Date(submission.created_at).toLocaleString("en-NG") : ""}
              </span>
            </li>
          ))}
          {submissions.length === 0 && <li className="text-gray-400">No website submissions recorded.</li>}
        </ul>
      </section>
    </main>
  );
}

function Field({ label, value, onChange, type = "text", placeholder = "" }) {
  return (
    <label className="flex flex-col gap-1 text-xs text-gray-300">
      {label}
      <input
        type={type}
        value={value}
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value)}
        className="rounded bg-white/10 px-3 py-2 text-sm text-white"
      />
    </label>
  );
}

