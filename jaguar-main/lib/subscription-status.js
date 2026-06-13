export const ROLE_RANK = { free: 0, user: 0, all: 0, premium: 1, vip: 2, pro: 3, lifetime: 4, admin: 99 };

export function isSubscriptionActive(subscription, now = new Date()) {
  if (subscription?.status !== "active") return false;
  if (!subscription.ended_at) return true;
  const endedAt = new Date(subscription.ended_at);
  return !Number.isNaN(endedAt.getTime()) && endedAt > now;
}

export async function getPlanStatus({ supabaseAdmin, email, plan, role }) {
  const normalizedRole = String(role || "user").toLowerCase();
  const normalizedPlan = String(plan || "").toLowerCase();
  const base = { plan: normalizedPlan, active: false, status: "inactive", source: null, endedAt: null };

  if (normalizedRole === "admin") return { ...base, active: true, status: "active", source: "admin" };
  if (normalizedRole === "lifetime" && normalizedPlan === "lifetime") {
    return { ...base, active: true, status: "active", source: "manual_lifetime" };
  }
  if (!supabaseAdmin || !email || !normalizedPlan) return base;

  try {
    const { data, error } = await supabaseAdmin
      .from("subscriptions")
      .select("plan, status, ended_at, started_at")
      .eq("email", email)
      .eq("plan", normalizedPlan)
      .order("started_at", { ascending: false })
      .limit(1);
    const subscription = data?.[0];
    if (error || !subscription) return base;
    const active = isSubscriptionActive(subscription);
    return {
      ...base,
      active,
      status: active ? "active" : subscription.status === "active" ? "expired" : subscription.status || "inactive",
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
  if (normalizedRole === "admin") return { active: true, rank: 99, status: "active" };
  if (normalizedRole === "lifetime") return { active: true, rank: 4, status: "active" };
  if ((ROLE_RANK[normalizedRole] || 0) === 0) return { active: false, rank: 0, status: "inactive" };
  const status = await getPlanStatus({ supabaseAdmin, email, plan: normalizedRole, role: normalizedRole });
  return { active: status.active, rank: status.active ? ROLE_RANK[normalizedRole] : 0, status: status.status };
}
