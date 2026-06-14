import { getSupabaseClient } from "../../../lib/supabaseClient";
import { verifyKorapayCharge } from "../../../lib/korapay";
import { validatePlanPayment } from "../../../lib/payment-amount";
import { activateSubscription } from "../../../lib/subscription-lifecycle";
import { createPagesServerClient } from "@supabase/auth-helpers-nextjs";

function normalizeReference(value) {
  if (!value) return null;
  const ref = Array.isArray(value) ? value[0] : String(value);
  if (!ref) return null;
  const trimmed = ref.trim();
  if (!trimmed) return null;
  if (trimmed.includes(",")) {
    return trimmed.split(",")[0];
  }
  const firstKbs = trimmed.indexOf("KBS_");
  const secondKbs = trimmed.indexOf("KBS_", firstKbs + 1);
  if (firstKbs === 0 && secondKbs > 0) {
    return trimmed.slice(0, secondKbs);
  }
  const match = trimmed.match(/KBS_[A-Za-z0-9_]+/);
  return match ? match[0] : trimmed;
}

function getReference(req) {
  return (
    normalizeReference(req.query?.reference) ||
    normalizeReference(req.body?.reference) ||
    normalizeReference(req.query?.ref) ||
    null
  );
}

function extractPlan(metadata) {
  if (!metadata) return null;
  return metadata.plan || metadata.product || metadata.tier || null;
}

export default async function handler(req, res) {
  const reference = getReference(req);
  if (!reference) {
    return res.status(400).json({ error: "Missing reference parameter" });
  }
  if (process.env.NODE_ENV === "production" && reference.startsWith("SIMULATED_")) {
    return res.status(400).json({ error: "Simulated payments are not accepted in production" });
  }

  try {
    const result = await verifyKorapayCharge(reference);
    if (!result.ok) {
      return res.status(400).json({ error: result.error || "Korapay verification failed" });
    }

    const metadata = result.metadata || {};
    const plan = extractPlan(metadata);
    const supabaseSession = createPagesServerClient({ req, res });
    const { data: { session } } = await supabaseSession.auth.getSession();
    const userId = metadata.userId || metadata.user_id || session?.user?.id || null;
    const buyerEmail = result.email || metadata.email || session?.user?.email || null;
    const paymentValidation = validatePlanPayment({ amount: result.amount, currency: result.currency, plan });
    if (!paymentValidation.valid) {
      return res.status(400).json({ error: paymentValidation.error });
    }

    const supabaseAdmin = getSupabaseClient({ server: true });
    if (!supabaseAdmin) return res.status(500).json({ error: "Subscription activation service is not configured" });
    let activation = null;
    if (supabaseAdmin) {
      try {
        await supabaseAdmin.from("payments").insert([
          {
            event: "korapay.verify",
            data: result.raw || {},
            customer_email: buyerEmail,
            amount: result.amount,
            status: result.status || "success",
            received_at: new Date().toISOString(),
            plan,
            user_id: userId,
            reference: result.reference || reference,
          },
        ]);
      } catch (e) {
        console.warn("Payment insert failed:", e?.message || e);
      }

      if (!buyerEmail || !plan) {
        return res.status(400).json({ error: "Verified payment is missing account email or plan metadata" });
      }
      try {
        activation = await activateSubscription({ supabaseAdmin, email: buyerEmail, plan, amount: paymentValidation.normalizedAmount, userId, reference: result.reference || reference });
      } catch (e) {
        console.error("Subscription activation failed:", e?.message || e);
        return res.status(500).json({
          error: "Payment verified, but subscription activation failed. Retry verification; no new payment is required.",
          diagnostic: e?.message || "Unknown subscription database error",
        });
      }
    }

    return res.status(200).json({
      success: true,
      reference: result.reference,
      plan,
      status: result.status,
      subscriptionActive: Boolean(activation?.active),
      repaired: Boolean(activation?.repaired),
    });
  } catch (err) {
    console.error("korapay/verify exception:", err);
    return res.status(500).json({ error: "Server error while verifying payment" });
  }
}
