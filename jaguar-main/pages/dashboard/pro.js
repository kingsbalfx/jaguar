// pages/dashboard/pro.js
import React, { useState } from "react";
import dynamic from "next/dynamic";
import PriceButton from "../../components/PriceButton";
import { PRICING_TIERS, formatPrice } from "../../lib/pricing-config";

const ReactPlayer = dynamic(() => import("react-player"), { ssr: false });

export default function ProDashboard() {
  const [useTwilio, setUseTwilio] = useState(false);
  const tier = PRICING_TIERS.PRO;
  const priceLabel = formatPrice(tier.price, tier.currency || "NGN");

  return (
    <main className="container mx-auto px-6 py-8 text-white">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold">Pro Dashboard</h2>
        <div className="text-right">
          <div className="text-sm text-gray-400">Access price</div>
          <div className="text-xl font-semibold text-yellow-300">{priceLabel}</div>
          <div className="mt-2 flex items-center gap-3">
            <a href={`/checkout?plan=pro`} className="px-3 py-2 bg-indigo-600 rounded">
              Checkout
            </a>
            <PriceButton initialPrice={tier.price} plan="pro" />
          </div>
        </div>
      </div>

      <div className="flex gap-4 mb-4">
        <button className="px-4 py-2 bg-indigo-600 rounded" onClick={() => setUseTwilio(false)}>
          Watch YouTube
        </button>
        <button className="px-4 py-2 bg-green-600 rounded" onClick={() => setUseTwilio(true)}>
          Join Twilio Live
        </button>
      </div>

      {!useTwilio ? (
        <div className="grid md:grid-cols-2 gap-6">
          <div className="p-4 bg-gray-800 rounded">
            <h3 className="font-semibold mb-2">Live Video (YouTube)</h3>
            <div className="bg-black/40 p-2 rounded">
              <ReactPlayer url="https://www.youtube.com/watch?v=dQw4w9WgXcQ" controls width="100%" />
            </div>
          </div>
          <div className="p-4 bg-gray-800 rounded">
            <h3 className="font-semibold mb-2">Pro Lesson Library</h3>
            <p className="text-gray-300">Advanced strategies, deep dives, and 1:1 mentorship resources.</p>
          </div>
        </div>
      ) : (
        <div className="p-4 bg-gray-800 rounded">
          <h3 className="font-semibold mb-2">Twilio Live</h3>
          <div className="text-gray-400">Twilio stream placeholder</div>
        </div>
      )}
    </main>
  );
}
