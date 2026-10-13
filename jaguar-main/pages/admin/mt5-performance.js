import { useCallback, useEffect, useState } from "react";
import { createPagesServerClient } from "@supabase/auth-helpers-nextjs";
import { getSupabaseClient } from "../../lib/supabaseClient";
import FeedbackMessage from "../../components/FeedbackMessage";
import Mt5SyncStatusPanel from "../../components/Mt5SyncStatusPanel";
import PairPerformanceBreakdown from "../../components/PairPerformanceBreakdown";
import TradeHistoryTable from "../../components/TradeHistoryTable";

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
    const { data: profile } = await supabaseAdmin
      .from("profiles")
      .select("role")
      .eq("id", session.user.id)
      .maybeSingle();

    const role = (profile?.role || "user").toLowerCase();
    const adminEmail = (process.env.NEXT_PUBLIC_ADMIN_EMAIL || process.env.SUPER_ADMIN_EMAIL || "").toLowerCase();
    const userEmail = (session.user.email || "").toLowerCase();
    const isAdminEmail = adminEmail && userEmail === adminEmail;

    if (role !== "admin" && !isAdminEmail) {
      return { redirect: { destination: "/", permanent: false } };
    }

    return { props: {} };
  } catch (err) {
    console.error("Admin MT5 performance auth error:", err);
    return { redirect: { destination: "/login", permanent: false } };
  }
};

function StatCard({ label, value, hint, tone = "text-white" }) {
  return (
    <div className="glass-panel rounded-lg p-4">
      <div className="text-xs text-gray-400">{label}</div>
      <div className={`text-2xl font-semibold ${tone}`}>{value}</div>
      {hint && <div className="mt-1 text-xs text-gray-400">{hint}</div>}
    </div>
  );
}

export default function AdminMt5Performance() {
  const [period, setPeriod] = useState("all");
  const [state, setState] = useState({ loading: true, error: "", pairs: [], totals: null, periods: [] });

  const load = useCallback(async () => {
    setState((prev) => ({ ...prev, loading: true, error: "" }));
    try {
      const res = await fetch(`/api/user/pair-performance?scope=all&period=${encodeURIComponent(period)}`);
      const data = await res.json();
      if (!res.ok) throw new Error(data?.error || "Failed to load platform pair performance.");
      setState({
        loading: false,
        error: "",
        pairs: data.pairs || [],
        totals: data.totals || null,
        periods: data.periods || [],
      });
    } catch (err) {
      setState((prev) => ({ ...prev, loading: false, error: err.message || "Failed to load pair performance." }));
    }
  }, [period]);

  useEffect(() => {
    load();
  }, [load]);

  const totals = state.totals || {};

  return (
    <div className="app-bg text-white relative overflow-hidden min-h-[calc(100vh-160px)]">
      <div className="candle-backdrop" aria-hidden="true" />
      <div className="app-content container mx-auto px-4 py-10 sm:px-6 sm:py-16">
        <header className="mx-auto flex max-w-6xl flex-wrap items-end justify-between gap-3">
          <div>
            <div className="text-xs uppercase tracking-[0.25em] text-emerald-200">Admin</div>
            <h1 className="text-3xl font-bold">MT5 Performance</h1>
            <p className="mt-2 text-sm text-gray-300">
              Synced closed trades across every linked account: pair analytics, exit reasons and sync health.
            </p>
          </div>
          <label className="text-xs text-gray-400">
            Period
            <select
              value={period}
              onChange={(event) => setPeriod(event.target.value)}
              className="mt-1 block rounded-md border border-white/10 bg-black/40 px-3 py-2 text-sm text-white"
            >
              <option value="all">All time</option>
              {state.periods.map((entry) => (
                <option key={entry.value} value={entry.value}>
                  {entry.label}
                </option>
              ))}
            </select>
          </label>
        </header>

        <div className="mx-auto mt-8 max-w-6xl space-y-6">
          <FeedbackMessage message={state.error} type="error" />

          <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard
              label="Platform Net P&L"
              value={Number(totals.netPnl || 0).toLocaleString("en-US", {
                style: "currency",
                currency: "USD",
                maximumFractionDigits: 2,
              })}
              hint={`${totals.trades || 0} trades · ${totals.wins || 0}W / ${totals.losses || 0}L`}
              tone={Number(totals.netPnl || 0) >= 0 ? "text-emerald-200" : "text-red-200"}
            />
            <StatCard label="Win rate" value={`${Number(totals.winRate || 0).toFixed(2)}%`} hint={`${state.pairs.length} instrument(s)`} />
            <StatCard label="Volume traded" value={Number(totals.volume || 0).toFixed(2)} hint="Sum of closed lots" />
            <StatCard
              label="Pips captured"
              value={Number(totals.pips || 0).toFixed(1)}
              hint={state.loading ? "Refreshing..." : "Across the filtered set"}
            />
          </section>

          <Mt5SyncStatusPanel admin />

          <PairPerformanceBreakdown
            pairs={state.pairs}
            title="Platform Pair Performance"
            subtitle="All linked accounts for the selected period."
            emptyMessage="No pair analytics yet - run a sync first."
          />

          <TradeHistoryTable admin />
        </div>
      </div>
    </div>
  );
}
