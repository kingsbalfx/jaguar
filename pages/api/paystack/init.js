// pages/api/paystack/initiate.js
import fetch from "node-fetch";
import { createPagesServerClient } from "@supabase/auth-helpers-nextjs";

const PLANS = {
  vip: { price: 150000, name: "VIP Access" },       // ₦150,000
  premium: { price: 90000, name: "Premium Access" } // ₦90,000
};

export default async function handler(req, res) {
  if (req.method !== "POST") return res.status(405).end();

  const supabase = createPagesServerClient({ req, res });

  // get supabase session (user must be signed in)
  const { data: { session }, error: sessionError } = await supabase.auth.getSession();
  if (sessionError || !session?.user) {
    return res.status(401).json({ error: "Not authenticated" });
  }
  const user = session.user;

  const { plan } = req.body || {};
  if (!plan || !PLANS[plan]) return res.status(400).json({ error: "Invalid plan" });

  const amount = PLANS[plan].price;
  const email = user.email;

  try {
    // Initialize Paystack transaction from server
    const initRes = await fetch("https://api.paystack.co/transaction/initialize", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${process.env.PAYSTACK_SECRET_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        email,
        amount: amount * 100, // Paystack expects kobo (so multiply Naira by 100)
        metadata: {
          userId: user.id,
          plan,
        },
        // You can optionally set callback_url here, Paystack will still redirect to the callback on the dashboard settings
        callback_url: `${process.env.NEXT_PUBLIC_SITE_URL || `https://${process.env.NEXT_PUBLIC_VERCEL_URL}`}/api/paystack/verify`
      }),
    });

    const json = await initRes.json();
    if (!initRes.ok) {
      console.error("Paystack init error", json);
      return res.status(500).json({ error: "Paystack initialization failed", details: json });
    }

    // Return authorization_url to client to redirect user
    return res.status(200).json({ authorization_url: json.data.authorization_url, reference: json.data.reference });
  } catch (err) {
    console.error("paystack/initiate error", err);
    return res.status(500).json({ error: "Server error" });
  }
}
