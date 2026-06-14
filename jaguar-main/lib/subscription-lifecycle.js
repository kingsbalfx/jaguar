import { getPricingTier } from "./pricing-config.js";
import { emailLayout, sendLifecycleEmail } from "./mailer.js";

export function subscriptionEndDate(plan, startedAt = new Date()) {
  const tier = getPricingTier(plan);
  return tier?.billingCycle === "monthly"
    ? new Date(startedAt.getTime() + 30 * 24 * 60 * 60 * 1000).toISOString()
    : null;
}

export async function activateSubscription({ supabaseAdmin, email, plan, amount, userId, reference }) {
  if (!supabaseAdmin || !email || !plan) throw new Error("Missing subscription activation details");
  if (reference) {
    const existingActivation = await supabaseAdmin
      .from("subscription_activations")
      .select("id,started_at,ended_at")
      .eq("payment_reference", reference)
      .maybeSingle();
    if (existingActivation.data?.id) {
      return { startedAt: existingActivation.data.started_at, endedAt: existingActivation.data.ended_at };
    }
  }
  const now = new Date();
  const startedAt = now.toISOString();
  const endedAt = subscriptionEndDate(plan, now);
  const payload = { status: "active", amount: amount || 0, started_at: startedAt, ended_at: endedAt };
  const existing = await supabaseAdmin.from("subscriptions").select("email,plan").eq("email", email).eq("plan", plan).limit(1);
  if (existing.error) throw existing.error;
  if (existing.data?.[0]) {
    const result = await supabaseAdmin.from("subscriptions").update(payload).eq("email", email).eq("plan", plan);
    if (result.error) throw result.error;
  } else {
    const result = await supabaseAdmin.from("subscriptions").insert({ email, plan, ...payload });
    if (result.error) throw result.error;
  }

  const profileUpdate = { role: plan, updated_at: startedAt };
  if (userId) await supabaseAdmin.from("profiles").update(profileUpdate).eq("id", userId);
  else await supabaseAdmin.from("profiles").update(profileUpdate).eq("email", email);
  if (reference) {
    await supabaseAdmin.from("subscription_activations").insert({
      payment_reference: reference,
      email,
      plan,
      started_at: startedAt,
      ended_at: endedAt,
    });
  }

  const tier = getPricingTier(plan);
  const expiryText = endedAt ? ` Your access is active until ${new Date(endedAt).toLocaleDateString("en-NG")}.` : "";
  await sendLifecycleEmail({
    supabaseAdmin,
    email,
    type: "subscription_activated",
    dedupeKey: `subscription_activated:${email}:${plan}:${startedAt.slice(0, 10)}`,
    subject: `${tier?.displayName || plan} subscription activated`,
    text: `Your KINGSBALFX ${tier?.displayName || plan} subscription is active.${expiryText}`,
    html: emailLayout(
      "Subscription activated",
      `<p>Your <strong>${tier?.displayName || plan}</strong> access is now active.${expiryText}</p>`,
      "Open dashboard",
      `/dashboard/${plan}`,
    ),
  });
  return { startedAt, endedAt };
}
