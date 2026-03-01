// pages/checkout/index.js
import { useEffect, useState } from "react";
import { useRouter } from "next/router";
import { PRICING_TIERS, formatPrice } from "../../lib/pricing-config";
import { getBrowserSupabaseClient, isSupabaseConfigured } from "../../lib/supabaseClient";

const TIERS = Object.values(PRICING_TIERS);

export default function Checkout() {
  const router = useRouter();
  const planQuery = Array.isArray(router.query.plan)
    ? router.query.plan[0]
    : router.query.plan;
  const plan = planQuery ? planQuery.toString().toLowerCase() : "vip";
  const tier = TIERS.find((t) => t.id === plan) || PRICING_TIERS.VIP;
  const amount = tier?.price ?? 0;
  const priceLabel = formatPrice(amount, tier?.currency || "NGN");
  const isFree = !amount || amount <= 0;

  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [termsAccepted, setTermsAccepted] = useState(false);
  const isConfigured = Boolean(isSupabaseConfigured);

  // Prefill email if logged in
  useEffect(() => {
    (async () => {
      try {
        if (!isConfigured) return;
        const client = getBrowserSupabaseClient();
        if (!client) return;
        const { data, error } = await client.auth.getSession();
        if (!error && data?.session?.user?.email) {
          setEmail(data.session.user.email);
        }
      } catch (err) {
        console.debug("prefill session error", err);
      }
    })();
  }, [isConfigured]);

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
    if (isFree) {
      setMessage("This plan is free and does not require checkout.");
      return;
    }
    if (!termsAccepted) {
      setMessage("Please accept the Terms & Refund Policy before continuing.");
      return;
    }
    if (!email) {
      setMessage("Enter buyer email before continuing.");
      return;
    }
    if (!isConfigured) {
      setMessage("Supabase is not configured. Please contact support.");
      return;
    }
    setLoading(true);

    try {
      const client = getBrowserSupabaseClient();
      if (!client) {
        setMessage("Supabase client not available.");
        setLoading(false);
        return;
      }
      const sessionData = await client.auth.getSession();
      const userId = sessionData?.data?.session?.user?.id;

      if (!sessionData?.data?.session) {
        // Not logged in -> redirect to register
        const next = `/checkout?plan=${encodeURIComponent(plan)}`;
        router.push(`/login?next=${encodeURIComponent(next)}`);
        return;
      }

      const payload = { plan, email, userId, termsAccepted: true };

      // Call the Init endpoint (omit the first try since we handle one endpoint)
      const resp = await fetch("/api/korapay/init", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const json = await resp.json();
      if (!resp.ok) {
        throw new Error(json?.error || json?.message || "Payment init failed");
      }

      // Redirect to Korapay checkout
      const checkoutUrl = json.checkout_url || json.authorization_url || json?.data?.checkout_url;
      if (!checkoutUrl) {
        throw new Error("No checkout URL returned from server");
      }
      window.location.href = checkoutUrl;
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
    <main className="app-bg text-white relative overflow-hidden">
      <div className="candle-backdrop" aria-hidden="true" />
      <div className="app-content container mx-auto px-6 py-8">
        <h1 className="text-2xl font-bold mb-4">Checkout</h1>

        <div className="mb-4">
          <div className="text-sm text-gray-400">Selected plan:</div>
        <div className="text-lg font-semibold">{tier?.displayName || plan.toUpperCase()}</div>
      </div>

        <div className="mb-6">
          <div className="text-sm text-gray-400">Price</div>
          <div className="text-2xl font-bold text-yellow-300">
          {priceLabel}
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

        <div className="mb-5 max-w-2xl rounded-xl border border-white/10 bg-black/40 p-4 text-sm text-gray-300">
          <div className="font-semibold mb-2">Refund Policy (Summary)</div>
          <ul className="list-disc pl-5 space-y-1">
            <li>Refunds are only considered if you have not benefited or used the service.</li>
            <li>You must request a refund within 7 days of payment.</li>
            <li>After 7 days, refunds are not allowed.</li>
            <li>If any usage or benefit is detected, refunds are not granted.</li>
          </ul>
          <div className="mt-3 flex items-start gap-2">
            <input
              id="termsAccepted"
              type="checkbox"
              className="mt-1"
              checked={termsAccepted}
              onChange={(e) => setTermsAccepted(e.target.checked)}
            />
            <label htmlFor="termsAccepted" className="text-gray-200">
              I agree to the Terms & Refund Policy.{" "}
              <a className="text-indigo-300 underline" href="/terms" target="_blank" rel="noreferrer">
                Read full terms
              </a>
            </label>
          </div>
        </div>

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
            {loading
              ? "Redirecting..."
              : isFree
              ? "No payment required"
              : `Pay ${priceLabel} (Korapay)`}
          </button>

          <button
            onClick={() => router.push("/")}
            className="px-3 py-2 bg-gray-700 rounded"
          >
            Cancel
          </button>
        </div>
      </div>
    </main>
  );
}
