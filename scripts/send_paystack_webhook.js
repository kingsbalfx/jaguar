/**
 * Simple script to POST a simulated Paystack webhook to the configured server.
 * Usage: node scripts/send_paystack_webhook.js
 * Ensure PAYSTACK_WEBHOOK_SECRET is set in your shell or .env when testing.
 */
import fetch from "node-fetch";
import crypto from "crypto";

const SECRET = process.env.PAYSTACK_WEBHOOK_SECRET || process.env.PAYSTACK_SECRET || "whsec_test";

async function send() {
  const url = process.env.WEBHOOK_URL || "https://kingsbalfx.name.ng/api/paystack-webhook";

  const payload = {
    event: "charge.success",
    data: { id: "test_123", amount: 500000, gateway_response: "Successful", customer: { email: "test@example.com" } },
  };

  const raw = JSON.stringify(payload);
  const sig = crypto.createHmac("sha512", SECRET).update(raw).digest("hex");

  const resp = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", "x-paystack-signature": sig },
    body: raw,
  });

  console.log("Sent webhook to", url, "status", resp.status);
  console.log(await resp.text());
}

send().catch((e) => console.error(e));
