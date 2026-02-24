import React from "react";
import PriceButton from "../../components/PriceButton";
import LiveSessionPanel from "../../components/LiveSessionPanel";
import ContentLibrary from "../../components/ContentLibrary";
import { PRICING_TIERS, formatPrice } from "../../lib/pricing-config";

export default function PremiumDashboard() {
  const tier = PRICING_TIERS.PREMIUM;
  const priceLabel = formatPrice(tier.price, tier.currency || "NGN");

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
            <div className="text-sm text-gray-400">Access price</div>
            <div className="text-xl font-semibold text-yellow-300">{priceLabel}</div>
            <div className="mt-2 flex items-center gap-3 justify-end">
              <a href={`/checkout?plan=premium`} className="px-3 py-2 bg-indigo-600 rounded">
                Checkout
              </a>
              <PriceButton initialPrice={tier.price} plan="premium" />
            </div>
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
            <PriceButton plan="vip" initialPrice={PRICING_TIERS.VIP.price} />
          </div>
        </div>

        <ContentLibrary />
      </div>
    </section>
  );
}
