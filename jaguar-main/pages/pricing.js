// pages/pricing.js
import React from "react";
import { PRICING_TIERS, formatPrice } from "../lib/pricing-config";

const COLOR_MAP = {
  yellow: "from-yellow-400/10 to-yellow-600/20 border-yellow-400/30",
  blue: "from-blue-500/10 to-blue-700/20 border-blue-500/30",
  purple: "from-purple-600/10 to-purple-900/20 border-purple-500/30",
  indigo: "from-indigo-600/10 to-indigo-900/20 border-indigo-500/30",
  pink: "from-pink-600/10 to-pink-900/20 border-pink-500/30",
};

const HIGHLIGHT_MAP = {
  yellow: "bg-yellow-500/10 text-yellow-300",
  blue: "bg-blue-600/10 text-blue-300",
  purple: "bg-purple-600/10 text-purple-300",
  indigo: "bg-indigo-600/10 text-indigo-300",
  pink: "bg-pink-600/10 text-pink-300",
};

function formatFeature(feature) {
  if (feature === "unlimited") return "Unlimited";
  if (feature === true) return "Included";
  if (feature === false || feature == null) return "Not included";
  return feature.toString();
}

export default function Pricing() {
  const tiers = Object.values(PRICING_TIERS)
    .sort((a, b) => {
      if (a.price === 0) return -1;
      if (b.price === 0) return 1;
      return a.price - b.price;
    })
    .map((tier) => {
      const bullets = [
        `Signal quality: ${formatFeature(tier.features.signalQuality)}`,
        `Signals/day: ${formatFeature(tier.features.maxSignalsPerDay)}`,
        `Max trades: ${formatFeature(tier.features.maxConcurrentTrades)}`,
        `Bot access: ${tier.features.botAccess ? "Yes" : "No"}`,
        `Mentorship: ${tier.features.mentorship ? "Yes" : "No"}`,
      ];

      return {
        id: tier.id,
        title: tier.displayName,
        subtitle: tier.description,
        price: tier.price === 0 ? "Free" : formatPrice(tier.price, tier.currency),
        billingCycle: tier.billingCycle,
        bullets,
        color: COLOR_MAP[tier.color] || COLOR_MAP.indigo,
        highlight: HIGHLIGHT_MAP[tier.color] || HIGHLIGHT_MAP.indigo,
      };
    });

  return (
    <main id="maincontent" role="main" className="container mx-auto px-6 py-16 text-white">
      <div className="mb-14 text-center">
        <div className="inline-flex items-center gap-2 rounded-full border border-indigo-500/40 bg-indigo-500/10 px-3 py-1 text-xs uppercase tracking-widest text-indigo-200 mb-4">
          Plans & Access
        </div>
        <h1 className="display-font text-4xl md:text-6xl font-bold mb-4">
          Choose the tier that matches your trading mission.
        </h1>
        <p className="text-gray-300 mb-3 max-w-3xl mx-auto text-lg">
          Every plan includes market analysis, community access, and automated trading support with
          tier‑based signal quality.
        </p>
        <p className="text-gray-500 max-w-3xl mx-auto">
          Upgrade anytime. Monthly plans stay flexible. Lifetime offers permanent access to updates.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-5 gap-6">
        {tiers.map((p) => (
          <div
            key={p.id}
            className={`rounded-2xl p-6 bg-gradient-to-br ${p.color} border transition-transform duration-300 shadow-lg shadow-black/40 backdrop-blur-md hover:-translate-y-1`}
          >
            <div className="mb-5 text-center">
              <h2 className="text-xl font-bold mb-2 uppercase tracking-wide">{p.title}</h2>
              <p className="text-sm text-gray-400">{p.subtitle}</p>
            </div>

            <div className="text-center mb-6">
              <span className="text-3xl font-extrabold">{p.price}</span>
              {p.price !== "Free" && p.billingCycle && (
                <span className="text-gray-400 text-sm ml-1">/{p.billingCycle}</span>
              )}
            </div>

            <ul className="space-y-2 mb-6 text-sm">
              {p.bullets.map((b, i) => (
                <li key={i} className="flex gap-2">
                  <span>✔</span>
                  <span>{b}</span>
                </li>
              ))}
            </ul>

            <div className="text-center">
              <a
                href={`/checkout?plan=${p.id}`}
                className={`inline-block px-5 py-3 rounded-full text-sm font-semibold ${p.highlight}`}
              >
                {p.price === "Free" ? "Start Free" : "Subscribe"}
              </a>
            </div>
          </div>
        ))}
      </div>
    </main>
  );
}
