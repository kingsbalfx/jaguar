export default async function handler(req, res) {
  // Send welcome email via Mailchimp API (stub)
  res.status(200).json({ status: "ok", message: "mailchimp stub sent" });
}
