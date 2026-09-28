import { SUCCESSFUL_PAYMENT_STATUSES, validatePlanPayment } from "./payment-amount.js";
import { activateSubscription } from "./subscription-lifecycle.js";
import {
  isPaidPlan,
  planAliasesFor,
  planRank,
  resolvePlanId,
} from "./pricing-config.js";

export const ROLE_RANK = { free: 0, user: 0, all: 0, premium: 1, vip: 2, pro: 3, lifetime: 4, admin: 99 };

export { isPaidPlan, planRank, resolvePlanId };

async function loadSubscriptions(supabaseAdmin, email, plan = null) {
  let query = supabaseAdmin
    .from("subscriptions")
    .select("plan, status, ended_at, started_at")
    .ilike("email", String(email).trim());
  if (plan) {
    // Match the canonical id plus every accepted spelling (academy -> premium...),
    // otherwise subscribers stored as "Academy"/"Academy Student" are invisible.
    const aliases = planAliasesFor(plan);
    query = aliases.length > 1 ? query.in("plan", aliases) : query.ilike("plan", plan);
  }
  let result = await query.order("started_at", { ascending: false });
  if (result.error?.code === "42703" || String(result.error?.message || "").toLowerCase().includes("column")) {
    let fallback = supabaseAdmin
      .from("subscriptions")
      .select("plan, status")
      .ilike("email", String(email).trim());
    if (plan) {
      const aliases = planAliasesFor(plan);
      fallback = aliases.length > 1 ? fallback.in("plan", aliases) : fallback.ilike("plan", plan);
    }
    result = await fallback;
  }
  return result;
}

export function isSubscriptionActive(subscription, now = new Date()) {
  if (String(subscription?.status || "").toLowerCase() !== "active") return false;
  if (!subscription.ended_at) return true;
  const endedAt = new Date(subscription.ended_at);
  return !Number.isNaN(endedAt.getTime()) && endedAt > now;
}

export async function getPlanStatus({ supabaseAdmin, email, plan, role }) {
  const normalizedRole = String(role || "user").toLowerCase();
  const normalizedPlan = resolvePlanId(plan) || String(plan || "").toLowerCase();
  const base = { plan: normalizedPlan, active: false, status: "inactive", source: null, endedAt: null };

  if (normalizedRole === "admin") return { ...base, active: true, status: "active", source: "admin" };
  if (!supabaseAdmin || !email || !normalizedPlan) return base;

  try {
    const { data, error } = await loadSubscriptions(supabaseAdmin, email, normalizedPlan);
    const subscription = (data || []).find(isSubscriptionActive) || data?.[0];
    if (error || !subscription) return base;
    const active = isSubscriptionActive(subscription);
    return {
      ...base,
      active,
      status: active ? "active" : String(subscription.status || "").toLowerCase() === "active" ? "expired" : subscription.status || "inactive",
      source: "subscriptions",
      endedAt: subscription.ended_at || null,
    };
  } catch (err) {
    console.error("getPlanStatus error:", err);
    return base;
  }
}

export async function getPaidAccess({ supabaseAdmin, email, role }) {
  const normalizedRole = String(role || "user").toLowerCase();
  if (normalizedRole === "admin") return { active: true, plan: "admin", plans: ["admin"], rank: 99, status: "active" };
  if (!supabaseAdmin || !email) return { active: false, plan: null, plans: [], rank: 0, status: "inactive" };
  try {
    const { data, error } = await loadSubscriptions(supabaseAdmin, email);
    if (error) return { active: false, plan: null, plans: [], rank: 0, status: "inactive" };
    const activePlans = (data || [])
      .filter(isSubscriptionActive)
      .sort((a, b) => planRank(b.plan) - planRank(a.plan));
    const highest = activePlans[0];
    const highestPlan = resolvePlanId(highest?.plan) || String(highest?.plan || "").toLowerCase();
    if (highest) {
      return {
        active: true,
        plan: highestPlan,
        plans: [...new Set(activePlans.map((subscription) => resolvePlanId(subscription.plan) || String(subscription.plan || "").toLowerCase()))],
        rank: planRank(highestPlan),
        status: "active",
      };
    }

    const { data: payments, error: paymentError } = await supabaseAdmin
      .from("payments")
      .select("customer_email,plan,status,amount,reference,received_at,user_id")
      .ilike("customer_email", String(email).trim())
      .order("received_at", { ascending: false })
      .limit(20);
    if (!paymentError) {
      const recentPaymentLimit = Date.now() - 7 * 24 * 60 * 60 * 1000;
      const verifiedPayment = (payments || []).find((payment) => {
        const successful = SUCCESSFUL_PAYMENT_STATUSES.has(String(payment.status || "").toLowerCase());
        const receivedAt = new Date(payment.received_at || 0).getTime();
        const paymentPlan = String(payment.plan || "").toLowerCase();
        const matchingSubscriptions = (data || []).filter(
          (subscription) => String(subscription.plan || "").toLowerCase() === paymentPlan
        );
        const latestMatching = matchingSubscriptions.sort(
          (a, b) => new Date(b.started_at || 0).getTime() - new Date(a.started_at || 0).getTime()
        )[0];
        const latestStatus = String(latestMatching?.status || "").toLowerCase();
        const latestEnd = new Date(latestMatching?.ended_at || 0).getTime();
        const latestStart = new Date(latestMatching?.started_at || 0).getTime();
        const deliberatelyDisabled = ["revoked", "cancelled", "canceled"].includes(latestStatus);
        const expired = latestStatus === "expired" ||
          (latestStatus === "active" && latestEnd > 0 && latestEnd <= Date.now());
        const isEligibleRepair = !deliberatelyDisabled && (
          !latestMatching
            ? receivedAt >= recentPaymentLimit
            : expired
            ? receivedAt > Math.max(latestEnd, latestStart)
            : receivedAt >= recentPaymentLimit && receivedAt >= latestStart - 60 * 60 * 1000
        );
        return successful && isEligibleRepair &&
          validatePlanPayment({ amount: payment.amount, currency: "NGN", plan: payment.plan }).valid;
      });
      if (verifiedPayment) {
        const validation = validatePlanPayment({ amount: verifiedPayment.amount, currency: "NGN", plan: verifiedPayment.plan });
        const repaired = await activateSubscription({
          supabaseAdmin,
          email,
          plan: verifiedPayment.plan,
          amount: validation.normalizedAmount,
          userId: verifiedPayment.user_id,
          reference: verifiedPayment.reference,
        });
        const repairedPlan = resolvePlanId(verifiedPayment.plan) || String(verifiedPayment.plan || "").toLowerCase();
        if (repaired?.active) {
          return {
            active: true,
            plan: repairedPlan,
            plans: [repairedPlan],
            rank: planRank(repairedPlan),
            status: "active",
            repaired: true,
          };
        }
      }
    }
    return { active: false, plan: null, plans: [], rank: 0, status: "inactive" };
  } catch (err) {
    console.error("getPaidAccess error:", err);
    return { active: false, plan: null, plans: [], rank: 0, status: "inactive" };
  }
}

/**
 * Resolve the plan that should drive signal delivery and demo challenges.
 *
 * A paid `subscriptions` row wins, but a paid `profiles.role` (or `profiles.bot_tier`)
 * is also honoured. Previously the audience builder required an *unexpired*
 * subscription row, so subscribers that an admin promoted by role — or whose
 * `ended_at` had lapsed while `status` still said "active" — were silently
 * dropped from every signal email.
 */
export function resolvePlanFromSubscriptions({ role, botTier = "", subscriptions = [] }) {
  const normalizedRole = String(role || "user").toLowerCase();
  if (normalizedRole === "admin" || normalizedRole === "super_admin") {
    return { plan: "admin", rank: 99, active: true, source: "admin", subscription: null, expired: false };
  }

  const rolePlan = resolvePlanId(normalizedRole);
  const tierPlan = resolvePlanId(botTier);
  const fallback = (() => {
    if (rolePlan && isPaidPlan(rolePlan)) {
      return { plan: rolePlan, rank: planRank(rolePlan), active: true, source: "profile_role", subscription: null };
    }
    if (tierPlan && isPaidPlan(tierPlan)) {
      return { plan: tierPlan, rank: planRank(tierPlan), active: true, source: "bot_tier", subscription: null };
    }
    return { plan: "free", rank: 0, active: true, source: "free", subscription: null };
  })();

  const rows = Array.isArray(subscriptions) ? subscriptions : [];
  const activeSubs = rows
    .filter(isSubscriptionActive)
    .sort((a, b) => planRank(b.plan) - planRank(a.plan));
  const paidSub = activeSubs.find((item) => isPaidPlan(item.plan));
  const paidSubPlan = resolvePlanId(paidSub?.plan);
  if (paidSub && paidSubPlan && planRank(paidSubPlan) >= planRank(fallback.plan)) {
    return {
      plan: paidSubPlan,
      rank: planRank(paidSubPlan),
      active: true,
      source: "subscription",
      subscription: paidSub,
      expired: false,
    };
  }
  const lapsed = rows.some(
    (row) => String(row.status || "").toLowerCase() === "active" && !isSubscriptionActive(row),
  );
  return { ...fallback, expired: lapsed };
}

export async function resolveEffectivePlan({ supabaseAdmin, email, role, botTier = "" }) {
  if (!supabaseAdmin || !email) return resolvePlanFromSubscriptions({ role, botTier });
  try {
    const { data, error } = await loadSubscriptions(supabaseAdmin, email);
    if (error) return resolvePlanFromSubscriptions({ role, botTier });
    return resolvePlanFromSubscriptions({ role, botTier, subscriptions: data || [] });
  } catch (err) {
    console.error("resolveEffectivePlan error:", err);
    return resolvePlanFromSubscriptions({ role, botTier });
  }
}
