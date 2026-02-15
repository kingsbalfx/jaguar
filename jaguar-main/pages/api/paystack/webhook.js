// pages/api/paystack/webhook.js
import crypto from "crypto";

export const config = {
  api: {
    bodyParser: false,
  },
};

function readRawBody(req) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    req.on("data", (chunk) => chunks.push(chunk));
    req.on("end", () => resolve(Buffer.concat(chunks)));
    req.on("error", reject);
  });
}

export default async function handler(req, res) {
  if (req.method !== "POST") {
    res.setHeader("Allow", "POST");
    return res.status(405).send("Method Not Allowed");
  }

  const rawBody = await readRawBody(req);
  // Verify Paystack signature
  const signature = req.headers["x-paystack-signature"] || "";
  const secret = process.env.PAYSTACK_SECRET_KEY || "";
  if (!secret) {
    console.error("PAYSTACK_SECRET_KEY is missing");
    return res.status(500).send("Server config error");
  }
  const hash = crypto.createHmac("sha512", secret).update(rawBody).digest("hex");
  if (hash !== signature) {
    console.warn("Invalid Paystack signature", hash, signature);
    return res.status(401).send("invalid signature");
  }

  // Process the event
  let event;
  try {
    event = JSON.parse(rawBody.toString("utf8"));
  } catch (e) {
    return res.status(400).send("invalid json");
  }
  console.log("Paystack webhook event:", event.event, event.data?.reference);

  // TODO: update payment record in your database based on event.data

  // Respond quickly to acknowledge
  return res.status(200).send("ok");
}
