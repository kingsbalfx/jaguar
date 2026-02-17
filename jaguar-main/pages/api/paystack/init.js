// pages/api/paystack/init.js
import fetch from "node-fetch";
import { getURL } from "../../../lib/getURL";
import { PRICING_TIERS } from "../../../lib/pricing-config";

function getTierById(plan) {
  if (!plan) return null;
  const planId = String(plan).toLowerCase();
  return Object.values(PRICING_TIERS).find((tier) => tier.id === planId) || null;
}

export default async function handler(req, res) {
  if (req.method !== "POST") {
    res.setHeader("Allow", "POST");
    return res.status(405).json({ error: "Method not allowed" });
  }

  const { plan, email, userId } = req.body;
  const tier = getTierById(plan);
  if (!tier) return res.status(400).json({ error: "Invalid plan" });
  if (!email) {
    return res.status(400).json({ error: "Buyer email required" });
  }
  if (!tier.price || tier.price <= 0) {
    return res.status(400).json({ error: "Selected plan is free" });
  }
  const amount = tier.price;

  try {
    const baseUrl = getURL().replace(/\/$/, "");
    // Initialize Paystack transaction
    const initRes = await fetch("https://api.paystack.co/transaction/initialize", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${process.env.PAYSTACK_SECRET_KEY}`, // Use your Paystack secret key
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        email,
        amount: amount * 100, // NGN to kobo (subunit)
        metadata: {
          plan: tier.id,
          planName: tier.name,
          planPrice: tier.price,
          email,
          userId,
        },
        callback_url: `${baseUrl}/checkout/success`,
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
