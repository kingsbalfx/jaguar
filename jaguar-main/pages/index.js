// pages/index.js
import React, { useState } from "react";
import Link from "next/link";
import AdSense from "../components/AdSense";

export default function Home() {
  const [mode, setMode] = useState("trial"); // trial | premium | vip

  const messages = [
    { id: 1, text: "Precision entries. Disciplined exits. Every signal measured.", segments: ["all"] },
    { id: 2, text: "VIP weekly signals are live with full trade walkthroughs.", segments: ["vip"] },
    { id: 3, text: "New lesson drop: Market Structure & Liquidity Sweeps.", segments: ["premium", "vip"] },
    { id: 4, text: "Premium & VIP challenge starts this week — join the desk.", segments: ["premium", "vip"] },
    { id: 5, text: "VIP 1:1 mentorship slots open for serious traders.", segments: ["vip"] }
  ];
  const visibleMessages = messages.filter(
    (m) => m.segments.includes("all") || m.segments.includes(mode)
  );

  return (
    <main className="flex-grow app-bg text-white">
      <div className="app-content container mx-auto px-6 py-14">
        <div className="grid gap-10 lg:grid-cols-[1.1fr_0.9fr] items-center">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-indigo-500/40 bg-indigo-500/10 px-3 py-1 text-xs uppercase tracking-widest text-indigo-200">
              KingsBalfx Trading Lab
            </div>
            <h1 className="display-font mt-4 text-4xl md:text-6xl font-bold leading-tight">
              Forex mentorship, live signals, and a bot engine built for consistency.
            </h1>
            <p className="mt-4 text-lg text-gray-300 max-w-2xl">
              Build your edge with guided ICT strategy, disciplined risk controls, and signals tuned
              to your tier. Every plan delivers actionable setups, clean execution, and a clear
              growth path.
            </p>
            <div className="mt-6 flex flex-wrap gap-3">
              <Link href="/pricing">
                <a className="px-6 py-3 rounded-lg text-white font-semibold btn-primary">
                  View Pricing
                </a>
              </Link>
              <Link href="/register">
                <a className="px-6 py-3 rounded-lg text-white/90 btn-outline">
                  Start Free Trial
                </a>
              </Link>
            </div>
            <div className="mt-8 grid gap-4 sm:grid-cols-3">
              <div className="glass-panel rounded-2xl p-4">
                <div className="text-xs text-gray-400">Signals / Day</div>
                <div className="mt-2 text-lg font-semibold">Up to 30+</div>
              </div>
              <div className="glass-panel rounded-2xl p-4">
                <div className="text-xs text-gray-400">Bot Risk Caps</div>
                <div className="mt-2 text-lg font-semibold">Tier‑Based</div>
              </div>
              <div className="glass-panel rounded-2xl p-4">
                <div className="text-xs text-gray-400">Mentorship</div>
                <div className="mt-2 text-lg font-semibold">Weekly Live</div>
              </div>
            </div>
          </div>

          <div className="glass-panel rounded-3xl p-6 relative overflow-hidden">
            <div className="absolute -top-20 -right-24 h-48 w-48 rounded-full bg-indigo-500/20 blur-3xl" />
            <div className="absolute -bottom-24 -left-16 h-48 w-48 rounded-full bg-yellow-400/10 blur-3xl" />
            <div className="relative space-y-4">
              <div className="text-sm text-indigo-200">Live Bot Snapshot</div>
              <div className="rounded-2xl border border-white/10 bg-black/50 p-4">
                <div className="text-xs text-gray-400">Signal Quality</div>
                <div className="mt-1 text-xl font-semibold">Premium Confidence</div>
                <p className="mt-2 text-sm text-gray-300">
                  Filters tuned to liquidity sweeps, structure shifts, and HTF momentum.
                </p>
              </div>
              <div className="rounded-2xl border border-white/10 bg-black/50 p-4">
                <div className="text-xs text-gray-400">Execution Layer</div>
                <div className="mt-1 text-xl font-semibold">Risk‑Locked Entries</div>
                <p className="mt-2 text-sm text-gray-300">
                  Dynamic lot sizing with max‑trade guards and tiered exposure rules.
                </p>
              </div>
              <div className="rounded-2xl border border-white/10 bg-black/50 p-4">
                <div className="text-xs text-gray-400">Community</div>
                <div className="mt-1 text-xl font-semibold">Mentor‑Led Rooms</div>
                <p className="mt-2 text-sm text-gray-300">
                  Daily breakdowns, session recaps, and accountability check‑ins.
                </p>
              </div>
            </div>
          </div>
        </div>

        <section className="mt-12">
          <div className="flex flex-wrap gap-3 mb-6">
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

          <div className="grid gap-4 md:grid-cols-2">
            {visibleMessages.map((m) => (
              <div key={m.id} className="glass-panel rounded-2xl p-4">
                {m.text}
              </div>
            ))}
          </div>

          {mode === "trial" && (
            <div className="mt-8 rounded-2xl border border-yellow-400/30 bg-yellow-500/5 p-4">
              <div className="text-xs uppercase tracking-widest text-yellow-300 mb-2">
                Sponsored
              </div>
              <AdSense slot="1636184407" />
            </div>
          )}
        </section>

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
                Our bot blends ICT structure with tiered signal quality, protecting your capital while
                hunting high‑probability setups. Premium and VIP unlock stronger filters, higher
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
                  <div className="mt-1 text-lg font-semibold text-white">Real‑time Alerts</div>
                </div>
              </div>

              <div className="mt-6 flex flex-wrap gap-3">
                <Link href="/pricing">
                  <a className="px-5 py-3 rounded-lg text-white font-semibold btn-primary">
                    Explore Bot Plans
                  </a>
                </Link>
                <Link href="/register">
                  <a className="px-5 py-3 rounded-lg text-yellow-200 border border-yellow-400/60 hover:bg-yellow-400/10 transition">
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
                  Combine the bot with mentorship sessions to fast‑track consistency and decision‑making.
                </p>
              </div>
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}
