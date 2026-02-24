import React from "react";
import PriceButton from "../../components/PriceButton";
import LiveSessionPanel from "../../components/LiveSessionPanel";
import ContentLibrary from "../../components/ContentLibrary";
import { PRICING_TIERS, formatPrice } from "../../lib/pricing-config";

export default function LifetimeDashboard() {
  const tier = PRICING_TIERS.LIFETIME;
  const priceLabel = formatPrice(tier.price, tier.currency || "NGN");

  return (
    <section className="relative overflow-hidden">
      <div className="candle-backdrop" aria-hidden="true" />
      <div className="container mx-auto px-6 py-8 text-white">
        <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
          <div>
            <div className="text-xs uppercase tracking-widest text-pink-200">Lifetime Access</div>
            <h2 className="text-2xl font-bold">Lifetime Dashboard</h2>
            <p className="text-sm text-gray-300 mt-1">{tier.description}</p>
          </div>
          <div className="text-right">
            <div className="text-sm text-gray-400">Access price</div>
            <div className="text-xl font-semibold text-yellow-300">{priceLabel}</div>
            <div className="mt-2 flex items-center gap-3 justify-end">
              <a href={`/checkout?plan=lifetime`} className="px-3 py-2 bg-indigo-600 rounded">
                Checkout
              </a>
              <PriceButton initialPrice={tier.price} plan="lifetime" />
            </div>
          </div>
        </div>

        <div className="grid lg:grid-cols-[1.1fr_0.9fr] gap-6">
          <LiveSessionPanel />
          <div className="glass-panel rounded-2xl p-5">
            <div className="text-xs uppercase tracking-widest text-pink-200">Plan Highlights</div>
            <ul className="mt-3 space-y-2 text-sm text-gray-300">
              <li>Lifetime vault of every lesson and replay</li>
              <li>Unlimited mentorship access and priority support</li>
              <li>Full strategy suite and future upgrades</li>
            </ul>
          </div>
        </div>

        <div className="mt-6 glass-panel rounded-2xl p-5 flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="text-xs uppercase tracking-widest text-emerald-200">Top Tier</div>
            <div className="text-lg font-semibold">You are on the highest plan</div>
            <p className="text-sm text-gray-300">
              Keep enjoying every update, live session, and priority access.
            </p>
          </div>
          <a href="/pricing" className="px-3 py-2 bg-emerald-600 rounded">
            View Plan Details
          </a>
        </div>

        <ContentLibrary />
      </div>
    </section>
  );
}
