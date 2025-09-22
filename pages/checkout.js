// pages/checkout.js
import { useEffect, useState } from "react";
import { useRouter } from "next/router";
import { createClient } from "@supabase/supabase-js";

const supabase = createClient(process.env.NEXT_PUBLIC_SUPABASE_URL, process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY);

export default function Checkout() {
  const router = useRouter();
  const { plan } = router.query; // ?plan=vip or premium
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!plan) return;
    // ensure user is logged in
    (async () => {
      const { data, error } = await supabase.auth.getSession();
      if (error || !data?.session) {
        // not logged in — send user to register/login and preserve plan in query param
        const base = process.env.NEXT_PUBLIC_SITE_URL || (typeof window !== "undefined" && window.location.origin) || "http://localhost:3000";
        // send to oauth/register with redirect back to /checkout?plan=...
        // easiest: redirect to /register?next=/checkout?plan=...
        router.push(`/register?next=/checkout?plan=${encodeURIComponent(plan)}`);
        return;
      }
      // user is logged in — initialize payment
      try {
        setLoading(true);
        const resp = await fetch("/api/paystack/initiate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ plan }),
        });
        const json = await resp.json();
        if (!resp.ok) throw new Error(json?.error || "Failed to initiate payment");
        // redirect browser to Paystack hosted page
        window.location.href = json.authorization_url;
      } catch (err) {
        console.error("checkout error", err);
        alert(err.message || "Unable to start payment");
      } finally {
        setLoading(false);
      }
    })();
  }, [plan, router]);

  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="text-center">
        {loading ? <p>Starting payment…</p> : <p>Preparing checkout for {plan}</p>}
      </div>
    </div>
  );
}
