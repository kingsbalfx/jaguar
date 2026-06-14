import { getPricingTier } from "./pricing-config.js";
import { emailLayout, sendLifecycleEmail } from "./mailer.js";
import { normalizePaymentAmount } from "./payment-amount.js";

export function subscriptionEndDate(plan, startedAt = new Date()) {
  const tier = getPricingTier(plan);
  return tier?.billingCycle === "monthly"
    ? new Date(startedAt.getTime() + 30 * 24 * 60 * 60 * 1000).toISOString()
    : null;
}

async function writeSubscription({ supabaseAdmin, email, plan, payload, exists }) {
  const variants = [
    payload,
    { status: payload.status, started_at: payload.started_at, ended_at: payload.ended_at },
    { status: payload.status },
  ];
  let lastError = null;
  for (const variant of variants) {
    const result = exists
      ? await supabaseAdmin
          .from("subscriptions")
          .update({ ...variant, email, plan })
          .ilike("email", email)
          .ilike("plan", plan)
      : await supabaseAdmin.from("subscriptions").insert({ email, plan, ...variant });
    if (!result.error) return;
    lastError = result.error;
    if (result.error.code !== "42703" && !String(result.error.message || "").toLowerCase().includes("column")) {
      break;
    }
  }
  throw lastError || new Error("Subscription write failed");
}

export async function activateSubscription({ supabaseAdmin, email, plan, amount, userId, reference }) {
  if (!supabaseAdmin || !email || !plan) throw new Error("Missing subscription activation details");
  const normalizedEmail = String(email).trim().toLowerCase();
  const normalizedPlan = String(plan).trim().toLowerCase();
  const normalizedReference = reference ? String(reference).trim() : null;
  let existingActivation = null;
  if (normalizedReference) {
    const activationResult = await supabaseAdmin
      .from("subscription_activations")
      .select("id,started_at,ended_at")
      .eq("payment_reference", normalizedReference)
      .maybeSingle();
    existingActivation = activationResult.data || null;
    if (existingActivation?.id) {
      const { data: currentSubscriptions, error: currentError } = await supabaseAdmin
        .from("subscriptions")
        .select("status,ended_at")
        .ilike("email", normalizedEmail)
        .ilike("plan", normalizedPlan);
      let subscriptions = currentSubscriptions || [];
      if (currentError?.code === "42703" || String(currentError?.message || "").toLowerCase().includes("column")) {
        const fallback = await supabaseAdmin
          .from("subscriptions")
          .select("status")
          .ilike("email", normalizedEmail)
          .ilike("plan", normalizedPlan);
        if (fallback.error) throw fallback.error;
        subscriptions = fallback.data || [];
      } else if (currentError) {
        throw currentError;
      }
      const active = subscriptions.some((subscription) => {
        if (String(subscription.status || "").toLowerCase() !== "active") return false;
        return !subscription.ended_at || new Date(subscription.ended_at) > new Date();
      });
      if (active) {
        return {
          active: true,
          repaired: false,
          startedAt: existingActivation.started_at,
          endedAt: existingActivation.ended_at,
        };
      }
      const deliberatelyDisabled = subscriptions.some((subscription) =>
        ["revoked", "cancelled", "canceled"].includes(String(subscription.status || "").toLowerCase())
      );
      if (deliberatelyDisabled) {
        return {
          active: false,
          revoked: true,
          repaired: false,
          startedAt: existingActivation.started_at,
          endedAt: existingActivation.ended_at,
        };
      }
      const recordedEnd = existingActivation.ended_at ? new Date(existingActivation.ended_at) : null;
      if (recordedEnd && !Number.isNaN(recordedEnd.getTime()) && recordedEnd <= new Date()) {
        return {
          active: false,
          expired: true,
          repaired: false,
          startedAt: existingActivation.started_at,
          endedAt: existingActivation.ended_at,
        };
      }
    }
  }
  const now = new Date();
  const startedAt = existingActivation?.started_at || now.toISOString();
  const endedAt = existingActivation?.ended_at ?? subscriptionEndDate(normalizedPlan, now);
  const normalizedAmount = Math.round(normalizePaymentAmount(amount, normalizedPlan));
  const payload = { status: "active", amount: normalizedAmount, started_at: startedAt, ended_at: endedAt };
  const existing = await supabaseAdmin
    .from("subscriptions")
    .select("email,plan,status")
    .ilike("email", normalizedEmail)
    .ilike("plan", normalizedPlan)
    .limit(1);
  if (existing.error) throw existing.error;
  await writeSubscription({
    supabaseAdmin,
    email: normalizedEmail,
    plan: normalizedPlan,
    payload,
    exists: Boolean(existing.data?.[0]),
  });

  const profileUpdate = { role: normalizedPlan, updated_at: startedAt };
  const profileResult = userId
    ? await supabaseAdmin.from("profiles").update(profileUpdate).eq("id", userId)
    : await supabaseAdmin.from("profiles").update(profileUpdate).ilike("email", normalizedEmail);
  if (profileResult.error) console.warn("Subscription activated but profile role update failed:", profileResult.error.message);
  if (normalizedReference && !existingActivation?.id) {
    const activationInsert = await supabaseAdmin.from("subscription_activations").insert({
      payment_reference: normalizedReference,
      email: normalizedEmail,
      plan: normalizedPlan,
      started_at: startedAt,
      ended_at: endedAt,
    });
    if (activationInsert.error) console.warn("Subscription activation audit insert failed:", activationInsert.error.message);
  }

  const tier = getPricingTier(normalizedPlan);
  const expiryText = endedAt ? ` Your access is active until ${new Date(endedAt).toLocaleDateString("en-NG")}.` : "";
  await sendLifecycleEmail({
    supabaseAdmin,
    email: normalizedEmail,
    type: "subscription_activated",
    dedupeKey: `subscription_activated:${normalizedEmail}:${normalizedPlan}:${startedAt.slice(0, 10)}`,
    subject: `${tier?.displayName || normalizedPlan} subscription activated`,
    text: `Your KINGSBALFX ${tier?.displayName || normalizedPlan} subscription is active.${expiryText}`,
    html: emailLayout(
      "Subscription activated",
      `<p>Your <strong>${tier?.displayName || normalizedPlan}</strong> access is now active.${expiryText}</p>`,
      "Open dashboard",
      `/dashboard/${normalizedPlan}`,
    ),
  });
  return { active: true, repaired: Boolean(existingActivation?.id), startedAt, endedAt };
}
