import React from "react";
import LiveSessionPanel from "../../components/LiveSessionPanel";
import ContentLibrary from "../../components/ContentLibrary";
import BotAccessPanel from "../../components/BotAccessPanel";
import { PRICING_TIERS } from "../../lib/pricing-config";
import { createPagesServerClient } from "@supabase/auth-helpers-nextjs";
import { getSupabaseClient } from "../../lib/supabaseClient";
import { getPaidAccess, getPlanStatus } from "../../lib/subscription-status";
import PlanInactivePanel from "../../components/PlanInactivePanel";
import MentorshipCards from "../../components/MentorshipCards";
import RiskDisclaimer from "../../components/RiskDisclaimer";

export async function getServerSideProps(ctx) {
  const planId = "pro";
  const supabase = createPagesServerClient(ctx);
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session?.user) {
    return {
      redirect: {
        destination: `/login?next=${encodeURIComponent(`/dashboard/${planId}`)}`,
        permanent: false,
      },
    };
  }

  const supabaseAdmin = getSupabaseClient({ server: true });
  let profile = null;
  if (supabaseAdmin) {
    const { data } = await supabaseAdmin
      .from("profiles")
      .select("role, email")
      .eq("id", session.user.id)
      .maybeSingle();
    profile = data || null;
  }

  const role = (profile?.role || "user").toLowerCase();
  if (role === "admin") return { redirect: { destination: "/admin", permanent: false } };
  const access = await getPaidAccess({ supabaseAdmin, email: session.user.email, role });
  if (access.active && access.plan !== planId) {
    return { redirect: { destination: `/dashboard/${access.plan}`, permanent: false } };
  }
  if (role !== planId && !access.active) return { redirect: { destination: "/dashboard", permanent: false } };

  const planStatus = await getPlanStatus({
    supabaseAdmin,
    userId: session.user.id,
    email: session.user.email,
    plan: planId,
    role,
  });

  return { props: { planStatus } };
}

export default function ProDashboard({ planStatus }) {
  const tier = PRICING_TIERS.PRO;
  const isActive = Boolean(planStatus?.active);
  const statusLabel = planStatus?.active ? "Active" : planStatus?.status === "expired" ? "Expired" : "Inactive";

  return (
    <section className="relative overflow-hidden">
      <div className="candle-backdrop" aria-hidden="true" />
      <div className="container mx-auto px-6 py-8 text-white">
        <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
          <div>
            <div className="text-xs uppercase tracking-widest text-indigo-200">Pro Access</div>
            <h2 className="text-2xl font-bold">Pro Dashboard</h2>
            <p className="text-sm text-gray-300 mt-1">{tier.description}</p>
          </div>
          <div className="text-right">
            <div className="text-xs uppercase tracking-widest text-gray-400">Plan status</div>
            <div className={`text-lg font-semibold ${isActive ? "text-emerald-300" : "text-yellow-300"}`}>
              {statusLabel}
            </div>
            {isActive && planStatus?.endedAt && <div className="text-xs text-gray-300">Expires {new Date(planStatus.endedAt).toLocaleDateString()}</div>}
            {!isActive && (
              <div className="mt-2">
                <a href={`/checkout?plan=pro`} className="inline-flex px-3 py-2 bg-indigo-600 rounded">
                  Reactivate Plan
                </a>
              </div>
            )}
          </div>
        </div>

        {!isActive ? <PlanInactivePanel planId="pro" /> : <>
        <div className="grid lg:grid-cols-[1.1fr_0.9fr] gap-6">
          <LiveSessionPanel />
          <div className="glass-panel rounded-2xl p-5">
            <div className="text-xs uppercase tracking-widest text-indigo-200">Plan Highlights</div>
            <ul className="mt-3 space-y-2 text-sm text-gray-300">
              <li>1:1 mentorship focus and pro community access</li>
              <li>Deeper strategy correction and journal review</li>
              <li>Personal risk review and disciplined execution planning</li>
            </ul>
          </div>
        </div>

        <div className="mt-6 glass-panel rounded-2xl p-5 flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="text-xs uppercase tracking-widest text-pink-200">Upgrade Option</div>
            <div className="text-lg font-semibold">Move up to Lifetime</div>
            <p className="text-sm text-gray-300">
              Permanent access to recorded lessons, PDFs, and course updates.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <a href="/checkout?plan=lifetime" className="px-3 py-2 bg-pink-600 rounded">
              Upgrade Now
            </a>
          </div>
        </div>

        <div id="bot-access" className="mt-6">
          <BotAccessPanel tier={tier} isActive={isActive} />
        </div>

        <div id="mentorship-content">
          <ContentLibrary />
        </div>
        <div className="mt-6"><MentorshipCards assignmentReview /></div>
        <div className="mt-6"><RiskDisclaimer /></div>
        </>}
      </div>
    </section>
  );
}
