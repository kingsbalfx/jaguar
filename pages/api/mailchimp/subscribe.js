import axios from "axios";
export default async function handler(req, res) {
  if (req.method !== "POST")
    return res.status(405).json({ error: "Method not allowed" });
  const { email, firstName } = req.body;
  const key = process.env.MAILCHIMP_API_KEY;
  const listId = process.env.MAILCHIMP_LIST_ID;
  const prefix = process.env.MAILCHIMP_SERVER_PREFIX; // e.g. us19
  if (!key || !listId || !prefix)
    return res.status(500).json({ error: "Mailchimp not configured" });
  const url = `https://${prefix}.api.mailchimp.com/3.0/lists/${listId}/members`;
  try {
    const resp = await axios.post(
      url,
      {
        email_address: email,
        status: "subscribed",
        merge_fields: { FNAME: firstName || "" },
      },
      {
        auth: { username: "anystring", password: key },
      },
    );
    return res.status(200).json({ status: "subscribed", data: resp.data });
  } catch (err) {
    console.error("Mailchimp error", err.response?.data || err.message);
    return res
      .status(500)
      .json({
        error: "Mailchimp subscribe failed",
        details: err.response?.data || err.message,
      });
  }
}
