import { handleKorapayEvent, verifyKorapaySignature } from "../../../lib/korapay";

export const config = {
  api: {
    bodyParser: false,
  },
};

async function getRawBody(req) {
  const chunks = [];
  for await (const chunk of req) {
    chunks.push(typeof chunk === "string" ? Buffer.from(chunk) : chunk);
  }
  return Buffer.concat(chunks).toString("utf8");
}

export default async function handler(req, res) {
  if (req.method !== "POST") return res.status(405).end();

  const rawBody = await getRawBody(req);
  const signature =
    req.headers["x-korapay-signature"] ||
    req.headers["x-kora-signature"] ||
    req.headers["x-korapay-signature".toLowerCase()] ||
    req.headers["x-kora-signature".toLowerCase()] ||
    "";

  const secret = process.env.KORAPAY_WEBHOOK_SECRET || process.env.KORAPAY_SECRET_KEY;
  if (secret) {
    const isValid = verifyKorapaySignature(rawBody, signature, secret);
    if (!isValid) {
      return res.status(401).json({ error: "Invalid signature" });
    }
  }

  try {
    const event = JSON.parse(rawBody);
    await handleKorapayEvent(rawBody, event);
    return res.status(200).json({ ok: true });
  } catch (err) {
    console.error("Korapay webhook error:", err);
    return res.status(400).json({ error: "Invalid payload" });
  }
}
