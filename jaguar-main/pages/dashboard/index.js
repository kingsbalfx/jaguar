import React from "react";
import Link from "next/link";
import { createPagesServerClient } from "@supabase/auth-helpers-nextjs";
import { getSupabaseClient } from "../../lib/supabaseClient";
import { getPaidAccess } from "../../lib/subscription-status";
import ContentLibrary from "../../components/ContentLibrary";
import LiveSessionPanel from "../../components/LiveSessionPanel";
import { getMentorshipGroup, getMentorshipGroupLabel } from "../../lib/mentorship-groups";

export async function getServerSideProps(ctx) {
  const supabase = createPagesServerClient(ctx);
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session?.user) {
    return {
      redirect: {
        destination: "/login",
        permanent: false,
      },
    };
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

  if (role === "admin") {
    return {
      redirect: {
        destination: "/admin",
        permanent: false,
      },
    };
  }
  const access = await getPaidAccess({ supabaseAdmin, email: session.user.email, role });
  return {
    props: {
      email: session.user.email || "",
      activePlan: access.active ? access.plan : null,
    },
  };
}

export default function DashboardHome({ email, activePlan }) {
  const group = getMentorshipGroup(activePlan || "free");
  const planLabel = activePlan ? getMentorshipGroupLabel(activePlan) : "Starter Resources";
  return (
    <div className="app-bg text-white relative overflow-hidden min-h-[calc(100vh-160px)]">
      <div className="candle-backdrop" aria-hidden="true" />
      <div className="app-content container mx-auto px-4 py-10 sm:px-6 sm:py-16">
        <div className={`mx-auto max-w-4xl overflow-hidden rounded-3xl border border-white/10 bg-gradient-to-br ${group.accent} p-[1px] shadow-2xl`}>
          <div className="rounded-3xl bg-black/75 p-6 text-center backdrop-blur sm:p-8">
          <div className="text-xs uppercase tracking-[0.25em] text-emerald-200">{planLabel}</div>
          <h1 className="text-3xl font-bold mb-3">Welcome back</h1>
          <p className="text-gray-300 mb-6">
            {activePlan
              ? `Your ${planLabel} access is active. Live rooms, chat, and learning resources are ready.`
              : "Your account is ready. Explore available lessons or choose a subscription tier to unlock live sessions."}
          </p>
          {email && <p className="text-sm text-gray-500 mb-6">Signed in as {email}</p>}
          <div className="flex flex-wrap justify-center gap-3">
            {activePlan && (
              <Link href={`/dashboard/${activePlan}`}>
                <a className="px-5 py-3 rounded-lg bg-indigo-600 text-white font-semibold">Open Plan Dashboard</a>
              </Link>
            )}
            <Link href="/pricing">
              <a className="px-5 py-3 rounded-lg border border-white/20 text-white/90">{activePlan ? "View Other Plans" : "View Pricing"}</a>
            </Link>
          </div>
          </div>
        </div>
        <div className="mx-auto mt-8 max-w-6xl">
          <LiveSessionPanel heading={activePlan ? `${planLabel} Live Room` : "Available Live Room"} />
        </div>
        <div id="mentorship-content" className="mx-auto mt-8 max-w-6xl">
          <ContentLibrary />
        </div>
      </div>
    </div>
  );
}
