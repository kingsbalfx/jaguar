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