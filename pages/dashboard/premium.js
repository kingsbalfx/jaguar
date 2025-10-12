// pages/dashboard/premium.js
import React, { useState } from "react";
import Header from "../../components/Header";
import Footer from "../../components/Footer";
import dynamic from "next/dynamic";
import PriceButton from "../../components/PriceButton";

const ReactPlayer = dynamic(() => import("react-player"), { ssr: false });
const PRICE_PREMIUM_NGN = 70000;

export default function PremiumDashboard() {
  const [useTwilio, setUseTwilio] = useState(false);
  const priceFormatter = new Intl.NumberFormat("en-NG", { style: "currency", currency: "NGN", maximumFractionDigits: 0 });

  return (
    <>
      <Header />
      <main className="container mx-auto px-6 py-8 text-white">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-2xl font-bold">Premium Dashboard</h2>
          <div className="text-right">
            <div className="text-sm text-gray-400">Access price</div>
            <div className="text-xl font-semibold text-yellow-300">{priceFormatter.format(PRICE_PREMIUM_NGN)}</div>
            <div className="mt-2 flex items-center gap-3">
              <a href={`/checkout?plan=premium`} className="px-3 py-2 bg-indigo-600 rounded">Checkout</a>
              <PriceButton initialPrice={PRICE_PREMIUM_NGN} plan="premium" />
            </div>
          </div>
        </div>

        <div className="flex gap-4 mb-4">
          <button className="px-4 py-2 bg-indigo-600 rounded" onClick={() => setUseTwilio(false)}>Watch YouTube</button>
          <button className="px-4 py-2 bg-green-600 rounded" onClick={() => setUseTwilio(true)}>Join Twilio Live</button>
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
              <h3 className="font-semibold mb-2">Latest Lesson</h3>
              <p className="text-gray-300">Video, documents and audio uploads are accessible here.</p>
            </div>
          </div>
        ) : (
          <div className="p-4 bg-gray-800 rounded">
            <h3 className="font-semibold mb-2">Twilio Live</h3>
            <div className="text-gray-400">Twilio stream placeholder</div>
          </div>
        )}
      </main>
      <Footer />
    </>
  );
}