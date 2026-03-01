import { getSupabaseClient } from "../../../lib/supabaseClient";
import { verifyKorapayCharge } from "../../../lib/korapay";
import { PRICING_TIERS } from "../../../lib/pricing-config";

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
  if (!metadata) return "user";
  return metadata.plan || metadata.product || metadata.tier || "user";
}

function getPlanEndDate(planId) {
  const tier = PRICING_TIERS[String(planId || "").toUpperCase()];
  if (!tier) return null;
  if (tier.billingCycle === "monthly") {
    return new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString();
  }
  return null;
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
            plan,
            user_id: userId,
            reference: result.reference || reference,
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

      try {
        if (buyerEmail) {
          const endedAt = getPlanEndDate(plan);
          await supabaseAdmin.from("subscriptions").upsert(
            {
              email: buyerEmail,
              plan,
              status: "active",
              amount: result.amount || 0,
              started_at: new Date().toISOString(),
              ended_at: endedAt,
            },
            { onConflict: "email,plan" }
          );
        }
      } catch (e) {
        console.warn("Subscription upsert failed:", e?.message || e);
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
