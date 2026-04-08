import { createPagesServerClient } from "@supabase/auth-helpers-nextjs";
import { getSupabaseClient } from "../../../lib/supabaseClient";
import { getBotTierDefaults, normalizeBotLimit } from "../../../lib/pricing-config";

const USER_SELECT =
  "id,email,name,username,role,lifetime,bot_tier,bot_max_signals_per_day,bot_max_concurrent_trades,bot_signal_quality,bot_tier_updated_at,created_at";

const BOT_QUALITY_OPTIONS = new Set(["none", "basic", "standard", "premium", "vip", "pro", "elite"]);

function cleanBotTier(value) {
  return String(value || "free").trim().toLowerCase();
}

function cleanBotQuality(value, fallback = "none") {
  const quality = String(value || fallback || "none").trim().toLowerCase();
  return BOT_QUALITY_OPTIONS.has(quality) ? quality : fallback;
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
    const { data: profiles, error } = await supabaseAdmin
      .from("profiles")
      .select(USER_SELECT);
    if (error) return res.status(500).json({ error: "failed to load users" });

    const { data: subs } = await supabaseAdmin
      .from("subscriptions")
      .select("email,plan,status,started_at,ended_at");

    const byEmail = new Map();
    (subs || []).forEach((sub) => {
      const current = byEmail.get(sub.email);
      if (!current) {
        byEmail.set(sub.email, sub);
        return;
      }
      if ((sub.started_at || "") > (current.started_at || "")) {
        byEmail.set(sub.email, sub);
      }
    });

    const users = (profiles || []).map((profile) => {
      const sub = byEmail.get(profile.email);
      return {
        ...profile,
        plan: sub?.plan || profile.role || "user",
        planStatus: sub?.status || "none",
        startedAt: sub?.started_at || null,
        endedAt: sub?.ended_at || null,
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

    if (
      botTier ||
      applyTierDefaults ||
      botMaxSignalsPerDay !== undefined ||
      botMaxConcurrentTrades !== undefined ||
      botSignalQuality !== undefined
    ) {
      updates.bot_tier_updated_at = new Date().toISOString();
    }

    const { data, error } = await supabaseAdmin
      .from("profiles")
      .update(updates)
      .eq("id", id)
      .select(USER_SELECT)
      .maybeSingle();

    if (error) return res.status(500).json({ error: error.message || "failed to update user" });
    return res.status(200).json({ user: data });
  }

  return res.status(405).json({ error: "Method not allowed" });
}
