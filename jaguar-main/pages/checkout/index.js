// pages/checkout/index.js
import { useEffect, useState } from "react";
import { useRouter } from "next/router";
import { createClient } from "@supabase/supabase-js";
import Header from "../../components/Header";
import Footer from "../../components/Footer";

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
);

// Define prices (in Naira)
const PRICES = {
  vip: 150000,
  premium: 90000,
};

function formatNGN(n) {
  return new Intl.NumberFormat("en-NG", {
    style: "currency",
    currency: "NGN",
    maximumFractionDigits: 0,
  }).format(n);
}

export default function Checkout() {
  const router = useRouter();
  const planQuery = Array.isArray(router.query.plan)
    ? router.query.plan[0]
    : router.query.plan;
  const plan = planQuery ? planQuery.toString().toLowerCase() : "vip";
  const amount = PRICES[plan] ?? 0;

  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");

  // Prefill email if logged in
  useEffect(() => {
    (async () => {
      try {
        const { data, error } = await supabase.auth.getSession();
        if (!error && data?.session?.user?.email) {
          setEmail(data.session.user.email);
        }
      } catch (err) {
        console.debug("prefill session error", err);
      }
    })();
  }, []);

  // If no plan query, default to vip
  useEffect(() => {
    if (!router.isReady) return;
    if (!router.query.plan) {
      router.replace(
        { pathname: "/checkout", query: { plan: "vip" } },
        undefined,
        { shallow: true }
      );
    }
  }, [router.isReady]);

  async function startPayment() {
    setMessage("");
    if (!email) {
      setMessage("Enter buyer email before continuing.");
      return;
    }
    setLoading(true);

    try {
      const sessionData = await supabase.auth.getSession();
      const userId = sessionData?.data?.session?.user?.id;

      if (!sessionData?.data?.session) {
        // Not logged in -> redirect to register
        const next = `/checkout?plan=${encodeURIComponent(plan)}`;
        router.push(`/register?next=${encodeURIComponent(next)}`);
        return;
      }

      const payload = {
        plan,
        amount,
        email,
        userId,
        // No need to send callback here (handled server-side)
      };

      // Call the Init endpoint (omit the first try since we handle one endpoint)
      const resp = await fetch("/api/paystack/init", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const json = await resp.json();
      if (!resp.ok) {
        throw new Error(json?.error || json?.message || "Payment init failed");
      }

      // Redirect to Paystack checkout
      if (!json.authorization_url) {
        throw new Error("No authorization_url returned from server");
      }
      window.location.href = json.authorization_url;
    } catch (err) {
      console.error("checkout error:", err);
      setMessage(err?.message || "Unable to start payment");
      setLoading(false);
    }
  }

  // A simulated payment (for testing)
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

        <div className="mb-4 max-w-md">
          <label className="block text-sm mb-1">Buyer email</label>
          <input
            type="email"
            placeholder="you@example.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full p-3 rounded bg-black/30 border border-gray-700"
          />
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
            onClick={startPayment}
            disabled={loading}
            className="px-4 py-2 bg-yellow-500 text-black rounded"
          >
            {loading ? "Redirecting..." : `Pay ${formatNGN(amount)} (Paystack)`}
          </button>

          <button
            onClick={() => router.push("/")}
            className="px-3 py-2 bg-gray-700 rounded"
          >
            Cancel
          </button>
        </div>
      </main>
      <Footer />
    </>
  );
}
