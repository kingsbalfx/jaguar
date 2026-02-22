import React from "react";
import PriceButton from "../../components/PriceButton";
import LiveSessionPanel from "../../components/LiveSessionPanel";
import ContentLibrary from "../../components/ContentLibrary";
import { PRICING_TIERS, formatPrice } from "../../lib/pricing-config";

export default function VipDashboard() {
  const tier = PRICING_TIERS.VIP;
  const priceLabel = formatPrice(tier.price, tier.currency || "NGN");

  return (
    <section className="relative overflow-hidden">
      <div className="candle-backdrop" aria-hidden="true" />
      <div className="container mx-auto px-6 py-8 text-white">
        <div className="flex flex-wrap items-center justify-between gap-4 mb-6">
          <div>
            <div className="text-xs uppercase tracking-widest text-purple-200">VIP Access</div>
            <h2 className="text-2xl font-bold">VIP Dashboard</h2>
            <p className="text-sm text-gray-300 mt-1">{tier.description}</p>
          </div>
          <div className="text-right">
            <div className="text-sm text-gray-400">Access price</div>
            <div className="text-xl font-semibold text-yellow-300">{priceLabel}</div>
            <div className="mt-2 flex items-center gap-3 justify-end">
              <a href={`/checkout?plan=vip`} className="px-3 py-2 bg-indigo-600 rounded">
                Checkout
              </a>
              <PriceButton initialPrice={tier.price} plan="vip" />
            </div>
          </div>
        </div>

        <div className="grid lg:grid-cols-[1.1fr_0.9fr] gap-6">
          <LiveSessionPanel />
          <div className="glass-panel rounded-2xl p-5">
            <div className="text-xs uppercase tracking-widest text-purple-200">Plan Highlights</div>
            <ul className="mt-3 space-y-2 text-sm text-gray-300">
              <li>Group mentorship sessions and VIP rooms</li>
              <li>High-frequency signals and session breakdowns</li>
              <li>Priority support and weekly strategy reviews</li>
            </ul>
          </div>
        </div>

        <ContentLibrary />
      </div>
    </section>
  );
}
