import Link from "next/link";
import { createPagesServerClient } from "@supabase/auth-helpers-nextjs";
import { getSupabaseClient } from "../../lib/supabaseClient";
import Mt5SyncStatusPanel from "../../components/Mt5SyncStatusPanel";
import TradeHistoryTable from "../../components/TradeHistoryTable";

export async function getServerSideProps(ctx) {
  const supabase = createPagesServerClient(ctx);
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session?.user) {
    return { redirect: { destination: "/login", permanent: false } };
  }

  const supabaseAdmin = getSupabaseClient({ server: true });
  let role = "user";
  if (supabaseAdmin) {
    const { data } = await supabaseAdmin
      .from("profiles")
      .select("role")
      .eq("id", session.user.id)
      .maybeSingle();
    role = (data?.role || "user").toLowerCase();
  }

  const adminEmails = [process.env.SUPER_ADMIN_EMAIL, process.env.NEXT_PUBLIC_ADMIN_EMAIL]
    .map((value) => String(value || "").trim().toLowerCase())
    .filter(Boolean);
  const userEmail = String(session.user.email || "").toLowerCase();
  const isAdmin = role === "admin" || (userEmail && adminEmails.includes(userEmail));

  return {
    props: {
      email: session.user.email || "",
      isAdmin,
    },
  };
}

export default function TradeHistoryPage({ email, isAdmin }) {
  return (
    <div className="app-bg text-white relative overflow-hidden min-h-[calc(100vh-160px)]">
      <div className="candle-backdrop" aria-hidden="true" />
      <div className="app-content container mx-auto px-4 py-10 sm:px-6 sm:py-16">
        <header className="mx-auto max-w-6xl">
          <div className="text-xs uppercase tracking-[0.25em] text-emerald-200">Trade History</div>
          <h1 className="text-3xl font-bold">MT5 Performance</h1>
          <p className="mt-2 text-sm text-gray-300">
            Every closed position synced from your MT5 account, with the exit reason MT5 reported and
            per-pair analytics built from the same trades.
          </p>
          {email && (
            <p className="mt-1 text-xs text-gray-500">
              Signed in as {email}
              {isAdmin ? " · admin view" : ""}
            </p>
          )}
        </header>

        <div className="mx-auto mt-8 max-w-6xl space-y-6">
          <Mt5SyncStatusPanel />
          <TradeHistoryTable />
          {isAdmin && (
            <p className="text-xs text-gray-500">
              Admin overview for every account lives on{" "}
              <Link href="/admin/mt5-performance">
                <a className="underline">/admin/mt5-performance</a>
              </Link>
              .
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
