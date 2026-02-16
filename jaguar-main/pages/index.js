// pages/index.js
import React, { useState } from "react";
import Link from "next/link";

export default function Home() {
  const [mode, setMode] = useState("trial"); // trial | premium | vip

  const messages = [
    { id: 1, text: "Unleash your true power — trade with precision.", segments: ["all"] },
    { id: 2, text: "VIP weekly signals released.", segments: ["vip"] },
    { id: 3, text: "Live lesson uploaded: Price Action Mastery.", segments: ["premium", "vip"] },
    { id: 4, text: "Premium & VIP monthly challenge — join now!", segments: ["premium", "vip"] },
    { id: 5, text: "VIP 1:1 mentorship available.", segments: ["vip"] }
  ];
  const visibleMessages = messages.filter(
    (m) => m.segments.includes("all") || m.segments.includes(mode)
  );

  return (
    <main className="flex-grow bg-gray-900">
      <div className="app-content container mx-auto px-6 py-12 text-white">
        <h1 className="text-4xl font-extrabold mb-4">
          KINGSBALFX — Forex Mentorship & VIP Signals
        </h1>
        <p className="text-gray-300 mb-6">
          Learn professional forex trading, join challenges, receive weekly signals and get 1:1 mentorship.
        </p>

        <div className="flex gap-3 mb-6">
          <button
            onClick={() => setMode("trial")}
            className={`px-4 py-2 rounded-full ${
              mode === "trial"
                ? "bg-yellow-400 text-black"
                : "bg-transparent border border-yellow-400 text-yellow-400"
            }`}
          >
            Free Trial
          </button>
          <button
            onClick={() => setMode("premium")}
            className={`px-4 py-2 rounded-full ${
              mode === "premium"
                ? "bg-blue-500 text-white"
                : "bg-transparent border border-blue-500 text-blue-300"
            }`}
          >
            Premium
          </button>
          <button
            onClick={() => setMode("vip")}
            className={`px-4 py-2 rounded-full ${
              mode === "vip"
                ? "bg-purple-600 text-white"
                : "bg-transparent border border-purple-600 text-purple-300"
            }`}
          >
            VIP
          </button>
        </div>

        <div className="grid gap-4">
          {visibleMessages.map((m) => (
            <div key={m.id} className="p-4 bg-gray-800 rounded">
              {m.text}
            </div>
          ))}
        </div>

        <section className="mt-12 relative overflow-hidden rounded-2xl border border-indigo-500/30 bg-gradient-to-br from-slate-950 via-indigo-950/60 to-black p-8">
          <div className="absolute -top-24 -right-24 h-64 w-64 rounded-full bg-indigo-500/20 blur-3xl" />
          <div className="absolute -bottom-28 -left-16 h-64 w-64 rounded-full bg-yellow-400/10 blur-3xl" />

          <div className="relative grid gap-8 md:grid-cols-[1.1fr_0.9fr] items-center">
            <div>
              <div className="inline-flex items-center gap-2 rounded-full border border-yellow-400/40 bg-yellow-400/10 px-3 py-1 text-xs uppercase tracking-widest text-yellow-300">
                Bot Trading Engine
              </div>
              <h2 className="mt-4 text-3xl md:text-4xl font-bold leading-tight">
                Automated entries, disciplined risk, and live signal delivery.
              </h2>
              <p className="mt-4 text-gray-300">
                Our bot combines ICT structure with tiered signal quality, protecting your capital while
                hunting high-probability setups. Premium and VIP members unlock stronger filters, higher
                trade limits, and priority execution logic.
              </p>

              <div className="mt-6 grid gap-3 sm:grid-cols-3">
                <div className="rounded-xl border border-white/10 bg-black/40 p-4">
                  <div className="text-xs text-gray-400">Signal Quality</div>
                  <div className="mt-1 text-lg font-semibold text-white">Tiered AI Scoring</div>
                </div>
                <div className="rounded-xl border border-white/10 bg-black/40 p-4">
                  <div className="text-xs text-gray-400">Trade Limits</div>
                  <div className="mt-1 text-lg font-semibold text-white">Smart Risk Caps</div>
                </div>
                <div className="rounded-xl border border-white/10 bg-black/40 p-4">
                  <div className="text-xs text-gray-400">Execution</div>
                  <div className="mt-1 text-lg font-semibold text-white">Real-time Alerts</div>
                </div>
              </div>

              <div className="mt-6 flex flex-wrap gap-3">
                <Link href="/pricing">
                  <a className="px-5 py-3 rounded-lg bg-indigo-600 text-white font-semibold hover:bg-indigo-700 transition">
                    Explore Bot Plans
                  </a>
                </Link>
                <Link href="/register">
                  <a className="px-5 py-3 rounded-lg border border-yellow-400/60 text-yellow-200 hover:bg-yellow-400/10 transition">
                    Start Free Trial
                  </a>
                </Link>
              </div>
            </div>

            <div className="grid gap-4">
              <div className="rounded-2xl border border-indigo-500/20 bg-black/40 p-6">
                <div className="text-sm text-indigo-200">What you get</div>
                <ul className="mt-4 space-y-2 text-sm text-gray-300">
                  <li>Live bot signals with clear SL/TP targets</li>
                  <li>Risk-protected entries based on liquidity sweeps</li>
                  <li>Weekly performance summaries and market breakdowns</li>
                </ul>
              </div>
              <div className="rounded-2xl border border-yellow-400/20 bg-gradient-to-br from-yellow-500/10 to-transparent p-6">
                <div className="text-sm text-yellow-200">Pro Tip</div>
                <p className="mt-3 text-sm text-gray-200">
                  Combine the bot with mentorship sessions to fast-track consistency and decision-making.
                </p>
              </div>
            </div>
          </div>
        </section>

        <div className="mt-12 text-center">
          <Link href="/register">
            <a className="px-6 py-3 bg-indigo-600 text-white font-semibold rounded shadow hover:bg-indigo-700 transition">
              Join Now
            </a>
          </Link>
        </div>
      </div>
    </main>
  );
}
