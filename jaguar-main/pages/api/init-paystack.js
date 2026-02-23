export default async function handler(req, res) {
  return res.status(410).json({
    error: "Paystack has been removed. Use /api/korapay/init instead.",
  });
}
