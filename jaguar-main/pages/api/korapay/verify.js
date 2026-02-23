import { getSupabaseClient } from "../../../lib/supabaseClient";
import { verifyKorapayCharge } from "../../../lib/korapay";

function getReference(req) {
  return req.query?.reference || req.body?.reference || req.query?.ref || null;
}

function extractPlan(metadata) {
  if (!metadata) return "user";
  return metadata.plan || metadata.product || metadata.tier || "user";
}

export default async function handler(req, res) {
  const reference = getReference(req);
  if (!reference) {
    return res.status(400).json({ error: "Missing reference parameter" });
  }

  try {
    const result = await verifyKorapayCharge(reference);
    if (!result.ok) {
      return res.status(400).json({ error: result.error || "Korapay verification failed" });
    }

    const metadata = result.metadata || {};
    const plan = extractPlan(metadata);
    const userId = metadata.userId || metadata.user_id || null;
    const buyerEmail = result.email || metadata.email || null;

    const supabaseAdmin = getSupabaseClient({ server: true });
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
          },
        ]);
      } catch (e) {
        console.warn("Payment insert failed:", e?.message || e);
      }

      try {
        if (userId) {
          await supabaseAdmin.from("profiles").update({ role: plan }).eq("id", userId);
          try {
            await supabaseAdmin.auth.admin.updateUserById(userId, {
              app_metadata: { role: plan },
            });
          } catch (e) {
            console.warn("auth.admin.updateUserById failed:", e?.message || e);
          }
        } else if (buyerEmail) {
          const { data: profile } = await supabaseAdmin
            .from("profiles")
            .select("id")
            .eq("email", buyerEmail)
            .maybeSingle();
          if (profile?.id) {
            await supabaseAdmin.from("profiles").update({ role: plan }).eq("id", profile.id);
          }
        }
      } catch (e) {
        console.warn("Role update failed:", e?.message || e);
      }
    }

    return res.status(200).json({
      success: true,
      reference: result.reference,
      plan,
      status: result.status,
    });
  } catch (err) {
    console.error("korapay/verify exception:", err);
    return res.status(500).json({ error: "Server error while verifying payment" });
  }
}
