import React, { useState } from "react";
import Link from "next/link";
import AdSense from "../components/AdSense";

export default function Home() {
  const [mode, setMode] = useState("trial"); // trial | premium | vip

  // messages with segment tags to control visibility
  const messages = [
    {
      id: 1,
      text: "Unleash your true power — trade with precision.",
      segments: ["all"]
    },
    {
      id: 2,
      text: "VIP weekly signals released.",
      segments: ["vip"]
    },
    {
      id: 3,
      text: "Live lesson uploaded: Price Action Mastery.",
      segments: ["premium", "vip"]
    },
    {
      id: 4,
      text: "Premium & VIP monthly challenge — join now!",
      segments: ["premium", "vip"]
    },
    {
      id: 5,
      text: "VIP 1:1 mentorship available.",
      segments: ["vip"]
    }
  ];

  // filter messages based on selected mode
  const visibleMessages = messages.filter((m) =>
    m.segments.includes("all") || m.segments.includes(mode)
  );

  return (
    <>
      <Header />
      <main className="container mx-auto px-6 py-12">
        <div className="grid md:grid-cols-2 gap-8 items-center">
          <div>
            <h1 className="text-4xl font-extrabold mb-4">
              KINGSBALFX — Forex Mentorship & VIP Signals
            </h1>
            <p className="text-gray-300 mb-6">
              Learn professional forex trading, join challenges, receive weekly
              signals and get 1:1 mentorship.
            </p>

            <div className="flex gap-3 mb-6">
              <button
                onClick={() => setMode("trial")}
                className={
                  "px-4 py-2 rounded-full " +
                  (mode === "trial"
                    ? "bg-yellow-400 text-black"
                    : "bg-transparent border border-yellow-400 text-yellow-400")
                }
              >
                Free Trial
              </button>
              <button
                onClick={() => setMode("premium")}
                className={
                  "px-4 py-2 rounded-full " +
                  (mode === "premium"
                    ? "bg-blue-500 text-white"
                    : "bg-transparent border border-blue-500 text-blue-300")
                }
              >
                Premium
              </button>
              <button
                onClick={() => setMode("vip")}
                className={
                  "px-4 py-2 rounded-full " +
                  (mode === "vip"
                    ? "bg-purple-600 text-white"
                    : "bg-transparent border border-purple-600 text-purple-300")
                }
              >
                VIP
              </button>
            </div>

            <div className="mb-6">
              <h3 className="font-bold">Selected: {mode.toUpperCase()}</h3>
              <p className="text-gray-300">
                Click continue to register with Gmail and complete subscription
                flow.
              </p>
            </div>

            <div className="flex gap-4">
              <Link
                href={`/register?plan=${mode}`}
                className="px-6 py-3 bg-green-600 rounded-xl shadow"
              >
                Continue with Gmail
              </Link>
              <a className="px-6 py-3 bg-gray-800 rounded-xl border border-gray-600">
                Watch Trial Video
              </a>
            </div>
          </div>

          <div>
            <div className="bg-black/30 p-6 rounded-lg">
              <h4 className="font-semibold mb-2">Why join KINGSBALFX?</h4>
              <ul className="list-disc ml-5 text-gray-300">
                <li>Weekly trading signals</li>
                <li>VIP-only challenges</li>
                <li>Live video lessons and uploads</li>
                <li>Community chat segmented for premium & VIP</li>
              </ul>

              <div className="mt-6 space-y-4">
                {/* Ad box (keeps AdSense here only) */}
                <div className="bg-gray-900 p-4 rounded">
                  <div className="text-sm text-gray-400">Advertisement</div>
                  <div className="mt-2 text-gray-300">
                    <AdSense slot="PUT_HOME_SLOT_ID_IF_ANY" />
                  </div>
                </div>

                {/* Community Chat fancy block */}
                <div className="bg-gradient-to-br from-slate-900/70 to-black/70 p-4 rounded ring-2 ring-yellow-400/20">
                  <div className="flex items-center justify-between">
                    <div>
                      <h5 className="text-yellow-300 font-extrabold tracking-wide uppercase text-sm">
                        UNLEASH YOUR TRUE POWER
                      </h5>
                      <p className="text-xs text-gray-400 mt-1">
                        Community chat (premium & VIP segments)
                      </p>
                    </div>
                    {/* small pulse indicator */}
                    <div className="ml-4">
                      <span className="inline-block relative">
                        <span className="absolute inline-flex h-3 w-3 rounded-full bg-yellow-400 opacity-70 animate-ping" />
                        <span className="relative inline-block h-3 w-3 rounded-full bg-yellow-400" />
                      </span>
                    </div>
                  </div>

                  {/* animated messages */}
                  <div className="mt-4 space-y-2 overflow-hidden">
                    {visibleMessages.map((m, i) => (
                      <div
                        key={m.id}
                        className="flex items-center gap-3"
                        aria-hidden={false}
                      >
                        <div
                          className="px-3 py-1 rounded-full text-xs font-semibold"
                          style={{
                            boxShadow:
                              "0 0 10px rgba(250,204,21,0.08), 0 0 20px rgba(99,102,241,0.03)",
                            background:
                              "linear-gradient(90deg, rgba(250,204,21,0.06), rgba(99,102,241,0.03))"
                          }}
                        >
                          <span className="text-yellow-300">{`#${m.id}`}</span>
                        </div>

                        <div className="flex-1">
                          <span
                            className="text-sm font-medium bg-clip-text text-transparent"
                            style={{
                              background:
                                "linear-gradient(90deg, #facc15, #8b5cf6, #06b6d4)",
                              WebkitBackgroundClip: "text",
                              textShadow:
                                "0 0 8px rgba(139,92,246,0.12), 0 0 12px rgba(6,182,212,0.06)",
                              animation: `glowBlink ${2.6 + (i % 3) * 0.25}s ease-in-out ${
                                i * 0.12
                              }s infinite`
                            }}
                          >
                            {m.text}
                          </span>
                        </div>

                        <div
                          className="w-2 h-2 rounded-full"
                          style={{
                            background:
                              "radial-gradient(circle at 30% 30%, #fff6d8, #f59e0b 30%, #7c3aed 70%)",
                            boxShadow: "0 0 8px rgba(245,158,11,0.5)"
                          }}
                        />
                      </div>
                    ))}
                  </div>
                </div>

                {/* Messages / Notifications (admin editable) */}
                <div className="mt-2">
                  <h5 className="font-semibold">Messages / Notifications</h5>
                  <div className="text-sm text-gray-300">
                    Admin-editable messages will appear here. Manage them from
                    Admin Panel.
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </main>
      <Footer />

      {/* local styles for the glowing/blinking animation */}
      <style jsx>{`
        @keyframes glowBlink {
          0% {
            opacity: 0.65;
            filter: blur(0px);
            transform: translateY(0);
          }
          40% {
            opacity: 1;
            filter: blur(0.6px);
            transform: translateY(-1px);
          }
          100% {
            opacity: 0.7;
            filter: blur(0px);
            transform: translateY(0);
          }
        }
      `}</style>
    </>
  );
}
