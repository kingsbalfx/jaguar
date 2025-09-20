// pages/dashboard/premium.js
import React, { useState } from "react";
import Header from "../../components/Header";
import Footer from "../../components/Footer";
import dynamic from "next/dynamic";
import PriceButton from "../components/PriceButton";

const ReactPlayer = dynamic(() => import("react-player"), { ssr: false });
const TwilioVideoClient = dynamic(
  () => import("../../components/TwilioVideoClient"),
  { ssr: false }
);

export default function PremiumDashboard() {
  const PRICE_PREMIUM_NGN = 70000;
  const priceFormatter = new Intl.NumberFormat("en-NG", {
    style: "currency",
    currency: "NGN",
    maximumFractionDigits: 0,
  });

  const [useTwilio, setUseTwilio] = useState(false);

  return (
    <>
      <Header />
      <main className="container mx-auto px-6 py-8">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-2xl font-bold">Premium Dashboard</h2>
          <div className="text-right">
            <div className="text-sm text-gray-400">Access price</div>
            <div className="text-lg font-semibold text-yellow-300">
              {priceFormatter.format(PRICE_PREMIUM_NGN)}
            </div>
            <a
              href={`/checkout?plan=premium`}
              className="mt-2 inline-block px-3 py-2 bg-indigo-600 rounded text-white"
            >
              Purchase Access
            </a>
          </div>
        </div>

        <div className="flex gap-4 mb-4">
          <button
            className="px-4 py-2 bg-indigo-600 rounded"
            onClick={() => setUseTwilio(false)}
          >
            Watch YouTube
          </button>
          <button
            className="px-4 py-2 bg-green-600 rounded"
            onClick={() => setUseTwilio(true)}
          >
            Join Twilio Live
          </button>
        </div>

        {!useTwilio ? (
          <div className="grid md:grid-cols-2 gap-6">
            <div className="p-4 bg-black/20 rounded">
              <h3 className="font-semibold mb-2">Live Video (YouTube)</h3>
              <div className="bg-black/40 p-2 rounded">
                <ReactPlayer
                  url="https://www.youtube.com/watch?v=dQw4w9WgXcQ"
                  controls
                  width="100%"
                />
              </div>
            </div>

            <div className="p-4 bg-black/20 rounded">
              <h3 className="font-semibold mb-2">Latest Lesson</h3>
              <p className="text-gray-300">
                Video, documents, images and audio uploads are accessible here.
              </p>
            </div>
          </div>
        ) : (
          <div className="p-4 bg-black/20 rounded">
            <h3 className="font-semibold mb-2">Twilio Live (Premium)</h3>
            <TwilioVideoClient />
          </div>
        )}
      </main>
      <Footer />
    </>
  );
}

