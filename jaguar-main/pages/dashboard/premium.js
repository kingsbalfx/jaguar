import React from "react";
import LiveSessionPanel from "../../components/LiveSessionPanel";
import ContentLibrary from "../../components/ContentLibrary";
import BotAccessPanel from "../../components/BotAccessPanel";
import { PRICING_TIERS, formatPrice } from "../../lib/pricing-config";
import { createPagesServerClient } from "@supabase/auth-helpers-nextjs";
import { getSupabaseClient } from "../../lib/supabaseClient";
import { getPlanStatus } from "../../lib/subscription-status";

export async function getServerSideProps(ctx) {
  const planId = "premium";
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
  const redirectMap = {
    admin: "/admin",
    vip: "/dashboard/vip",
    pro: "/dashboard/pro",
    lifetime: "/dashboard/lifetime",
  };
  if (role !== planId) {
    const dest = redirectMap[role] || "/dashboard";
    return { redirect: { destination: dest, permanent: false } };
  }

  const planStatus = await getPlanStatus({
    supabaseAdmin,
    userId: session.user.id,
    email: session.user.email,
    plan: planId,
    role,
  });

  return { props: { planStatus } };
}

export default function PremiumDashboard({ planStatus }) {
  const tier = PRICING_TIERS.PREMIUM;
  const priceLabel = formatPrice(tier.price, tier.currency || "NGN");
  const isActive = Boolean(planStatus?.active);
  const statusLabel = planStatus?.active ? "Active" : planStatus?.status === "expired" ? "Expired" : "Inactive";

  return (
    <section className="relative overflow-hidden">
      <div className="candle-backdrop" aria-hidden="true" />
      <div className="container mx-auto px-6 py-8 text-white">
        <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
          <div>
            <div className="text-xs uppercase tracking-widest text-indigo-200">Premium Access</div>
            <h2 className="text-2xl font-bold">Premium Dashboard</h2>
            <p className="text-sm text-gray-300 mt-1">{tier.description}</p>
          </div>
          <div className="text-right">
            <div className="text-xs uppercase tracking-widest text-gray-400">Plan status</div>
            <div className={`text-lg font-semibold ${isActive ? "text-emerald-300" : "text-yellow-300"}`}>
              {statusLabel}
            </div>
            {!isActive && (
              <div className="mt-2">
                <div className="text-sm text-gray-400">Access price</div>
                <div className="text-xl font-semibold text-yellow-300">{priceLabel}</div>
                <a href={`/checkout?plan=premium`} className="mt-2 inline-flex px-3 py-2 bg-indigo-600 rounded">
                  Pay to Activate
                </a>
              </div>
            )}
          </div>
        </div>

        <div className="grid lg:grid-cols-[1.1fr_0.9fr] gap-6">
          <LiveSessionPanel />
          <div className="glass-panel rounded-2xl p-5">
            <div className="text-xs uppercase tracking-widest text-blue-200">Plan Highlights</div>
            <ul className="mt-3 space-y-2 text-sm text-gray-300">
              <li>Premium-grade signals and tiered bot filters</li>
              <li>Daily lesson drops and community room access</li>
              <li>Priority support and analytics tracking</li>
            </ul>
          </div>
        </div>

        <div className="mt-6 glass-panel rounded-2xl p-5 flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="text-xs uppercase tracking-widest text-purple-200">Upgrade Option</div>
            <div className="text-lg font-semibold">Move up to VIP</div>
            <p className="text-sm text-gray-300">
              Unlock mentorship sessions and high-frequency VIP signals.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <a href="/checkout?plan=vip" className="px-3 py-2 bg-purple-600 rounded">
              Upgrade Now
            </a>
          </div>
        </div>

        <div className="mt-6">
          <BotAccessPanel tier={tier} isActive={isActive} />
        </div>

        <ContentLibrary />
      </div>
    </section>
  );
}
