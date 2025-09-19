import Twilio from "twilio";
export default async function handler(req, res) {
  if (req.method !== "POST")
    return res.status(405).json({ error: "Method not allowed" });
  const sid = process.env.TWILIO_SID;
  const token = process.env.TWILIO_AUTH_TOKEN;
  const from = process.env.TWILIO_PHONE;
  if (!sid || !token || !from)
    return res.status(500).json({ error: "Twilio not configured" });
  const { to, body } = req.body;
  try {
    const client = Twilio(sid, token);
    const msg = await client.messages.create({ body, from, to });
    return res.status(200).json({ status: "sent", sid: msg.sid });
  } catch (err) {
    console.error("Twilio error", err);
    return res
      .status(500)
      .json({ error: "Twilio send failed", details: err.message });
  }
}
