import { getSupabaseClient } from "../../../lib/supabaseClient";

export default async function handler(req, res) {
  if (req.method !== "GET") return res.status(405).json({ error: "Method not allowed" });
  const receiptId = String(req.query.receipt || req.query.id || "").trim();
  if (!receiptId) return res.status(400).json({ valid: false, error: "receipt id required" });

  const supabaseAdmin = getSupabaseClient({ server: true });
  if (!supabaseAdmin) return res.status(500).json({ valid: false, error: "Supabase admin client not configured" });

  const { data, error } = await supabaseAdmin
    .from("subscription_receipts")
    .select("receipt_id,email,plan,amount,currency,payment_reference,started_at,ended_at,issued_at,signature")
    .eq("receipt_id", receiptId)
    .maybeSingle();

  if (error?.code === "42P01" || error?.code === "42703") {
    return res.status(404).json({ valid: false, error: "receipt registry is not installed" });
  }
  if (error) return res.status(500).json({ valid: false, error: error.message });
  if (!data) return res.status(404).json({ valid: false, error: "receipt not found" });

  return res.status(200).json({
    valid: true,
    receipt: {
      id: data.receipt_id,
      email: data.email,
      plan: data.plan,
      amount: data.amount,
      currency: data.currency,
      paymentReference: data.payment_reference,
      startedAt: data.started_at,
      endedAt: data.ended_at,
      issuedAt: data.issued_at,
      signature: data.signature,
    },
  });
}
