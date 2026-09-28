import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
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
      .select("role,name")
      .eq("id", session.user.id)
      .maybeSingle();

    return {
      props: {
        email: session.user.email || null,
        name: profile?.name || null,
        role: String(profile?.role || "user").toLowerCase(),
      },
    };
  } catch (error) {
    console.error("challenge page error:", error);
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

function daysLeft(expiresAt) {
  if (!expiresAt) return null;
  const diff = new Date(expiresAt).getTime() - Date.now();
  if (Number.isNaN(diff)) return null;
  return Math.ceil(diff / 86400000);
}

export default function StudentChallenge({ email, name }) {
  const [context, setContext] = useState(null);
  const [platforms, setPlatforms] = useState([]);
  const [challenges, setChallenges] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [feedback, setFeedback] = useState({ type: "", message: "" });
  const [missingTable, setMissingTable] = useState(false);
  const [credentials, setCredentials] = useState({});
  const [draft, setDraft] = useState({ platform: "mt5", goal: "", experience: "" });

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const response = await fetch("/api/user/challenges");
      const payload = await response.json();
      if (!response.ok) {
        if (payload.missingTable) setMissingTable(true);
        throw new Error(payload.error || "Unable to load your challenges");
      }
      setContext(payload.context || null);
      setPlatforms(payload.platforms || []);
      setChallenges(payload.challenges || []);
      setDraft((current) => ({
        ...current,
        platform: (payload.platforms || [])[0]?.id || current.platform,
      }));
    } catch (error) {
      setFeedback({ type: "error", message: error.message || String(error) });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const create = async () => {
    setBusy(true);
    try {
      const response = await fetch("/api/user/challenges", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(draft),
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || "Unable to create the challenge");
      setFeedback({ type: "success", message: "Challenge requested — your mentor will review it shortly." });
      setDraft({ ...draft, goal: "", experience: "" });
      await load();
    } catch (error) {
      setFeedback({ type: "error", message: error.message || String(error) });
    } finally {
      setBusy(false);
    }
  };

  const cancel = async (id) => {
    setBusy(true);
    try {
      const response = await fetch(`/api/user/challenges?id=${encodeURIComponent(id)}`, {
        method: "DELETE",
      });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || "Unable to cancel the challenge");
      setFeedback({ type: "success", message: "Challenge cancelled." });
      await load();
    } catch (error) {
      setFeedback({ type: "error", message: error.message || String(error) });
    } finally {
      setBusy(false);
    }
  };

  const reveal = async (id) => {
    setBusy(true);
    try {
      const response = await fetch(`/api/user/challenge-credentials?id=${encodeURIComponent(id)}`);
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || "Credentials are not available yet");
      setCredentials((current) => ({ ...current, [id]: payload.credentials }));
    } catch (error) {
      setFeedback({ type: "error", message: error.message || String(error) });
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="container mx-auto px-4 py-6 sm:px-6 sm:py-8 text-white">
      <h1 className="text-2xl font-bold mb-1">Student Demo Challenge</h1>
      <p className="text-sm text-gray-400 mb-4">
        Request a demo challenge for MT5 or TradingView. Challenges follow your subscription plan and
        are handed out to registered students only.
      </p>

      <FeedbackMessage type={feedback.type} message={feedback.message} />

      {missingTable && (
        <div className="mt-4 rounded border border-yellow-500/40 bg-yellow-500/10 p-4 text-sm text-yellow-100">
          Demo challenges are not installed yet. Run
          <span className="font-mono"> jaguar-main/sql/2026-09-28_student_challenges.sql </span>
          in Supabase, then reload this page.
        </div>
      )}

      {loading && <div className="mt-4 text-sm text-gray-400">Loading…</div>}

      {!loading && context && (
        <>
          <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
            <div className="rounded border border-white/10 bg-white/5 p-3">
              <div className="text-xs uppercase tracking-wide text-gray-400">Your plan</div>
              <div className="mt-1 text-sm font-semibold capitalize">{context.plan}</div>
              <div className="text-xs text-gray-500">source: {context.planSource}</div>
            </div>
            <div className="rounded border border-white/10 bg-white/5 p-3">
              <div className="text-xs uppercase tracking-wide text-gray-400">Challenge length</div>
              <div className="mt-1 text-sm font-semibold">
                {context.rules.enabled ? `${context.rules.days} days` : "not included"}
              </div>
              <div className="text-xs text-gray-500">
                platforms: {context.rules.platforms.join(", ") || "none"}
              </div>
            </div>
            <div className="rounded border border-white/10 bg-white/5 p-3">
              <div className="text-xs uppercase tracking-wide text-gray-400">Usage</div>
              <div className="mt-1 text-sm font-semibold">
                {context.usage.active} open / {context.usage.usedThisMonth} this month
              </div>
              <div className="text-xs text-gray-500">
                {context.usage.remainingThisMonth === null
                  ? "unlimited this month"
                  : `${context.usage.remainingThisMonth} remaining`}
              </div>
            </div>
          </div>

          {!context.canCreate && (
            <div className="mt-4 rounded border border-yellow-500/40 bg-yellow-500/10 p-4 text-sm text-yellow-100">
              {context.reasons.includes("plan_not_eligible")
                ? "Demo challenges are part of the Academy, VIP, Pro and Lifetime plans. Upgrade to join a challenge."
                : "You already have an open challenge or have used your monthly allowance."}
              <Link href="/pricing" className="ml-2 underline">
                See plans
              </Link>
            </div>
          )}

          {context.canCreate && (
            <section className="mt-6 rounded border border-white/10 bg-white/5 p-4">
              <h2 className="text-lg font-semibold mb-3">Request a challenge</h2>
              <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
                <label className="flex flex-col gap-1 text-xs text-gray-300">
                  Platform
                  <select
                    value={draft.platform}
                    onChange={(event) => setDraft({ ...draft, platform: event.target.value })}
                    className="rounded bg-white/10 px-3 py-2 text-sm"
                  >
                    {platforms.map((platform) => (
                      <option key={platform.id} value={platform.id}>
                        {platform.label}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="flex flex-col gap-1 text-xs text-gray-300 md:col-span-2">
                  Goal for this challenge
                  <input
                    value={draft.goal}
                    onChange={(event) => setDraft({ ...draft, goal: event.target.value })}
                    placeholder="e.g. 6% growth with max 0.5% risk per trade"
                    className="rounded bg-white/10 px-3 py-2 text-sm"
                  />
                </label>
                <label className="flex flex-col gap-1 text-xs text-gray-300">
                  Experience
                  <input
                    value={draft.experience}
                    onChange={(event) => setDraft({ ...draft, experience: event.target.value })}
                    placeholder="beginner / 1 year"
                    className="rounded bg-white/10 px-3 py-2 text-sm"
                  />
                </label>
              </div>
              <div className="mt-3 flex flex-wrap items-center gap-3">
                <button
                  type="button"
                  onClick={create}
                  className="px-4 py-2 rounded bg-green-600 text-sm"
                  disabled={busy || !draft.platform}
                >
                  {busy ? "Submitting…" : "Request challenge"}
                </button>
                <span className="text-xs text-gray-400">
                  A mentor approves the request and assigns your demo credentials.
                </span>
              </div>
            </section>
          )}

          <MyChallengeList
            challenges={challenges}
            credentials={credentials}
            busy={busy}
            name={name}
            onReveal={reveal}
            onCancel={cancel}
          />
        </>
      )}
    </main>
  );
}
function MyChallengeList({ challenges, credentials, busy, name, onReveal, onCancel }) {
  return (
    <section className="mt-6">
      <h2 className="text-lg font-semibold mb-2">My challenges ({challenges.length})</h2>
      <ul className="space-y-3">
        {challenges.map((challenge) => {
          const remaining = daysLeft(challenge.expires_at);
          const revealed = credentials[challenge.id];
          return (
            <li key={challenge.id} className="rounded border border-white/10 bg-white/5 p-4">
              <div className="flex flex-wrap items-center gap-3">
                <span
                  className={`rounded-full px-2 py-0.5 text-xs ${
                    STATUS_STYLES[challenge.status] || "bg-white/10"
                  }`}
                >
                  {challenge.status}
                </span>
                <span className="text-sm font-semibold uppercase">{challenge.platform}</span>
                <span className="text-xs text-gray-400">plan: {challenge.plan}</span>
                <span className="text-xs text-gray-500">
                  requested {new Date(challenge.created_at).toLocaleString("en-NG")}
                </span>
                {remaining !== null && ["active", "approved"].includes(challenge.status) && (
                  <span className="text-xs text-green-300">{remaining} day(s) left</span>
                )}
              </div>

              {challenge.goal && <p className="mt-2 text-sm text-gray-300">Goal: {challenge.goal}</p>}
              {challenge.rejection_reason && (
                <p className="mt-2 text-sm text-red-200">Reason: {challenge.rejection_reason}</p>
              )}
              {challenge.admin_note && (
                <p className="mt-2 text-sm text-blue-200">Mentor note: {challenge.admin_note}</p>
              )}

              {["active", "approved"].includes(challenge.status) && (
                <div className="mt-3">
                  {!revealed ? (
                    <button
                      type="button"
                      onClick={() => onReveal(challenge.id)}
                      className="rounded bg-indigo-600 px-3 py-1.5 text-sm"
                      disabled={busy}
                    >
                      Show my credentials
                    </button>
                  ) : (
                    <div className="rounded bg-black/40 p-3 text-sm space-y-1">
                      <div className="text-xs uppercase text-gray-400">
                        {revealed.platform === "mt5" ? "MT5 demo login" : "TradingView access"}
                      </div>
                      {revealed.login && (
                        <div>
                          Login: <span className="font-mono">{revealed.login}</span>
                        </div>
                      )}
                      {revealed.server && (
                        <div>
                          Server: <span className="font-mono">{revealed.server}</span>
                        </div>
                      )}
                      {revealed.password && (
                        <div>
                          Password: <span className="font-mono">{revealed.password}</span>
                        </div>
                      )}
                      {revealed.tradingviewUrl && (
                        <div>
                          Invite link:{" "}
                          <a
                            href={revealed.tradingviewUrl}
                            target="_blank"
                            rel="noreferrer"
                            className="underline break-all"
                          >
                            {revealed.tradingviewUrl}
                          </a>
                        </div>
                      )}
                      {revealed.tradingviewUsername && (
                        <div>
                          TradingView user:{" "}
                          <span className="font-mono">{revealed.tradingviewUsername}</span>
                        </div>
                      )}
                      {!revealed.login && !revealed.tradingviewUrl && !revealed.tradingviewUsername && (
                        <div className="text-yellow-200">
                          Your mentor has not assigned demo credentials yet.
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}

              {["pending", "active"].includes(challenge.status) && (
                <button
                  type="button"
                  onClick={() => onCancel(challenge.id)}
                  className="mt-3 rounded bg-white/10 px-3 py-1.5 text-xs"
                  disabled={busy}
                >
                  Cancel challenge
                </button>
              )}
            </li>
          );
        })}
        {challenges.length === 0 && (
          <li className="text-sm text-gray-400">
            You have not joined a challenge yet{name ? `, ${name}` : ""}.
          </li>
        )}
      </ul>
    </section>
  );
}


