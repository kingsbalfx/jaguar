import axios from "axios";

export default async function handler(req, res) {
  if (req.method !== "GET") return res.status(405).end();
  const { reference } = req.query;
  const key = process.env.PAYSTACK_SECRET_KEY;
  if (!key)
    return res.status(500).json({ error: "Paystack key not configured" });

  try {
    const resp = await axios.get(
      `https://api.paystack.co/transaction/verify/${encodeURIComponent(reference)}`,
      {
        headers: { Authorization: `Bearer ${key}` },
      },
    );
    // TODO: validate and update user subscription in DB
    return res.status(200).json(resp.data);
  } catch (err) {
    console.error(err.response?.data || err.message);
    return res.status(500).json({ error: "Paystack verify failed" });
  }
}
