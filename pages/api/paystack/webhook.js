import crypto from "crypto";
export default async function handler(req, res) {
  // Paystack sends JSON payload with X-Paystack-Signature header (HMAC SHA512 using secret)
  const signature = req.headers["x-paystack-signature"] || "";
  const secret = process.env.PAYSTACK_SECRET || "";
  const body = JSON.stringify(req.body);
  if (!secret) return res.status(500).send("PAYSTACK_SECRET missing");
  const hash = crypto.createHmac("sha512", secret).update(body).digest("hex");
  if (hash !== signature) {
    console.warn("Invalid Paystack signature", hash, signature);
    return res.status(401).send("invalid signature");
  }
  // At this point, process the event
  const event = req.body;
  console.log("Paystack webhook event", event.event, event.data?.reference);
  // TODO: update payment record in Supabase
  res.status(200).send("ok");
}
