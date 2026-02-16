// pages/pricing.js
import React from "react";

export default function Pricing() {
  const plans = [
    {
      id: "trial",
      title: "Trial",
      price: "Free",
      subtitle: "Perfect for beginners",
      bullets: ["Lite trading signals", "Weekly lessons", "Community preview"],
      color: "from-yellow-400/10 to-yellow-600/20 border-yellow-400/30",
      highlight: "bg-yellow-500/10 text-yellow-300",
    },
    {
      id: "premium",
      title: "Premium",
      price: "₦70,000",
      subtitle: "For serious traders",
      bullets: [
        "Full trading signals",
        "Access to private community",
        "Market breakdowns & updates",
        "Performance archive",
      ],
      color: "from-blue-500/10 to-blue-700/20 border-blue-500/30",
      highlight: "bg-blue-600/10 text-blue-300",
    },
    {
      id: "vip",
      title: "VIP",
      price: "₦150,000",
      subtitle: "For elite mentorship",
      bullets: [
        "1:1 mentorship program",
        "Priority signal alerts",
        "Direct strategy feedback",
        "Exclusive challenges",
      ],
      color: "from-purple-600/10 to-purple-900/20 border-purple-500/30",
      highlight: "bg-purple-600/10 text-purple-300",
    },
  ];

  return (
    <main
      id="maincontent"
      role="main"
      className="container mx-auto px-6 py-16 text-white"
    >
      <h1 className="text-4xl font-extrabold text-center mb-4">
        Choose Your Plan
      </h1>
      <p className="text-center text-gray-400 mb-12 max-w-2xl mx-auto">
        Select the plan that matches your trading goals. All tiers come with
        expert mentorship, active community access, and transparent progress tracking.
      </p>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
        {plans.map((p) => (
          <div
            key={p.id}
            className={`rounded-2xl p-8 bg-gradient-to-br ${p.color} border hover:scale-105 transition-transform duration-300 shadow-lg shadow-black/40 backdrop-blur-md`}
          >
            <div className="mb-6 text-center">
              <h2 className="text-2xl font-bold mb-2 uppercase tracking-wide">
                {p.title}
              </h2>
              <p className="text-sm text-gray-400">{p.subtitle}</p>
            </div>

            <div className="text-center mb-6">
              <span className="text-4xl font-extrabold">{p.price}</span>
              {p.id !== "trial" && (
                <span className="text-gray-400 text-sm ml-1">/month</span>
              )}
            </div>

            <ul className="space-y-2 mb-8 text-sm">
              {p.bullets.map((b, i) => (
                <li key={i} className="flex items-start gap-2">
                  <span
                    className={`w-2 h-2 rounded-full ${p.highlight}`}
                  ></span>
                  <span>{b}</span>
                </li>
              ))}
            </ul>

            <a
              href={`/register?plan=${p.id}`}
              className={`block text-center py-3 rounded-xl font-semibold tracking-wide ${p.highlight} border border-white/10 hover:bg-white/10 transition`}
            >
              Choose {p.title}
            </a>
          </div>
        ))}
      </div>

      <div className="mt-16 text-center text-sm text-gray-500">
        * All payments are securely processed via Paystack.
      </div>
    </main>
  );
}
