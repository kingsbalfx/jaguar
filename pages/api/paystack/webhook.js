// pages/api/paystack/webhook.js
import crypto from "crypto";

export default async function handler(req, res) {
  if (req.method !== "POST") {
    res.setHeader("Allow", "POST");
    return res.status(405).send("Method Not Allowed");
  }
  // Verify Paystack signature
  const signature = req.headers["x-paystack-signature"] || "";
  const secret = process.env.PAYSTACK_SECRET_KEY || "";
  const body = JSON.stringify(req.body);
  if (!secret) {
    console.error("PAYSTACK_SECRET_KEY is missing");
    return res.status(500).send("Server config error");
  }
  const hash = crypto.createHmac("sha512", secret).update(body).digest("hex");
  if (hash !== signature) {
    console.warn("Invalid Paystack signature", hash, signature);
    return res.status(401).send("invalid signature");
  }

  // Process the event
  const event = req.body;
  console.log("Paystack webhook event:", event.event, event.data?.reference);

  // TODO: update payment record in your database based on event.data

  // Respond quickly to acknowledge
  return res.status(200).send("ok");
}