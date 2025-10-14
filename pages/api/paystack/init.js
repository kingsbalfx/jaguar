// pages/api/paystack/init.js
import fetch from "node-fetch";
import { getSupabaseClient } from "../../lib/supabaseClient";

const PLANS = {
  vip: { price: 150000, name: "VIP Access" },
  premium: { price: 70000, name: "Premium Access" },
};

export default async function handler(req, res) {
  if (req.method !== "POST") {
    return res.status(405).json({ error: "Method not allowed" });
  }

  const { plan, email, userId } = req.body;
  if (!plan || !PLANS[plan]) {
    return res.status(400).json({ error: "Invalid plan" });
  }
  if (!email) {
    return res.status(400).json({ error: "Buyer email required" });
  }
  const amount = PLANS[plan].price;

  try {
    const initRes = await fetch("https://api.paystack.co/transaction/initialize", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${process.env.PAYSTACK_SECRET_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        email,
        amount: amount * 100, // NGN to kobo
        metadata: { plan, email, userId },
        callback_url: `${process.env.NEXT_PUBLIC_SITE_URL}/api/paystack/verify`,
      }),
    });

    const json = await initRes.json();
    if (!initRes.ok) {
      console.error("Paystack init error:", json);
      return res.status(500).json({ error: "Paystack initialization failed", details: json });
    }

    return res.status(200).json({
      authorization_url: json.data.authorization_url,
      reference: json.data.reference,
    });
  } catch (err) {
    console.error("paystack/init exception:", err);
    return res.status(500).json({ error: "Server error" });
  }
}