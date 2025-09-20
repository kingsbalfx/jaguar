// components/PriceButton.jsx
import React, { useState } from "react";

export default function PriceButton({ initialPrice = null, plan = "vip" }) {
  const [visible, setVisible] = useState(Boolean(initialPrice));
  const [price, setPrice] = useState(initialPrice);
  const [loading, setLoading] = useState(false);

  const handleToggle = async () => {
    if (price) {
      setVisible((v) => !v);
      return;
    }
    setLoading(true);
    try {
      // Optionally fetch the price from server if needed:
      const res = await fetch(`/api/price?plan=${encodeURIComponent(plan)}`);
      if (!res.ok) throw new Error("Failed to fetch price");
      const json = await res.json();
      setPrice(json?.price ?? null);
      setVisible(true);
    } catch (err) {
      alert(err?.message || "Could not load price");
    } finally {
      setLoading(false);
    }
  };

  const formatted = price
    ? new Intl.NumberFormat("en-NG", { style: "currency", currency: "NGN", maximumFractionDigits: 0 }).format(price)
    : null;

  return (
    <div>
      <button
        onClick={handleToggle}
        className="px-4 py-2 rounded bg-yellow-500 text-black font-semibold hover:bg-yellow-400"
      >
        {loading ? "Loading..." : price ? (visible ? "Hide Price" : "Show Price") : "Show Price"}
      </button>

      {visible && price && (
        <div className="mt-2 text-yellow-300 font-bold">
          Access price: {formatted}
          <div className="mt-2">
            <a
              href={`/checkout?plan=${encodeURIComponent(plan)}`}
              className="inline-block px-3 py-2 bg-indigo-600 rounded text-white"
            >
              Purchase Access
            </a>
          </div>
        </div>
      )}
    </div>
  );
}
