// pages/api/paystack/initiate.js
import fetch from "node-fetch";
import { getSupabaseClient } from "../../../lib/supabaseClient";

const PLANS = {
  vip: { price: 150000, name: "VIP Access" }, // ₦150,000
  premium: { price: 70000, name: "Premium Access" }, // ₦70,000 (updated per request)
};

export default async function handler(req, res) {
  if (req.method !== "POST") return res.status(405).end();

  // Option A: if you want to require logged-in user with session cookie,
  // use @supabase/auth-helpers-nextjs createPagesServerClient (recommended).
  // Option B (this file): use server factory. It won't parse session cookies,
  // so this endpoint expects the client to POST { plan } while the server
  // will return authorization_url. Adjust as needed.

  const plan = req.body?.plan;
  if (!plan || !PLANS[plan]) return res.status(400).json({ error: "Invalid plan" });

  const amount = PLANS[plan].price;
  const buyerEmail = req.body?.email || null;
  if (!buyerEmail) {
    // if you require the user to be authenticated server-side, change this behavior
    return res.status(400).json({ error: "Buyer email required" });
  }

  try {
    const initRes = await fetch("https://api.paystack.co/transaction/initialize", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${process.env.PAYSTACK_SECRET_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        email: buyerEmail,
        amount: amount * 100, // kobo
        metadata: { plan, email: buyerEmail },
        callback_url: `${process.env.NEXT_PUBLIC_SITE_URL || `https://${process.env.NEXT_PUBLIC_VERCEL_URL}`}/api/paystack/verify`,
      }),
    });

    const json = await initRes.json();
    if (!initRes.ok) {
      console.error("Paystack init error", json);
      return res.status(500).json({ error: "Paystack initialization failed", details: json });
    }

    return res.status(200).json({ authorization_url: json.data.authorization_url, reference: json.data.reference });
  } catch (err) {
    console.error("paystack/initiate error", err);
    return res.status(500).json({ error: "Server error" });
  }
}
