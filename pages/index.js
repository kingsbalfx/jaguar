import React, { useState } from "react";
import Header from "../components/Header";
import Footer from "../components/Footer";
import Link from "next/link";

export default function Home() {
  const [mode, setMode] = useState("trial"); // trial | premium | vip
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
                className="px-6 py-3 bg-green-600 rounded-xl shadow">
                
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
              <div className="mt-6">
                <div className="bg-gray-900 p-4 rounded">
                  <div className="text-sm text-gray-500">
                    Placeholder for Google Adsense area
                  </div>
                  <div className="mt-2 text-gray-300">
                    Your monetization ad will display here.
                  </div>
                </div>
                <div className="mt-4">
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
    </>
  );
}
