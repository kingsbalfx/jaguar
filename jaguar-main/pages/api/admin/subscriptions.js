import { createPagesServerClient } from "@supabase/auth-helpers-nextjs";
import { getSupabaseClient } from "../../../lib/supabaseClient";
import { isSubscriptionActive } from "../../../lib/subscription-status";
import { activateSubscription } from "../../../lib/subscription-lifecycle";
import { SUCCESSFUL_PAYMENT_STATUSES, validatePlanPayment } from "../../../lib/payment-amount";
import { emailLayout, getSmtpStatus, sendEmail, verifySmtpConnection } from "../../../lib/mailer";

async function requireAdmin(req, res) {
  const supabase = createPagesServerClient({ req, res });
  const { data: { session } } = await supabase.auth.getSession();
  if (!session?.user) {
    res.status(401).json({ error: "not authenticated" });
    return null;
  }
  const supabaseAdmin = getSupabaseClient({ server: true });
  if (!supabaseAdmin) {
    res.status(500).json({ error: "Supabase admin client not configured" });
    return null;
  }
  const { data: profile } = await supabaseAdmin.from("profiles").select("role").eq("id", session.user.id).maybeSingle();
  if (String(profile?.role || "").toLowerCase() !== "admin") {
    res.status(403).json({ error: "forbidden" });
    return null;
  }
  return { supabaseAdmin, adminEmail: session.user.email };
}

export default async function handler(req, res) {
  const context = await requireAdmin(req, res);
  if (!context) return;
  const { supabaseAdmin, adminEmail } = context;

  if (req.method === "GET") {
    const [{ data: subscriptions, error: subscriptionError }, { data: payments, error: paymentError }] = await Promise.all([
      supabaseAdmin.from("subscriptions").select("email,plan,status,amount,started_at,ended_at").order("started_at", { ascending: false }),
      supabaseAdmin.from("payments").select("id,user_id,customer_email,plan,status,amount,reference,received_at").order("received_at", { ascending: false }).limit(500),
    ]);
    if (subscriptionError || paymentError) {
      return res.status(500).json({ error: "failed to load subscription data" });
    }
    const activeEmails = new Set(
      (subscriptions || []).filter(isSubscriptionActive).map((item) => String(item.email || "").toLowerCase())
    );
    const repairable = (payments || []).filter((payment) => {
      const validStatus = SUCCESSFUL_PAYMENT_STATUSES.has(String(payment.status || "").toLowerCase());
      return validStatus && payment.customer_email && !activeEmails.has(String(payment.customer_email).toLowerCase()) &&
        validatePlanPayment({ amount: payment.amount, currency: "NGN", plan: payment.plan }).valid;
    });
    return res.status(200).json({
      subscriptions: subscriptions || [],
      repairable,
      smtpStatus: getSmtpStatus(),
    });
  }

  if (req.method === "POST") {
    if (req.body?.action === "test_email") {
      const verification = await verifySmtpConnection();
      if (!verification.ok) {
        return res.status(400).json({ error: "Gmail SMTP connection failed. Check the Gmail address and App Password." });
      }
      if (!adminEmail) return res.status(400).json({ error: "Admin account email is missing." });
      try {
        const result = await sendEmail({
          to: adminEmail,
          subject: "KINGSBALFX Gmail SMTP test",
          text: "Your Gmail SMTP configuration is working.",
          html: emailLayout(
            "Gmail SMTP is working",
            "<p>Your KINGSBALFX lifecycle emails are configured correctly.</p>",
            "Open admin dashboard",
            "/admin/subscriptions",
          ),
        });
        return res.status(result.sent ? 200 : 400).json({
          ok: result.sent,
          message: result.sent ? `Test email sent to ${adminEmail}.` : "Test email could not be sent.",
        });
      } catch (error) {
        console.error("Gmail SMTP test delivery failed:", error?.message || error);
        return res.status(400).json({ error: "Gmail accepted the connection but test delivery failed." });
      }
    }
    const reference = String(req.body?.reference || "").trim();
    if (!reference) return res.status(400).json({ error: "payment reference required" });
    const { data: payment } = await supabaseAdmin
      .from("payments")
      .select("user_id,customer_email,plan,status,amount,reference")
      .eq("reference", reference)
      .maybeSingle();
    if (!payment || !SUCCESSFUL_PAYMENT_STATUSES.has(String(payment.status || "").toLowerCase())) {
      return res.status(400).json({ error: "verified successful payment not found" });
    }
    const validation = validatePlanPayment({ amount: payment.amount, currency: "NGN", plan: payment.plan });
    if (!validation.valid) return res.status(400).json({ error: validation.error });
    await activateSubscription({
      supabaseAdmin,
      email: payment.customer_email,
      plan: payment.plan,
      amount: payment.amount,
      userId: payment.user_id,
    });
    return res.status(200).json({ ok: true });
  }

  return res.status(405).json({ error: "Method not allowed" });
}
