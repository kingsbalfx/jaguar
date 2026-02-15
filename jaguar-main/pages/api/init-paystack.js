import fetch from "node-fetch";

export default async function handler(req, res) {
  if (req.method !== "POST") return res.status(405).end();

  const { email, amount, metadata } = req.body || {};
  if (!email || !amount) return res.status(400).json({ error: "email and amount required" });

  const secret = process.env.PAYSTACK_SECRET_KEY;
  if (!secret) return res.status(500).json({ error: "paystack secret not configured" });

  try {
    const resp = await fetch("https://api.paystack.co/transaction/initialize", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${secret}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ email, amount: Number(amount), metadata: metadata || {} }),
    });

    const data = await resp.json();
    if (!resp.ok) {
      return res.status(resp.status).json({ error: data });
    }
    return res.status(200).json(data);
  } catch (e) {
    return res.status(500).json({ error: e.message || String(e) });
  }
}
