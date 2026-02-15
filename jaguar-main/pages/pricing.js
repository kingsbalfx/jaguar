// pages/pricing.js
import React from "react";
import { PRICING_TIERS, formatPrice } from "../lib/pricing-config";

export default function Pricing() {
  // Get all pricing tiers and sort them by price (Free first, then by price)
  const plans = Object.values(PRICING_TIERS)
    .sort((a, b) => {
      if (a.price === 0) return -1;
      if (b.price === 0) return 1;
      return a.price - b.price;
    })
    .map((tier) => ({
      id: tier.id,
      title: tier.displayName,
      price: tier.price === 0 ? "Free" : formatPrice(tier.price),
      priceRaw: tier.price,
      subtitle: tier.description,
      badge: tier.badge,
      currency: tier.currency,
      billingCycle: tier.billingCycle,
      features: tier.features,
      color: getColorClasses(tier.color),
      highlight: getHighlightClasses(tier.color),
    }));

  function getColorClasses(color) {
    const colorMap = {
      yellow: "from-yellow-400/10 to-yellow-600/20 border-yellow-400/30",
      blue: "from-blue-500/10 to-blue-700/20 border-blue-500/30",
      purple: "from-purple-600/10 to-purple-900/20 border-purple-500/30",
      indigo: "from-indigo-600/10 to-indigo-900/20 border-indigo-500/30",
      pink: "from-pink-600/10 to-pink-900/20 border-pink-500/30",
    };
    return colorMap[color] || "from-gray-600/10 to-gray-800/20 border-gray-500/30";
  }

  function getHighlightClasses(color) {
    const colorMap = {
      yellow: "bg-yellow-500/10 text-yellow-300",
      blue: "bg-blue-600/10 text-blue-300",
      purple: "bg-purple-600/10 text-purple-300",
      indigo: "bg-indigo-600/10 text-indigo-300",
      pink: "bg-pink-600/10 text-pink-300",
    };
    return colorMap[color] || "bg-gray-600/10 text-gray-300";
  }

  function formatFeatureName(key) {
    return key
      .replace(/([A-Z])/g, " $1")
      .replace(/^./, (str) => str.toUpperCase())
      .trim();
  }

  function getFeatureDisplay(feature) {
    if (typeof feature === "boolean") {
      return feature ? "✓ Included" : "✗ Not included";
    }
    if (typeof feature === "number") {
      return feature;
    }
    if (feature === "unlimited") {
      return "Unlimited";
    }
    return feature?.toString() || "Included";
  }

  return (
    <main
      id="maincontent"
      role="main"
      className="container mx-auto px-6 py-16 text-white"
    >
      <div className="mb-16">
        <h1 className="text-4xl md:text-5xl font-extrabold text-center mb-6">
          Pricing Plans
        </h1>
        <p className="text-center text-gray-400 mb-4 max-w-3xl mx-auto text-lg">
          Choose the plan that matches your trading goals. All tiers include expert market analysis,
          community access, and our automated trading bot with tier-based signal quality and trade limits.
        </p>
        <p className="text-center text-gray-500 max-w-3xl mx-auto">
          Upgrade anytime. Cancel monthly plans without penalty. Lifetime plans are one-time purchases
          with immediate access to all future updates and unlimited features.
        </p>
      </div>

      {/* Pricing Comparison Table */}
      <div className="mb-16 overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-700">
              <th className="text-left py-4 px-4 font-bold">Feature</th>
              {plans.map((p) => (
                <th key={p.id} className="text-center py-4 px-4 font-bold">
                  {p.title}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            <tr className="border-b border-gray-800">
              <td className="py-4 px-4">Price</td>
              {plans.map((p) => (
                <td key={p.id} className="text-center py-4 px-4 font-bold">
                  <div>
                    {p.price}
                    {p.billingCycle === "monthly" && (
                      <div className="text-xs text-gray-400">/month</div>
                    )}
                    {p.billingCycle === "one-time" && (
                      <div className="text-xs text-gray-400">one-time</div>
                    )}
                  </div>
                </td>
              ))}
            </tr>
            <tr className="border-b border-gray-800">
              <td className="py-4 px-4">Trading Signals/Day</td>
              {plans.map((p) => (
                <td key={p.id} className="text-center py-4 px-4">
                  {getFeatureDisplay(p.features.maxSignalsPerDay)}
                </td>
              ))}
            </tr>
            <tr className="border-b border-gray-800">
              <td className="py-4 px-4">Max Concurrent Trades</td>
              {plans.map((p) => (
                <td key={p.id} className="text-center py-4 px-4">
                  {getFeatureDisplay(p.features.maxConcurrentTrades)}
                </td>
              ))}
            </tr>
            <tr className="border-b border-gray-800">
              <td className="py-4 px-4">Signal Quality</td>
              {plans.map((p) => (
                <td key={p.id} className="text-center py-4 px-4 capitalize">
                  {p.features.signalQuality}
                </td>
              ))}
            </tr>
            <tr className="border-b border-gray-800">
              <td className="py-4 px-4">Community Access</td>
              {plans.map((p) => (
                <td key={p.id} className="text-center py-4 px-4 capitalize">
                  {getFeatureDisplay(p.features.communityAccess)}
                </td>
              ))}
            </tr>
            <tr className="border-b border-gray-800">
              <td className="py-4 px-4">Market Breakdowns</td>
              {plans.map((p) => (
                <td key={p.id} className="text-center py-4 px-4">
                  {p.features.tradingHistory || p.features.performanceAnalytics ? "✓" : "✗"}
                </td>
              ))}
            </tr>
            <tr className="border-b border-gray-800">
              <td className="py-4 px-4">Priority Support</td>
              {plans.map((p) => (
                <td key={p.id} className="text-center py-4 px-4">
                  {p.features.prioritySupport ? "✓" : "✗"}
                </td>
              ))}
            </tr>
            <tr className="border-b border-gray-800">
              <td className="py-4 px-4">Mentorship Access</td>
              {plans.map((p) => (
                <td key={p.id} className="text-center py-4 px-4">
                  {p.features.mentorship ? "✓" : "✗"}
                </td>
              ))}
            </tr>
            {/* Group mentorship sessions */}
            <tr className="border-b border-gray-800">
              <td className="py-4 px-4 pl-8 text-xs text-gray-400">
                Group Sessions/Month
              </td>
              {plans.map((p) => (
                <td key={p.id} className="text-center py-4 px-4 text-xs">
                  {p.features.groupSessionsPerMonth || "-"}
                </td>
              ))}
            </tr>
            {/* 1-on-1 mentorship sessions */}
            <tr className="border-b border-gray-800">
              <td className="py-4 px-4 pl-8 text-xs text-gray-400">
                1-on-1 Sessions/Month
              </td>
              {plans.map((p) => (
                <td key={p.id} className="text-center py-4 px-4 text-xs">
                  {p.features.oneOnOneSessionsPerMonth || "-"}
                </td>
              ))}
            </tr>
            <tr className="border-b border-gray-800">
              <td className="py-4 px-4">Custom Strategies</td>
              {plans.map((p) => (
                <td key={p.id} className="text-center py-4 px-4">
                  {p.features.customStrategies ? "✓" : "✗"}
                </td>
              ))}
            </tr>
            <tr>
              <td className="py-4 px-4">API Access</td>
              {plans.map((p) => (
                <td key={p.id} className="text-center py-4 px-4">
                  {p.features.apiAccess ? "✓" : "✗"}
                </td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>

      {/* Card View for Mobile */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-6 mb-16 hidden md:hidden lg:grid xl:grid">
        {plans.map((p) => (
          <div
            key={p.id}
            className={`rounded-2xl p-6 bg-gradient-to-br ${p.color} border hover:scale-105 transition-transform duration-300 shadow-lg shadow-black/40 backdrop-blur-md ${
              p.id === "vip" || p.id === "pro" ? "lg:col-span-1 lg:scale-105" : ""
            }`}
          >
            {p.badge && (
              <div className={`text-xs font-bold mb-2 ${p.highlight} inline-block px-3 py-1 rounded-full`}>
                {p.badge}
              </div>
            )}

            <h2 className="text-2xl font-bold mb-2">{p.title}</h2>
            <p className="text-xs text-gray-400 mb-4">{p.subtitle}</p>

            <div className="text-center mb-6">
              <span className="text-3xl font-extrabold">{p.price}</span>
              {p.billingCycle === "monthly" && (
                <span className="text-gray-400 text-xs ml-1">/month</span>
              )}
              {p.billingCycle === "one-time" && (
                <span className="text-gray-400 text-xs ml-1">one-time</span>
              )}
            </div>

            <ul className="space-y-2 mb-6 text-xs">
              <li className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-green-400"></span>
                <span>{p.features.maxSignalsPerDay} signals/day</span>
              </li>
              <li className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-green-400"></span>
                <span>{p.features.maxConcurrentTrades} trades max</span>
              </li>
              <li className="flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-green-400"></span>
                <span>{p.features.signalQuality} signals</span>
              </li>
            </ul>

            <a
              href={`/register?plan=${p.id}`}
              className={`block text-center py-2.5 rounded-lg font-semibold text-sm ${p.highlight} border border-white/10 hover:bg-white/10 transition`}
            >
              Get Started
            </a>
          </div>
        ))}
      </div>

      {/* FAQ */}
      <div className="mt-16 max-w-2xl mx-auto">
        <h3 className="text-2xl font-bold mb-8 text-center">Frequently Asked Questions</h3>
        
        <div className="space-y-4">
          <details className="group border border-gray-700 rounded-lg p-4 cursor-pointer">
            <summary className="font-semibold flex justify-between items-center">
              Can I change plans anytime?
              <span className="group-open:rotate-180 transition">▼</span>
            </summary>
            <p className="text-gray-400 mt-4 text-sm">
              Yes! You can upgrade or downgrade your plan anytime. Monthly plans can be downgraded without penalty.
              Lifetime purchases last forever and cover all future updates.
            </p>
          </details>

          <details className="group border border-gray-700 rounded-lg p-4 cursor-pointer">
            <summary className="font-semibold flex justify-between items-center">
              What payment methods do you accept?
              <span className="group-open:rotate-180 transition">▼</span>
            </summary>
            <p className="text-gray-400 mt-4 text-sm">
              We process payments via Paystack. You can pay with card, bank transfer, or mobile money.
              All payments are secure and PCI-DSS compliant.
            </p>
          </details>

          <details className="group border border-gray-700 rounded-lg p-4 cursor-pointer">
            <summary className="font-semibold flex justify-between items-center">
              How do signal limits work?
              <span className="group-open:rotate-180 transition">▼</span>
            </summary>
            <p className="text-gray-400 mt-4 text-sm">
              Each tier has a daily signal limit. Free: 3 signals/day, Premium: 15, VIP: 30, Pro & Lifetime: Unlimited.
              Signals reset daily at midnight UTC.
            </p>
          </details>

          <details className="group border border-gray-700 rounded-lg p-4 cursor-pointer">
            <summary className="font-semibold flex justify-between items-center">
              Is mentorship included in all tiers?
              <span className="group-open:rotate-180 transition">▼</span>
            </summary>
            <p className="text-gray-400 mt-4 text-sm">
              Mentorship starts with VIP tier (group sessions). Pro tier includes 1-on-1 sessions (2/month).
              Lifetime members get unlimited 1-on-1 sessions. Free and Premium get community access only.
            </p>
          </details>

          <details className="group border border-gray-700 rounded-lg p-4 cursor-pointer">
            <summary className="font-semibold flex justify-between items-center">
              What symbols can I trade?
              <span className="group-open:rotate-180 transition">▼</span>
            </summary>
            <p className="text-gray-400 mt-4 text-sm">
              Free tier: Major forex only (8 pairs). Premium & above unlock: Minor forex, exotic pairs, 
              precious metals, cryptocurrencies, indices, and commodities. Total 66+ tradable instruments.
            </p>
          </details>
        </div>
      </div>

      <div className="mt-16 text-center text-sm text-gray-500">
        * All payments processed securely via Paystack.
        <br />* Pricing may vary by region. Shown in NGN (Nigerian Naira).
        <br />* 100% refund guarantee within 7 days of purchase.
      </div>
    </main>
  );
}
