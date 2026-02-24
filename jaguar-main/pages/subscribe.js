import { useState } from "react";
import { PRICING_TIERS, formatPrice } from "../lib/pricing-config";

export default function Subscribe() {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [termsAccepted, setTermsAccepted] = useState(false);

  async function handleSubscribe(e) {
    e.preventDefault();
    if (!termsAccepted) {
      setError("Please accept the Terms & Refund Policy before continuing.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const lifetime = PRICING_TIERS.LIFETIME;
      const plan = lifetime.id;
      const resp = await fetch("/api/korapay/init", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, plan, termsAccepted: true }),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data?.error || "init failed");
      // redirect to Korapay checkout url
      const url = data?.checkout_url || data?.authorization_url || data?.data?.checkout_url;
      if (url) window.location.href = url;
      else throw new Error("No authorization URL returned");
    } catch (e) {
      setError(e.message || String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
      <main className="container mx-auto p-6">
        <h1 className="text-2xl font-bold mb-4">Purchase Lifetime Bot Access</h1>
      <form onSubmit={handleSubscribe} className="max-w-md">
        <label className="block mb-2">Email</label>
        <input value={email} onChange={(e) => setEmail(e.target.value)} required className="w-full p-2 rounded bg-white/5 mb-3" />
        <div className="mb-3 text-gray-300">
          Price: {formatPrice(PRICING_TIERS.LIFETIME.price, PRICING_TIERS.LIFETIME.currency)} (one-time lifetime)
        </div>
        <div className="mb-4 rounded-lg border border-white/10 bg-black/40 p-3 text-sm text-gray-300">
          <div className="font-semibold mb-2">Refund Policy (Summary)</div>
          <ul className="list-disc pl-5 space-y-1">
            <li>Refunds are only considered if you have not benefited or used the service.</li>
            <li>You must request a refund within 7 days of payment.</li>
            <li>After 7 days, refunds are not allowed.</li>
            <li>If any usage or benefit is detected, refunds are not granted.</li>
          </ul>
          <div className="mt-3 flex items-start gap-2">
            <input
              id="termsAcceptedSubscribe"
              type="checkbox"
              className="mt-1"
              checked={termsAccepted}
              onChange={(e) => setTermsAccepted(e.target.checked)}
            />
            <label htmlFor="termsAcceptedSubscribe" className="text-gray-200">
              I agree to the Terms & Refund Policy.{" "}
              <a className="text-indigo-300 underline" href="/terms" target="_blank" rel="noreferrer">
                Read full terms
              </a>
            </label>
          </div>
        </div>
        <button disabled={loading} className="px-4 py-2 bg-green-600 text-white rounded">
          {loading ? "Processing..." : "Buy Lifetime Access"}
        </button>
        {error && <div className="mt-3 text-red-400">{error}</div>}
      </form>
    </main>
  );
}
