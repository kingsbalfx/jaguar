import { useState } from "react";

export default function Subscribe() {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  async function handleSubscribe(e) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      // amount in kobo (NGN) or lowest currency unit
      const amount = 500000; // e.g., NGN 5,000.00 -> 500000 kobo
      const resp = await fetch("/api/init-paystack", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, amount }),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data?.error || "init failed");
      // redirect to Paystack authorization_url
      const url = data?.data?.authorization_url;
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
        <div className="mb-3 text-gray-300">Price: NGN 5,000 (one-time lifetime)</div>
        <button disabled={loading} className="px-4 py-2 bg-green-600 text-white rounded">
          {loading ? "Processing..." : "Buy Lifetime Access"}
        </button>
        {error && <div className="mt-3 text-red-400">{error}</div>}
      </form>
    </main>
  );
}
