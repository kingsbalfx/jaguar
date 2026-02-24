import React from "react";
import PriceButton from "../../components/PriceButton";
import LiveSessionPanel from "../../components/LiveSessionPanel";
import ContentLibrary from "../../components/ContentLibrary";
import { PRICING_TIERS, formatPrice } from "../../lib/pricing-config";

export default function ProDashboard() {
  const tier = PRICING_TIERS.PRO;
  const priceLabel = formatPrice(tier.price, tier.currency || "NGN");

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
            <div className="text-sm text-gray-400">Access price</div>
            <div className="text-xl font-semibold text-yellow-300">{priceLabel}</div>
            <div className="mt-2 flex items-center gap-3 justify-end">
              <a href={`/checkout?plan=pro`} className="px-3 py-2 bg-indigo-600 rounded">
                Checkout
              </a>
              <PriceButton initialPrice={tier.price} plan="pro" />
            </div>
          </div>
        </div>

        <div className="grid lg:grid-cols-[1.1fr_0.9fr] gap-6">
          <LiveSessionPanel />
          <div className="glass-panel rounded-2xl p-5">
            <div className="text-xs uppercase tracking-widest text-indigo-200">Plan Highlights</div>
            <ul className="mt-3 space-y-2 text-sm text-gray-300">
              <li>1:1 mentorship focus and pro community access</li>
              <li>Advanced analytics and custom strategy reviews</li>
              <li>Unlimited signal flow with higher trade limits</li>
            </ul>
          </div>
        </div>

        <div className="mt-6 glass-panel rounded-2xl p-5 flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="text-xs uppercase tracking-widest text-pink-200">Upgrade Option</div>
            <div className="text-lg font-semibold">Move up to Lifetime</div>
            <p className="text-sm text-gray-300">
              Permanent access to every update, session, and signal.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <a href="/checkout?plan=lifetime" className="px-3 py-2 bg-pink-600 rounded">
              Upgrade Now
            </a>
            <PriceButton plan="lifetime" initialPrice={PRICING_TIERS.LIFETIME.price} />
          </div>
        </div>

        <ContentLibrary />
      </div>
    </section>
  );
}
