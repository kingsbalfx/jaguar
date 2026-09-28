import { createPagesServerClient } from "@supabase/auth-helpers-nextjs";
import { getSupabaseClient } from "../../../lib/supabaseClient";
import { getSmtpStatus } from "../../../lib/mailer";
import { getSignalGate, isSignalGateActive } from "../../../lib/signal-gate";
import {
  previewSignalAudience,
  summarizeExclusions,
  unsupportedTargetPlans,
} from "../../../lib/signal-delivery";

const DEFAULT_TARGET_PLANS = "premium,vip,pro,lifetime";

function parseTargetPlans(value) {
  const raw = Array.isArray(value) ? value.join(",") : String(value || "");
  const cleaned = raw
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
  if (cleaned.length) return cleaned;
  return String(process.env.BOT_SIGNAL_TARGET_PLANS || DEFAULT_TARGET_PLANS)
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
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

  const role = String(profile?.role || "user").toLowerCase();
  const adminEmail = (
    process.env.SUPER_ADMIN_EMAIL ||
    process.env.NEXT_PUBLIC_ADMIN_EMAIL ||
    ""
  ).toLowerCase();
  const userEmail = String(session.user.email || "").toLowerCase();
  if (role !== "admin" && !(adminEmail && userEmail === adminEmail)) {
    res.status(403).json({ error: "forbidden" });
    return null;
  }

  return { supabaseAdmin, session };
}

function startOfTodayIso() {
  const date = new Date();
  date.setHours(0, 0, 0, 0);
  return date.toISOString();
}

async function loadBotStatus() {
  const baseUrl = String(
    process.env.BOT_API_INTERNAL || process.env.BOT_API_URL || "",
  )
    .trim()
    .replace(/\/+$/, "");
  if (!baseUrl) {
    return { reachable: false, configured: false, reason: "BOT_API_URL not configured" };
  }
  try {
    const response = await fetch(`${baseUrl}/status`, { cache: "no-store" });
    const data = await response.json().catch(() => ({}));
    return { reachable: response.ok, configured: true, status: response.status, ...data };
  } catch (error) {
    return { reachable: false, configured: true, reason: error.message || "bot unreachable" };
  }
}

export default async function handler(req, res) {
  if (req.method !== "GET") {
    return res.status(405).json({ error: "Method not allowed" });
  }

  const ctx = await requireAdmin(req, res);
  if (!ctx) return;
  const { supabaseAdmin } = ctx;

  try {
    const targetPlans = parseTargetPlans(req.query.plans || req.query.targetPlans);

    const [{ gate, missingTable: gateTableMissing }, botStatus] = await Promise.all([
      getSignalGate(supabaseAdmin),
      loadBotStatus(),
    ]);

    const audiencePreview = await previewSignalAudience({
      supabaseAdmin,
      targetPlans,
    });

    const [
      { data: recentSignals },
      { data: recentDeliveries },
      { data: deliveryLogs },
      todayDeliveries,
    ] = await Promise.all([
      supabaseAdmin
        .from("bot_signals")
        .select("id,symbol,direction,status,signal_quality,created_at")
        .order("created_at", { ascending: false })
        .limit(5),
      supabaseAdmin
        .from("signal_deliveries")
        .select("id,email,plan,status,delivered_at")
        .order("delivered_at", { ascending: false })
        .limit(8),
      supabaseAdmin
        .from("bot_logs")
        .select("event,payload,created_at")
        .eq("event", "signal_delivery")
        .order("created_at", { ascending: false })
        .limit(5),
      supabaseAdmin
        .from("signal_deliveries")
        .select("id", { count: "exact", head: true })
        .gte("delivered_at", startOfTodayIso()),
    ]);

    const lastSignalAt = recentSignals?.[0]?.created_at || null;
    const lastDeliveryAt = recentDeliveries?.[0]?.delivered_at || null;
    const lastSignalAgeHours = lastSignalAt
      ? Math.round(((Date.now() - new Date(lastSignalAt).getTime()) / 3600000) * 10) / 10
      : null;

    const unsupported = unsupportedTargetPlans(targetPlans);
    const warnings = [];
    if (!botStatus.reachable) {
      warnings.push(
        "The MT5 bot API is not reachable, so no new signals can be produced. Restart the bot and check its terminal.",
      );
    }
    if (lastSignalAgeHours !== null && lastSignalAgeHours > 24) {
      warnings.push(
        `No master signal for ${lastSignalAgeHours}h — the bot may be stopped, or every strategy is blocked/disabled.`,
      );
    }
    if (!audiencePreview.audience.length) {
      warnings.push(
        "The audience is empty: no subscriber matches the target plans, so nothing would be emailed.",
      );
    }
    if (unsupported.length) {
      warnings.push(`Unrecognised target plans were ignored: ${unsupported.join(", ")}`);
    }
    if (isSignalGateActive(gate)) {
      warnings.push(`Signal delivery is paused: ${gate.message || "pause active"}`);
    }
    if (!getSmtpStatus()?.configured) {
      warnings.push("SMTP is not configured: dashboard alerts work, emails do not.");
    }

    return res.status(200).json({
      gate,
      gateActive: isSignalGateActive(gate),
      gateTableMissing: Boolean(gateTableMissing),
      smtp: getSmtpStatus(),
      targetPlans,
      unsupportedTargetPlans: unsupported,
      audience: audiencePreview.audience.map((user) => ({
        id: user.id,
        email: user.email,
        plan: user.plan,
        planSource: user.planSource,
        dailyLimit: user.dailyLimit,
        signalQuality: user.signalQuality,
        subscriptionExpired: user.subscriptionExpired,
      })),
      audienceByPlan: audiencePreview.byPlan,
      excluded: audiencePreview.excluded.map((user) => ({
        id: user.id,
        email: user.email,
        plan: user.plan,
        planSource: user.planSource,
        reason: user.reason,
        subscriptionExpired: user.subscriptionExpired,
      })),
      excludedSummary: summarizeExclusions(audiencePreview.excluded),
      counts: audiencePreview.counts,
      rules: {
        allowRoleFallback: audiencePreview.allowRoleFallback,
        includeAdmin: audiencePreview.includeAdmin,
        allowQuotaFallback: audiencePreview.allowQuotaFallback,
        hasMuteColumn: audiencePreview.hasMuteColumn,
      },
      recentSignals: recentSignals || [],
      recentDeliveries: recentDeliveries || [],
      recentDeliveryLogs: deliveryLogs || [],
      deliveriesToday: todayDeliveries?.count || 0,
      lastSignalAt,
      lastDeliveryAt,
      lastSignalAgeHours,
      bot: botStatus,
      warnings,
      fetchedAt: new Date().toISOString(),
    });
  } catch (error) {
    const message = String(error?.message || "Unable to load signal health");
    const missingSql = error?.code === "42P01" || /signal_deliveries/i.test(message);
    return res.status(missingSql ? 503 : 500).json({ error: message, missingTable: missingSql });
  }
}

