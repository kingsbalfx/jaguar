import { getSupabaseClient } from "../../../lib/supabaseClient";
import { emailLayout, sendLifecycleEmail } from "../../../lib/mailer";
import { getPricingTier } from "../../../lib/pricing-config";

export default async function handler(req, res) {
  const token = String(req.headers.authorization || "").replace(/^Bearer\s+/i, "");
  if (!process.env.CRON_SECRET || token !== process.env.CRON_SECRET) {
    return res.status(401).json({ error: "unauthorized" });
  }
  const supabaseAdmin = getSupabaseClient({ server: true });
  if (!supabaseAdmin) return res.status(500).json({ error: "Supabase admin client not configured" });

  const now = new Date();
  const warningLimit = new Date(now.getTime() + 2 * 24 * 60 * 60 * 1000);
  const { data, error } = await supabaseAdmin
    .from("subscriptions")
    .select("email,plan,status,ended_at")
    .eq("status", "active")
    .not("ended_at", "is", null)
    .lte("ended_at", warningLimit.toISOString());
  if (error) return res.status(500).json({ error: error.message });

  let warnings = 0;
  let expired = 0;
  const failures = [];
  for (const subscription of data || []) {
    const endDate = new Date(subscription.ended_at);
    const tier = getPricingTier(subscription.plan);
    const dateLabel = endDate.toLocaleDateString("en-NG");
    if (endDate <= now) {
      await supabaseAdmin.from("subscriptions").update({ status: "expired" }).eq("email", subscription.email).eq("plan", subscription.plan).eq("ended_at", subscription.ended_at);
      const result = await sendLifecycleEmail({
        supabaseAdmin,
        email: subscription.email,
        type: "subscription_expired",
        dedupeKey: `subscription_expired:${subscription.email}:${subscription.plan}:${subscription.ended_at}`,
        subject: "Your KINGSBALFX subscription has expired",
        text: `Your ${tier?.displayName || subscription.plan} subscription expired on ${dateLabel}.`,
        html: emailLayout("Subscription expired", `<p>Your <strong>${tier?.displayName || subscription.plan}</strong> access expired on ${dateLabel}.</p>`, "Reactivate plan", `/checkout?plan=${subscription.plan}`),
      });
      if (result.sent || result.reason === "already_sent") expired += 1;
      else failures.push({ email: subscription.email, type: "expired", reason: result.reason, details: result.details || null });
    } else {
      const result = await sendLifecycleEmail({
        supabaseAdmin,
        email: subscription.email,
        type: "subscription_expiry_warning",
        dedupeKey: `subscription_expiry_warning:${subscription.email}:${subscription.plan}:${subscription.ended_at}`,
        subject: "Your subscription expires in 2 days",
        text: `Your ${tier?.displayName || subscription.plan} subscription expires on ${dateLabel}.`,
        html: emailLayout("Subscription expiry reminder", `<p>Your <strong>${tier?.displayName || subscription.plan}</strong> access expires on ${dateLabel}.</p>`, "Renew plan", `/checkout?plan=${subscription.plan}`),
      });
      if (result.sent || result.reason === "already_sent") warnings += 1;
      else failures.push({ email: subscription.email, type: "warning", reason: result.reason, details: result.details || null });
    }
  }
  return res.status(failures.length ? 207 : 200).json({ ok: failures.length === 0, warnings, expired, failures });
}
