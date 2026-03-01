export async function getPlanStatus({ supabaseAdmin, userId, email, plan, role }) {
  const base = {
    plan,
    active: false,
    status: "inactive",
    source: null,
    endedAt: null,
  };

  if (!supabaseAdmin || !plan) return base;

  try {
    if (email) {
      const { data: subscription, error: subErr } = await supabaseAdmin
        .from("subscriptions")
        .select("status, ended_at, started_at")
        .eq("email", email)
        .eq("plan", plan)
        .maybeSingle();

      if (!subErr && subscription) {
        const endedAt = subscription.ended_at ? new Date(subscription.ended_at) : null;
        const active = subscription.status === "active" && (!endedAt || endedAt > new Date());
        const status =
          active ? "active" : subscription.status === "active" ? "expired" : subscription.status || "inactive";
        return {
          plan,
          active,
          status,
          source: "subscriptions",
          endedAt: endedAt ? endedAt.toISOString() : null,
        };
      }
    }

    const orClauses = [];
    if (userId) orClauses.push(`user_id.eq.${userId}`);
    if (email) orClauses.push(`customer_email.eq.${email}`);

    let payments = [];
    if (orClauses.length > 0) {
      const { data } = await supabaseAdmin
        .from("payments")
        .select("id, status, received_at")
        .eq("plan", plan)
        .in("status", ["success", "successful", "completed", "paid", "approved"])
        .or(orClauses.join(","))
        .limit(1);
      payments = data || [];
    }

    if (payments.length > 0) {
      return {
        plan,
        active: true,
        status: "active",
        source: "payments",
        endedAt: null,
      };
    }

    if (role && role === plan) {
      return {
        plan,
        active: true,
        status: "active",
        source: "role",
        endedAt: null,
      };
    }

    return base;
  } catch (err) {
    console.error("getPlanStatus error:", err);
    return base;
  }
}
