// pages/api/paystack/init.js
import axios from "axios";

export default async function handler(req, res) {
  if (req.method !== "POST") {
    return res.status(405).json({ error: "Method not allowed" });
  }

  const { plan, amount, email, reference, callback_url } = req.body ?? {};
  const PAYSTACK_SECRET = process.env.PAYSTACK_SECRET;

  if (!PAYSTACK_SECRET) {
    return res.status(500).json({
      error:
        "Missing PAYSTACK_SECRET in environment. Set PAYSTACK_SECRET in your .env or Vercel env vars.",
    });
  }

  if (!email || !amount) {
    return res
      .status(400)
      .json({ error: "Missing required fields: email and amount" });
  }

  // Ensure numeric amount and convert to kobo (NGN * 100)
  const numericAmount = Number(amount);
  if (Number.isNaN(numericAmount) || numericAmount <= 0) {
    return res.status(400).json({ error: "Invalid amount" });
  }
  const kobo = Math.round(numericAmount * 100);

  // callback_url: prefer caller-provided, otherwise default to /checkout/success on same origin
  const callbackUrl =
    callback_url ?? `${req.headers.origin ?? ""}/checkout/success`;

  const body = {
    email,
    amount: kobo,
    callback_url: callbackUrl,
    metadata: { plan: plan ?? "unknown" },
  };

  // include provided reference if present (optional)
  if (reference) {
    body.reference = reference;
  }

  try {
    const resp = await axios.post(
      "https://api.paystack.co/transaction/initialize",
      body,
      {
        headers: {
          Authorization: `Bearer ${PAYSTACK_SECRET}`,
          "Content-Type": "application/json",
        },
        timeout: 15000,
      }
    );

    // resp.data typically includes { status, message, data: { authorization_url, access_code, reference, ... } }
    const responseData = resp.data ?? {};

    // Return the key fields + raw response for flexibility
    return res.status(200).json({
      ok: true,
      message: responseData.message ?? "initialized",
      authorization_url: responseData.data?.authorization_url ?? null,
      access_code: responseData.data?.access_code ?? null,
      reference: responseData.data?.reference ?? null,
      raw: responseData,
    });
  } catch (err) {
    const details = err.response?.data ?? err.message ?? String(err);
    console.error("Paystack init error:", details);
    return res.status(500).json({
      ok: false,
      error: "Paystack initialization failed",
      details,
    });
  }
}
