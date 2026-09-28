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
    console.error("admin challenges page error:", error);
    return { redirect: { destination: "/login", permanent: false } };
  }
};

const STATUS_STYLES = {
  pending: "bg-yellow-500/20 text-yellow-100",
  approved: "bg-blue-500/20 text-blue-100",
  active: "bg-green-500/20 text-green-100",
  rejected: "bg-red-500/20 text-red-100",
  expired: "bg-gray-500/20 text-gray-200",
  cancelled: "bg-gray-500/20 text-gray-300",
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

export default function AdminChallenges() {
  const [challenges, setChallenges] = useState([]);
  const [pool, setPool] = useState([]);
  const [stats, setStats] = useState(null);
  const [warnings, setWarnings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState("");
  const [feedback, setFeedback] = useState({ type: "", message: "" });
  const [approveDraft, setApproveDraft] = useState({ id: "", durationDays: "", note: "", accountId: "" });
  const [rejectDraft, setRejectDraft] = useState({ id: "", reason: "" });
  const [poolDraft, setPoolDraft] = useState({
    platform: "mt5",
    label: "",
    login: "",
    server: "Headway-Demo",
    password: "",
    tradingviewUrl: "",
    tradingviewUsername: "",
    notes: "",
  });

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const response = await fetch("/api/admin/challenges");
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || "Unable to load challenges");
      setChallenges(payload.challenges || []);
      setPool(payload.pool || []);
      setStats(payload.stats || null);
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

  const call = async (label, body, url = "/api/admin/challenges") => {
    setBusy(label);
    try {
      const response = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || "Request failed");
      setFeedback({
        type: "success",
        message: payload.warning || `${label} completed.`,
      });
      await load();
    } catch (error) {
      setFeedback({ type: "error", message: error.message || String(error) });
    } finally {
      setBusy("");
    }
  };

  const pending = useMemo(
    () => challenges.filter((challenge) => challenge.status === "pending"),
    [challenges],
  );

  return (
    <main className="container mx-auto px-4 py-6 sm:px-6 sm:py-8 text-white">
      <h1 className="text-2xl font-bold mb-1">Student Demo Challenges</h1>
      <p className="text-sm text-gray-400 mb-4">
        Approve student challenges, hand out demo credentials and keep the demo pool stocked.
      </p>

      <FeedbackMessage type={feedback.type} message={feedback.message} />

      {warnings.length > 0 && (
        <div className="mt-4 rounded border border-yellow-500/40 bg-yellow-500/10 p-4 text-sm text-yellow-100">
          <ul className="list-disc ml-5 space-y-1">
            {warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="mt-4 grid grid-cols-2 gap-3 lg:grid-cols-5">
        <Stat label="Pending" value={stats?.pending ?? "—"} tone="warn" />
        <Stat label="Active" value={stats?.active ?? "—"} tone="good" />
        <Stat label="Pool available" value={stats?.poolAvailable ?? "—"} />
        <Stat label="Pool total" value={stats?.poolTotal ?? "—"} />
        <Stat label="Expired on load" value={stats?.expiredNow ?? "—"} tone="bad" />
      </div>

      <div className="mt-4 flex flex-wrap gap-3">
        <button type="button" onClick={load} className="rounded bg-indigo-600 px-4 py-2 text-sm" disabled={loading}>
          Refresh
        </button>
        <button
          type="button"
          onClick={() => call("Expire sweep", { action: "expire" })}
          className="rounded bg-white/10 px-4 py-2 text-sm"
          disabled={Boolean(busy)}
        >
          Expire overdue challenges
        </button>
      </div>

      <PendingList
        pending={pending}
        pool={pool}
        busy={busy}
        approveDraft={approveDraft}
        setApproveDraft={setApproveDraft}
        rejectDraft={rejectDraft}
        setRejectDraft={setRejectDraft}
        onApprove={(payload) => call("Approve", payload)}
        onReject={(payload) => call("Reject", payload)}
      />

      <ChallengeTable
        challenges={challenges}
        busy={busy}
        onCancel={(id) => call("Cancel", { action: "cancel", id })}
      />

      <PoolSection
        pool={pool}
        draft={poolDraft}
        setDraft={setPoolDraft}
        busy={busy}
        onAdd={(payload) => call("Add demo account", payload, "/api/admin/challenge-accounts")}
        onAction={(payload) => call("Update demo account", payload, "/api/admin/challenge-accounts")}
      />
    </main>
  );
}

function PendingList({
  pending,
  pool,
  busy,
  approveDraft,
  setApproveDraft,
  rejectDraft,
  setRejectDraft,
  onApprove,
  onReject,
}) {
  return (
    <section className="mt-6">
      <h2 className="text-lg font-semibold mb-2">Pending requests ({pending.length})</h2>
      <ul className="space-y-3">
        {pending.map((challenge) => {
          const available = pool.filter(
            (account) => account.platform === challenge.platform && account.status === "available",
          );
          return (
            <li key={challenge.id} className="rounded border border-white/10 bg-white/5 p-4">
              <div className="flex flex-wrap items-center gap-3">
                <span className="rounded-full bg-yellow-500/20 px-2 py-0.5 text-xs text-yellow-100">pending</span>
                <span className="text-sm font-semibold uppercase">{challenge.platform}</span>
                <span className="text-sm">{challenge.email}</span>
                <span className="text-xs text-gray-400">plan: {challenge.plan}</span>
                <span className="text-xs text-gray-500">
                  {new Date(challenge.created_at).toLocaleString("en-NG")}
                </span>
              </div>
              {challenge.goal && <p className="mt-2 text-sm text-gray-300">Goal: {challenge.goal}</p>}
              {challenge.experience && (
                <p className="text-xs text-gray-400">Experience: {challenge.experience}</p>
              )}

              <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-4">
                <input
                  value={approveDraft.id === challenge.id ? approveDraft.durationDays : ""}
                  onChange={(event) =>
                    setApproveDraft({ ...approveDraft, id: challenge.id, durationDays: event.target.value })
                  }
                  placeholder={`days (${challenge.duration_days || 14})`}
                  className="rounded bg-white/10 px-3 py-2 text-sm"
                />
                <input
                  value={approveDraft.id === challenge.id ? approveDraft.note : ""}
                  onChange={(event) =>
                    setApproveDraft({ ...approveDraft, id: challenge.id, note: event.target.value })
                  }
                  placeholder="mentor note (optional)"
                  className="rounded bg-white/10 px-3 py-2 text-sm"
                />
                <select
                  value={approveDraft.id === challenge.id ? approveDraft.accountId : ""}
                  onChange={(event) =>
                    setApproveDraft({ ...approveDraft, id: challenge.id, accountId: event.target.value })
                  }
                  className="rounded bg-white/10 px-3 py-2 text-sm"
                >
                  <option value="">auto-assign ({available.length} free)</option>
                  {available.map((account) => (
                    <option key={account.id} value={account.id}>
                      {account.label || account.login || account.id}
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  className="rounded bg-green-600 px-4 py-2 text-sm"
                  disabled={Boolean(busy)}
                  onClick={() =>
                    onApprove({
                      action: "approve",
                      id: challenge.id,
                      durationDays:
                        approveDraft.id === challenge.id ? approveDraft.durationDays : undefined,
                      note: approveDraft.id === challenge.id ? approveDraft.note : undefined,
                      accountId:
                        approveDraft.id === challenge.id && approveDraft.accountId
                          ? approveDraft.accountId
                          : undefined,
                    })
                  }
                >
                  Approve &amp; assign
                </button>
              </div>

              <div className="mt-2 flex flex-wrap gap-2">
                <input
                  value={rejectDraft.id === challenge.id ? rejectDraft.reason : ""}
                  onChange={(event) =>
                    setRejectDraft({ ...rejectDraft, id: challenge.id, reason: event.target.value })
                  }
                  placeholder="rejection reason"
                  className="flex-1 rounded bg-white/10 px-3 py-2 text-sm"
                />
                <button
                  type="button"
                  className="rounded bg-red-600/80 px-4 py-2 text-sm"
                  disabled={Boolean(busy)}
                  onClick={() =>
                    onReject({
                      action: "reject",
                      id: challenge.id,
                      reason: rejectDraft.id === challenge.id ? rejectDraft.reason : "",
                    })
                  }
                >
                  Reject
                </button>
              </div>
            </li>
          );
        })}
        {pending.length === 0 && <li className="text-sm text-gray-400">No pending requests.</li>}
      </ul>
    </section>
  );
}



function ChallengeTable({ challenges, busy, onCancel }) {
  return (
    <section className="mt-6">
      <h2 className="text-lg font-semibold mb-2">All challenges ({challenges.length})</h2>
      <div className="overflow-x-auto rounded border border-white/10">
        <table className="min-w-full text-sm">
          <thead className="bg-white/5 text-left text-gray-300">
            <tr>
              <th className="px-3 py-2">Student</th>
              <th className="px-3 py-2">Platform</th>
              <th className="px-3 py-2">Plan</th>
              <th className="px-3 py-2">Status</th>
              <th className="px-3 py-2">Demo login</th>
              <th className="px-3 py-2">Expires</th>
              <th className="px-3 py-2">Actions</th>
            </tr>
          </thead>
          <tbody>
            {challenges.slice(0, 60).map((challenge) => (
              <tr key={challenge.id} className="border-t border-white/5">
                <td className="px-3 py-2">{challenge.email}</td>
                <td className="px-3 py-2 uppercase">{challenge.platform}</td>
                <td className="px-3 py-2 capitalize">{challenge.plan}</td>
                <td className="px-3 py-2">
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs ${
                      STATUS_STYLES[challenge.status] || "bg-white/10"
                    }`}
                  >
                    {challenge.status}
                  </span>
                </td>
                <td className="px-3 py-2 font-mono">{challenge.demo_login || "—"}</td>
                <td className="px-3 py-2 text-gray-400">
                  {challenge.expires_at ? new Date(challenge.expires_at).toLocaleDateString("en-NG") : "—"}
                </td>
                <td className="px-3 py-2">
                  {["pending", "active"].includes(challenge.status) && (
                    <button
                      type="button"
                      className="rounded bg-white/10 px-2 py-1 text-xs"
                      disabled={Boolean(busy)}
                      onClick={() => onCancel(challenge.id)}
                    >
                      Cancel
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {challenges.length === 0 && (
              <tr>
                <td className="px-3 py-2 text-gray-400" colSpan={7}>
                  No challenges yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function PoolSection({ pool, draft, setDraft, busy, onAdd, onAction }) {
  const isMt5 = draft.platform === "mt5";
  return (
    <section className="mt-6">
      <h2 className="text-lg font-semibold mb-2">Demo account pool ({pool.length})</h2>

      <div className="rounded border border-white/10 bg-white/5 p-4">
        <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
          <label className="flex flex-col gap-1 text-xs text-gray-300">
            Platform
            <select
              value={draft.platform}
              onChange={(event) => setDraft({ ...draft, platform: event.target.value })}
              className="rounded bg-white/10 px-3 py-2 text-sm"
            >
              <option value="mt5">MT5 demo</option>
              <option value="tradingview">TradingView</option>
            </select>
          </label>
          <label className="flex flex-col gap-1 text-xs text-gray-300">
            Label
            <input
              value={draft.label}
              onChange={(event) => setDraft({ ...draft, label: event.target.value })}
              placeholder="Academy demo #1"
              className="rounded bg-white/10 px-3 py-2 text-sm"
            />
          </label>
          {isMt5 ? (
            <>
              <label className="flex flex-col gap-1 text-xs text-gray-300">
                Login
                <input
                  value={draft.login}
                  onChange={(event) => setDraft({ ...draft, login: event.target.value })}
                  className="rounded bg-white/10 px-3 py-2 text-sm"
                />
              </label>
              <label className="flex flex-col gap-1 text-xs text-gray-300">
                Password
                <input
                  type="password"
                  value={draft.password}
                  onChange={(event) => setDraft({ ...draft, password: event.target.value })}
                  className="rounded bg-white/10 px-3 py-2 text-sm"
                />
              </label>
              <label className="flex flex-col gap-1 text-xs text-gray-300">
                Server
                <input
                  value={draft.server}
                  onChange={(event) => setDraft({ ...draft, server: event.target.value })}
                  className="rounded bg-white/10 px-3 py-2 text-sm"
                />
              </label>
            </>
          ) : (
            <>
              <label className="flex flex-col gap-1 text-xs text-gray-300 md:col-span-2">
                Invite link
                <input
                  value={draft.tradingviewUrl}
                  onChange={(event) => setDraft({ ...draft, tradingviewUrl: event.target.value })}
                  placeholder="https://www.tradingview.com/..."
                  className="rounded bg-white/10 px-3 py-2 text-sm"
                />
              </label>
              <label className="flex flex-col gap-1 text-xs text-gray-300">
                TradingView username
                <input
                  value={draft.tradingviewUsername}
                  onChange={(event) => setDraft({ ...draft, tradingviewUsername: event.target.value })}
                  className="rounded bg-white/10 px-3 py-2 text-sm"
                />
              </label>
            </>
          )}
          <label className="flex flex-col gap-1 text-xs text-gray-300">
            Notes
            <input
              value={draft.notes}
              onChange={(event) => setDraft({ ...draft, notes: event.target.value })}
              className="rounded bg-white/10 px-3 py-2 text-sm"
            />
          </label>
        </div>
        <button
          type="button"
          className="mt-3 rounded bg-green-600 px-4 py-2 text-sm"
          disabled={Boolean(busy)}
          onClick={async () => {
            await onAdd({ action: "add", ...draft });
            setDraft({
              ...draft,
              login: "",
              password: "",
              tradingviewUrl: "",
              tradingviewUsername: "",
              label: "",
              notes: "",
            });
          }}
        >
          Add demo account
        </button>
        <p className="mt-2 text-xs text-gray-400">
          Passwords are encrypted with MT5_CREDENTIALS_SECRET and only revealed to the student who owns
          the approved challenge.
        </p>
      </div>

      <PoolTable pool={pool} busy={busy} onAction={onAction} />
    </section>
  );
}

function PoolTable({ pool, busy, onAction }) {
  return (
    <div className="mt-3 overflow-x-auto rounded border border-white/10">
      <table className="min-w-full text-sm">
        <thead className="bg-white/5 text-left text-gray-300">
          <tr>
            <th className="px-3 py-2">Platform</th>
            <th className="px-3 py-2">Label</th>
            <th className="px-3 py-2">Login / link</th>
            <th className="px-3 py-2">Server</th>
            <th className="px-3 py-2">Status</th>
            <th className="px-3 py-2">Actions</th>
          </tr>
        </thead>
        <tbody>
          {pool.map((account) => (
            <tr key={account.id} className="border-t border-white/5">
              <td className="px-3 py-2 uppercase">{account.platform}</td>
              <td className="px-3 py-2">{account.label || "—"}</td>
              <td className="px-3 py-2 font-mono">
                {account.login || account.tradingviewUsername || account.tradingviewUrl || "—"}
              </td>
              <td className="px-3 py-2">{account.server || "—"}</td>
              <td className="px-3 py-2">{account.status}</td>
              <td className="px-3 py-2">
                <div className="flex flex-wrap gap-2">
                  {account.status !== "retired" ? (
                    <button
                      type="button"
                      className="rounded bg-white/10 px-2 py-1 text-xs"
                      disabled={Boolean(busy)}
                      onClick={() => onAction({ action: "retire", id: account.id })}
                    >
                      Retire
                    </button>
                  ) : (
                    <button
                      type="button"
                      className="rounded bg-white/10 px-2 py-1 text-xs"
                      disabled={Boolean(busy)}
                      onClick={() => onAction({ action: "activate", id: account.id })}
                    >
                      Reactivate
                    </button>
                  )}
                  <button
                    type="button"
                    className="rounded bg-red-600/80 px-2 py-1 text-xs"
                    disabled={Boolean(busy)}
                    onClick={() => onAction({ action: "delete", id: account.id })}
                  >
                    Delete
                  </button>
                </div>
              </td>
            </tr>
          ))}
          {pool.length === 0 && (
            <tr>
              <td className="px-3 py-2 text-gray-400" colSpan={6}>
                The demo pool is empty — add an MT5 demo or TradingView entry above.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

