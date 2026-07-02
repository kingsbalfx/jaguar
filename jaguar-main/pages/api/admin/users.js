import { createPagesServerClient } from "@supabase/auth-helpers-nextjs";
import { getSupabaseClient } from "../../../lib/supabaseClient";
import { getBotTierDefaults, normalizeBotLimit } from "../../../lib/pricing-config";
import { isSubscriptionActive } from "../../../lib/subscription-status";
import { subscriptionEndDate } from "../../../lib/subscription-lifecycle";

const USER_SELECT_BASE =
  "id,email,name,username,role,lifetime,bot_tier,bot_max_signals_per_day,bot_max_concurrent_trades,bot_signal_quality,bot_tier_updated_at,created_at";

const USER_SELECT_EXT = `${USER_SELECT_BASE},trading_profile`;

const BOT_QUALITY_OPTIONS = new Set(["none", "sample", "basic", "standard", "academy", "premium", "vip", "pro", "lifetime", "elite"]);
const PAID_ROLES = new Set(["premium", "vip", "pro", "lifetime"]);

function cleanBotTier(value) {
  return String(value || "free").trim().toLowerCase();
}

function cleanBotQuality(value, fallback = "none") {
  const quality = String(value || fallback || "none").trim().toLowerCase();
  return BOT_QUALITY_OPTIONS.has(quality) ? quality : fallback;
}

async function syncSubscriptionForRole(supabaseAdmin, { id, role }) {
  const normalizedRole = String(role || "").trim().toLowerCase();
  if (!normalizedRole) return;

  const { data: profile, error: profileError } = await supabaseAdmin
    .from("profiles")
    .select("email")
    .eq("id", id)
    .maybeSingle();
  if (profileError || !profile?.email) return;

  const email = String(profile.email).trim().toLowerCase();
  const now = new Date();

  if (!PAID_ROLES.has(normalizedRole)) {
    await supabaseAdmin
      .from("subscriptions")
      .update({ status: "cancelled", ended_at: now.toISOString() })
      .ilike("email", email)
      .in("plan", [...PAID_ROLES]);
    return;
  }

  const payload = {
    email,
    plan: normalizedRole,
    status: "active",
    started_at: now.toISOString(),
    ended_at: subscriptionEndDate(normalizedRole, now),
  };

  const existing = await supabaseAdmin
    .from("subscriptions")
    .select("email,plan")
    .ilike("email", email)
    .ilike("plan", normalizedRole)
    .limit(1);
  if (existing.error) return;

  if (existing.data?.[0]) {
    const update = await supabaseAdmin
      .from("subscriptions")
      .update(payload)
      .ilike("email", email)
      .ilike("plan", normalizedRole);
    if (!update.error) return;
    if (update.error.code !== "42703" && !String(update.error.message || "").toLowerCase().includes("column")) return;
    await supabaseAdmin
      .from("subscriptions")
      .update({ email, plan: normalizedRole, status: "active" })
      .ilike("email", email)
      .ilike("plan", normalizedRole);
    return;
  }

  const insert = await supabaseAdmin.from("subscriptions").insert(payload);
  if (insert.error?.code === "42703" || String(insert.error?.message || "").toLowerCase().includes("column")) {
    await supabaseAdmin.from("subscriptions").insert({ email, plan: normalizedRole, status: "active" });
  }
}

async function requireAdmin(req, res) {
  const supabase = createPagesServerClient({ req, res });
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session?.user) {
    res.status(401).json({ error: "not authenticated" });
    return null;
  }

  const supabaseAdmin = getSupabaseClient({ server: true });
  if (!supabaseAdmin) {
    res.status(500).json({ error: "Supabase admin client not configured" });
    return null;
  }

  const { data: profile } = await supabaseAdmin
    .from("profiles")
    .select("role")
    .eq("id", session.user.id)
    .maybeSingle();

  const role = (profile?.role || "user").toLowerCase();
  if (role !== "admin") {
    res.status(403).json({ error: "forbidden" });
    return null;
  }

  return { supabaseAdmin };
}

export default async function handler(req, res) {
  const ctx = await requireAdmin(req, res);
  if (!ctx) return;
  const { supabaseAdmin } = ctx;

  if (req.method === "GET") {
    let profiles = null;
    let error = null;
    let usedExtended = true;

    {
      const resProfiles = await supabaseAdmin.from("profiles").select(USER_SELECT_EXT);
      profiles = resProfiles.data || null;
      error = resProfiles.error || null;
    }

    if (error && error.code === "42703") {
      usedExtended = false;
      const resProfiles = await supabaseAdmin.from("profiles").select(USER_SELECT_BASE);
      profiles = resProfiles.data || null;
      error = resProfiles.error || null;
    }

    if (error) return res.status(500).json({ error: "failed to load users" });

    const { data: subs } = await supabaseAdmin
      .from("subscriptions")
      .select("email,plan,status,started_at,ended_at");

    const byEmail = new Map();
    (subs || []).forEach((sub) => {
      const email = String(sub.email || "").toLowerCase();
      const current = byEmail.get(email);
      if (!current) {
        byEmail.set(email, sub);
        return;
      }
      if (isSubscriptionActive(sub) && !isSubscriptionActive(current)) {
        byEmail.set(email, sub);
        return;
      }
      if ((sub.started_at || "") > (current.started_at || "")) {
        byEmail.set(email, sub);
      }
    });

    const { data: authData } = await supabaseAdmin.auth.admin.listUsers({ page: 1, perPage: 1000 });
    const profilesById = new Map((profiles || []).map((profile) => [profile.id, profile]));
    const mergedProfiles = [...(profiles || [])];
    for (const authUser of authData?.users || []) {
      if (!profilesById.has(authUser.id)) {
        mergedProfiles.push({
          id: authUser.id,
          email: authUser.email,
          name: authUser.user_metadata?.full_name || authUser.user_metadata?.name || null,
          username: authUser.user_metadata?.username || null,
          role: authUser.app_metadata?.role || "user",
          created_at: authUser.created_at,
        });
      }
    }
    const authById = new Map((authData?.users || []).map((user) => [user.id, user]));

    const users = mergedProfiles.map((profile) => {
      const sub = byEmail.get(String(profile.email || "").toLowerCase());
      const authUser = authById.get(profile.id);
      return {
        ...profile,
        trading_profile: usedExtended ? profile.trading_profile || "balanced" : undefined,
        plan: sub?.plan || profile.role || "user",
        planStatus: sub ? (isSubscriptionActive(sub) ? "active" : sub.status === "active" ? "expired" : sub.status) : "none",
        startedAt: sub?.started_at || null,
        endedAt: sub?.ended_at || null,
        lastSignInAt: authUser?.last_sign_in_at || null,
        emailConfirmedAt: authUser?.email_confirmed_at || null,
      };
    });

    return res.status(200).json({ users });
  }

  if (req.method === "PUT") {
    const {
      id,
      role,
      lifetime,
      botTier,
      botMaxSignalsPerDay,
      botMaxConcurrentTrades,
      botSignalQuality,
      applyTierDefaults,
      tradingProfile,
    } = req.body || {};
    if (!id) return res.status(400).json({ error: "user id required" });

    const updates = {};
    if (role) updates.role = role;
    if (typeof lifetime === "boolean") updates.lifetime = lifetime;
    const tierDefaults = botTier ? getBotTierDefaults(botTier) : null;

    if (botTier) {
      updates.bot_tier = cleanBotTier(tierDefaults?.botTier || botTier);
    }

    if (applyTierDefaults && tierDefaults) {
      updates.bot_max_signals_per_day = tierDefaults.botMaxSignalsPerDay;
      updates.bot_max_concurrent_trades = tierDefaults.botMaxConcurrentTrades;
      updates.bot_signal_quality = tierDefaults.botSignalQuality;
    }

    if (botMaxSignalsPerDay !== undefined) {
      updates.bot_max_signals_per_day = normalizeBotLimit(botMaxSignalsPerDay, 0);
    }
    if (botMaxConcurrentTrades !== undefined) {
      updates.bot_max_concurrent_trades = normalizeBotLimit(botMaxConcurrentTrades, 0);
    }
    if (botSignalQuality !== undefined) {
      updates.bot_signal_quality = cleanBotQuality(botSignalQuality);
    }

    if (tradingProfile !== undefined) {
      updates.trading_profile = String(tradingProfile || "balanced").trim().toLowerCase();
    }

    if (
      botTier ||
      applyTierDefaults ||
      botMaxSignalsPerDay !== undefined ||
      botMaxConcurrentTrades !== undefined ||
      botSignalQuality !== undefined
    ) {
      updates.bot_tier_updated_at = new Date().toISOString();
    }

    // Use extended select when available; fall back if trading_profile column isn't migrated yet.
    let data = null;
    let error = null;
    {
      const resUpdate = await supabaseAdmin
        .from("profiles")
        .update(updates)
        .eq("id", id)
        .select(USER_SELECT_EXT)
        .maybeSingle();
      data = resUpdate.data || null;
      error = resUpdate.error || null;
    }

    if (error && error.code === "42703") {
      const cleaned = { ...updates };
      delete cleaned.trading_profile;
      const resUpdate = await supabaseAdmin
        .from("profiles")
        .update(cleaned)
        .eq("id", id)
        .select(USER_SELECT_BASE)
        .maybeSingle();
      data = resUpdate.data || null;
      error = resUpdate.error || null;
    }

    if (error) return res.status(500).json({ error: error.message || "failed to update user" });
    if (role) await syncSubscriptionForRole(supabaseAdmin, { id, role });
    return res.status(200).json({ user: data });
  }

  return res.status(405).json({ error: "Method not allowed" });
}
