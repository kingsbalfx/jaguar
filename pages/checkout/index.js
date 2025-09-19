import React, { useState, useEffect } from "react";
import { useRouter } from "next/router";
import Header from "../../components/Header";
import Footer from "../../components/Footer";

const PRICES = {
  vip: 150000,
  premium: 70000,
  default: 0,
};

function formatNGN(n) {
  return new Intl.NumberFormat("en-NG", {
    style: "currency",
    currency: "NGN",
    maximumFractionDigits: 0,
  }).format(n);
}

export default function CheckoutPage() {
  const router = useRouter();
  const { plan: planQuery } = router.query;
  const plan = planQuery ? planQuery.toString().toLowerCase() : "vip";
  const amount = PRICES[plan] ?? PRICES.default;

  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (!planQuery && router.isReady) {
      // If no plan in query, default to vip
      router.replace(
        { pathname: "/checkout", query: { plan: "vip" } },
        undefined,
        { shallow: true }
      );
    }
  }, [planQuery, router]);

  async function handlePaystack() {
    setMessage("");
    if (!email) {
      setMessage("Enter buyer email before continuing (Paystack requires it).");
      return;
    }
    setLoading(true);
    try {
      const res = await fetch("/api/paystack/init", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ plan, amount, email }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data?.message || "Paystack init failed");
      }
      if (data?.authorization_url) {
        window.location.href = data.authorization_url;
      } else {
        throw new Error("No authorization_url returned from /api/paystack/init");
      }
    } catch (err) {
      console.error("Checkout error:", err);
      setMessage(String(err.message || err));
      setLoading(false);
    }
  }

  async function simulate() {
    setMessage("");
    setLoading(true);
    setTimeout(() => {
      setLoading(false);
      router.push(`/checkout/success?plan=${plan}&reference=SIMULATED_${Date.now()}`);
    }, 1200);
  }

  return (
    <>
      <Header />
      <main className="container mx-auto px-6 py-8">
        <h1 className="text-2xl font-bold mb-4">Checkout</h1>
        <div className="mb-4">
          <div className="text-sm text-gray-400">Selected plan:</div>
          <div className="text-lg font-semibold">{plan.toUpperCase()}</div>
        </div>

        <div className="mb-6">
          <div className="text-sm text-gray-400">Price</div>
          <div className="text-2xl font-bold text-yellow-300">
            {formatNGN(amount)}
          </div>
        </div>

        <div className="mb-4">
          <label className="block text-sm mb-1">Buyer email</label>
          <input
            type="email"
            placeholder="you@example.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full p-2 rounded bg-black/30 border border-gray-700"
          />
          <div className="text-xs text-gray-400 mt-1">
            A valid email is recommended for payment receipts.
          </div>
        </div>

        {message && <div className="mb-4 text-red-400">{message}</div>}

        <div className="flex gap-3">
          <button
            onClick={simulate}
            disabled={loading}
            className="px-4 py-2 bg-gray-600 rounded"
          >
            {loading ? "Processing..." : "Simulate payment"}
          </button>
          <button
            onClick={handlePaystack}
            disabled={loading}
            className="px-4 py-2 bg-yellow-500 text-black rounded"
          >
            {loading ? "Redirecting..." : "Pay with Paystack (demo)"}
          </button>
          <button
            onClick={() => router.push("/")}
            className="px-3 py-2 bg-gray-700 rounded"
          >
            Cancel
          </button>
        </div>

        <div className="mt-6 text-sm text-gray-400">
          This is a demo/placeholder checkout. The "Pay with Paystack" button calls <code>/api/paystack/init</code>.
        </div>
      </main>
      <Footer />
    </>
  );
}
