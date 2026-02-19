import React, { useState } from "react";
import { useRouter } from "next/router";
import { supabase } from "../lib/supabaseClient";

export default function PriceButton({ plan = "vip", initialPrice = null }) {
  const [price, setPrice] = useState(initialPrice);
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  const formatted = price
    ? new Intl.NumberFormat("en-NG", { style: "currency", currency: "NGN" }).format(price)
    : null;

  const startPayment = async () => {
    setLoading(true);
    try {
      if (!supabase) {
        alert("Supabase not configured. Set NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY.");
        setLoading(false);
        return;
      }
      const { data } = await supabase.auth.getSession();
      const user = data?.session?.user;
      if (!user) {
        router.push(`/login?next=/checkout?plan=${plan}`);
        return;
      }

      const res = await fetch("/api/paystack/init", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ plan, email: user.email, userId: user.id }),
      });
      const json = await res.json();
      if (!res.ok) throw new Error(json?.error || "Payment init failed");

      window.location.href = json.authorization_url;
    } catch (err) {
      alert(err.message || "Payment error");
    } finally {
      setLoading(false);
    }
  };

  const handleShow = async () => {
    if (price) return;
    setLoading(true);
    try {
      const res = await fetch(`/api/price?plan=${plan}`);
      const data = await res.json();
      setPrice(data.price || 0);
    } catch {
      alert("Could not fetch price");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-2">
      {price ? (
        <>
          <div className="text-yellow-300 font-bold">Access price: {formatted}</div>
          <button
            onClick={startPayment}
            disabled={loading}
            className="px-4 py-2 bg-indigo-600 rounded text-white hover:bg-indigo-500"
          >
            {loading ? "Processing…" : `Pay ${formatted}`}
          </button>
        </>
      ) : (
        <button
          onClick={handleShow}
          disabled={loading}
          className="px-4 py-2 bg-yellow-400 text-black rounded font-semibold hover:bg-yellow-300"
        >
          {loading ? "Loading…" : "Show Price"}
        </button>
      )}
    </div>
  );
}
