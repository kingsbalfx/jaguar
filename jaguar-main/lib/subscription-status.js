import { SUCCESSFUL_PAYMENT_STATUSES, validatePlanPayment } from "./payment-amount.js";
import { activateSubscription } from "./subscription-lifecycle.js";

export const ROLE_RANK = { free: 0, user: 0, all: 0, premium: 1, vip: 2, pro: 3, lifetime: 4, admin: 99 };

async function loadSubscriptions(supabaseAdmin, email, plan = null) {
  let query = supabaseAdmin
    .from("subscriptions")
    .select("plan, status, ended_at, started_at")
    .ilike("email", String(email).trim());
  if (plan) query = query.ilike("plan", plan);
  let result = await query.order("started_at", { ascending: false });
  if (result.error?.code === "42703" || String(result.error?.message || "").toLowerCase().includes("column")) {
    let fallback = supabaseAdmin
      .from("subscriptions")
      .select("plan, status")
      .ilike("email", String(email).trim());
    if (plan) fallback = fallback.ilike("plan", plan);
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
  const normalizedPlan = String(plan || "").toLowerCase();
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
      .sort((a, b) => (ROLE_RANK[String(b.plan || "").toLowerCase()] || 0) - (ROLE_RANK[String(a.plan || "").toLowerCase()] || 0));
    const highest = activePlans[0];
    const highestPlan = String(highest?.plan || "").toLowerCase();
    if (highest) {
      return {
        active: true,
        plan: highestPlan,
        plans: activePlans.map((subscription) => String(subscription.plan || "").toLowerCase()),
        rank: ROLE_RANK[highestPlan] || 0,
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
        const repairedPlan = String(verifiedPayment.plan || "").toLowerCase();
        if (repaired?.active) {
          return {
            active: true,
            plan: repairedPlan,
            plans: [repairedPlan],
            rank: ROLE_RANK[repairedPlan] || 0,
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
