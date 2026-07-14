import { emailLayout, getSmtpStatus, sendLifecycleEmail } from "./mailer";
import { createInAppNotification } from "./notifications";
import { BOT_UNLIMITED_LIMIT, PRICING_TIERS, getBotTierDefaults, getPricingTier, normalizeBotLimit } from "./pricing-config";
import { assertSignalDeliveryOpen } from "./signal-gate";
import { ROLE_RANK, isSubscriptionActive } from "./subscription-status";

const VALID_DIRECTIONS = new Set(["BUY", "SELL"]);
const VALID_PLANS = new Set(Object.values(PRICING_TIERS).map((tier) => tier.id));

function escapeHtml(value) {
  return String(value || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function cleanPlan(value) {
  const plan = String(value || "").trim().toLowerCase();
  return VALID_PLANS.has(plan) ? plan : "";
}

function cleanNumber(value) {
  if (value === null || value === undefined || value === "") return null;
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
}

function cleanSignalPayload(input = {}) {
  const symbol = String(input.symbol || "").trim().toUpperCase().replace(/[^A-Z0-9._-]/g, "").slice(0, 24);
  const direction = String(input.direction || "").trim().toUpperCase();
  if (!symbol) throw new Error("symbol is required");
  if (!VALID_DIRECTIONS.has(direction)) throw new Error("direction must be BUY or SELL");
  const signal = {
    symbol,
    direction,
    entryPrice: cleanNumber(input.entryPrice ?? input.entry_price ?? input.entry),
    stopLoss: cleanNumber(input.stopLoss ?? input.stop_loss ?? input.sl),
    takeProfit: cleanNumber(input.takeProfit ?? input.take_profit ?? input.tp),
    confidence: cleanNumber(input.confidence),
    timeframe: String(input.timeframe || input.interval || "").trim().slice(0, 24),
    strategy: String(input.strategy || input.source || "KINGSBALFX Bot").trim().slice(0, 80),
    note: String(input.note || input.message || input.reason || "").trim().slice(0, 600),
    status: String(input.status || "delivered").trim().toLowerCase().slice(0, 40),
  };
  return signal;
}

function normalizeTargetPlans({ targetPlans, minTier }) {
  const requested = Array.isArray(targetPlans) ? targetPlans : String(targetPlans || "").split(",");
  const explicit = requested.map(cleanPlan).filter(Boolean);
  if (explicit.length) return [...new Set(explicit)];
  const minimum = cleanPlan(minTier);
  if (minimum) {
    const minRank = ROLE_RANK[minimum] || 0;
    return Object.values(PRICING_TIERS)
      .filter((tier) => tier.features?.signals && (ROLE_RANK[tier.id] || 0) >= minRank)
      .map((tier) => tier.id);
  }
  return Object.values(PRICING_TIERS)
    .filter((tier) => tier.features?.signals)
    .map((tier) => tier.id);
}

function startOfTodayIso() {
  const date = new Date();
  date.setHours(0, 0, 0, 0);
  return date.toISOString();
}

function buildSignalSvg(signal) {
  const sideColor = signal.direction === "BUY" ? "#22c55e" : "#ef4444";
  const rows = [
    ["Entry", signal.entryPrice ?? "Market"],
    ["Stop Loss", signal.stopLoss ?? "Managed"],
    ["Take Profit", signal.takeProfit ?? "Managed"],
    ["Confidence", signal.confidence === null ? "Review" : `${signal.confidence}%`],
  ];
  return `<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="675" viewBox="0 0 1200 675">
  <defs>
    <linearGradient id="bg" x1="0" x2="1" y1="0" y2="1">
      <stop offset="0" stop-color="#020617"/>
      <stop offset="0.55" stop-color="#111827"/>
      <stop offset="1" stop-color="#0f172a"/>
    </linearGradient>
    <radialGradient id="glow" cx="75%" cy="20%" r="55%">
      <stop offset="0" stop-color="${sideColor}" stop-opacity="0.28"/>
      <stop offset="1" stop-color="${sideColor}" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <rect width="1200" height="675" fill="url(#bg)"/>
  <rect width="1200" height="675" fill="url(#glow)"/>
  <text x="600" y="350" text-anchor="middle" transform="rotate(-14 600 350)" fill="#ffffff" opacity="0.08" font-family="Arial" font-size="104" font-weight="900" letter-spacing="18">KINGSBALFX</text>
  <rect x="64" y="54" width="1072" height="567" rx="34" fill="rgba(15,23,42,0.82)" stroke="rgba(255,255,255,0.18)" stroke-width="2"/>
  <text x="98" y="120" fill="#f8fafc" font-family="Arial" font-size="34" font-weight="900">KINGSBALFX SIGNAL</text>
  <text x="98" y="158" fill="#94a3b8" font-family="Arial" font-size="18">${escapeHtml(signal.strategy)}${signal.timeframe ? ` - ${escapeHtml(signal.timeframe)}` : ""}</text>
  <rect x="98" y="202" width="230" height="86" rx="18" fill="${sideColor}"/>
  <text x="213" y="257" text-anchor="middle" fill="#ffffff" font-family="Arial" font-size="42" font-weight="900">${signal.direction}</text>
  <text x="370" y="270" fill="#ffffff" font-family="Arial" font-size="82" font-weight="900">${escapeHtml(signal.symbol)}</text>
  ${rows.map((row, index) => {
    const x = 98 + (index % 2) * 510;
    const y = 350 + Math.floor(index / 2) * 112;
    return `<rect x="${x}" y="${y}" width="456" height="84" rx="18" fill="rgba(255,255,255,0.07)" stroke="rgba(255,255,255,0.1)"/>
      <text x="${x + 24}" y="${y + 32}" fill="#94a3b8" font-family="Arial" font-size="18">${escapeHtml(row[0])}</text>
      <text x="${x + 24}" y="${y + 64}" fill="#f8fafc" font-family="Arial" font-size="28" font-weight="800">${escapeHtml(row[1])}</text>`;
  }).join("")}
  <text x="98" y="584" fill="#cbd5e1" font-family="Arial" font-size="18">${escapeHtml(signal.note || "Educational signal. Manage risk carefully; this is not financial advice.")}</text>
  <text x="1102" y="584" text-anchor="end" fill="#64748b" font-family="Arial" font-size="16">${new Date().toLocaleString("en-NG")}</text>
</svg>`;
}

function buildSignalAttachment(signal) {
  return {
    filename: `KINGSBALFX_${signal.symbol}_${signal.direction}_signal.svg`,
    content: Buffer.from(buildSignalSvg(signal), "utf8"),
    cid: "kingsbalfx-signal-card",
    contentType: "image/svg+xml",
  };
}

function buildProvidedImageAttachment(imageData, signal) {
  const match = String(imageData || "").match(/^data:image\/(png|jpe?g|webp);base64,(.+)$/i);
  if (!match) return null;
  if (imageData.length > 6_500_000) throw new Error("Signal image is too large. Keep screenshots under 6 MB.");
  const extension = match[1].toLowerCase().replace("jpeg", "jpg");
  return {
    filename: `KINGSBALFX_${signal.symbol}_${signal.direction}_signal.${extension}`,
    content: Buffer.from(match[2], "base64"),
    cid: "kingsbalfx-signal-card",
    contentType: `image/${extension === "jpg" ? "jpeg" : extension}`,
  };
}

async function loadAudience(supabaseAdmin, targetPlans) {
  const [{ data: profiles, error: profileError }, { data: subscriptions, error: subscriptionError }] = await Promise.all([
    supabaseAdmin.from("profiles").select("id,email,name,username,role,bot_tier,bot_max_signals_per_day,bot_signal_quality"),
    supabaseAdmin.from("subscriptions").select("email,plan,status,started_at,ended_at"),
  ]);
  if (profileError) throw new Error(profileError.message || "Unable to load users");
  if (subscriptionError) throw new Error(subscriptionError.message || "Unable to load subscriptions");

  const activeByEmail = new Map();
  for (const subscription of subscriptions || []) {
    if (!isSubscriptionActive(subscription)) continue;
    const plan = cleanPlan(subscription.plan);
    if (!plan) continue;
    const email = String(subscription.email || "").trim().toLowerCase();
    const current = activeByEmail.get(email);
    if (!current || (ROLE_RANK[plan] || 0) > (ROLE_RANK[current.plan] || 0)) {
      activeByEmail.set(email, { ...subscription, plan });
    }
  }

  const targetSet = new Set(targetPlans);
  return (profiles || []).map((profile) => {
    const email = String(profile.email || "").trim().toLowerCase();
    const active = activeByEmail.get(email);
    const profilePlan = cleanPlan(profile.role);
    const plan = active?.plan || profilePlan || "free";
    const tier = getPricingTier(plan) || PRICING_TIERS.FREE;
    const defaults = getBotTierDefaults(plan);
    const dailyLimit = normalizeBotLimit(profile.bot_max_signals_per_day, defaults.botMaxSignalsPerDay);
    return {
      ...profile,
      email,
      plan,
      tier,
      dailyLimit,
      signalQuality: profile.bot_signal_quality || defaults.botSignalQuality,
      active: Boolean(active) || plan === "free" || String(profile.role || "").toLowerCase() === "admin",
      eligible: targetSet.has(plan) && Boolean(tier.features?.signals) && dailyLimit > 0,
    };
  }).filter((user) => user.email && user.active && user.eligible);
}

function summarizeAudience(users = []) {
  return users.reduce((summary, user) => {
    const plan = user.plan || "unknown";
    summary[plan] = (summary[plan] || 0) + 1;
    return summary;
  }, {});
}

async function runWithConcurrency(items, limit, worker) {
  const results = [];
  let nextIndex = 0;
  const workerCount = Math.max(1, Math.min(Number(limit) || 1, items.length || 1));
  await Promise.all(Array.from({ length: workerCount }, async () => {
    while (nextIndex < items.length) {
      const index = nextIndex;
      nextIndex += 1;
      results[index] = await worker(items[index], index);
    }
  }));
  return results;
}

async function countDeliveriesToday(supabaseAdmin, userId) {
  const result = await supabaseAdmin
    .from("signal_deliveries")
    .select("id", { count: "exact", head: true })
    .eq("user_id", userId)
    .gte("delivered_at", startOfTodayIso());
  if (result.error) throw result.error;
  return result.count || 0;
}

async function insertMasterSignal(supabaseAdmin, signal, targetPlans, payload) {
  const { data, error } = await supabaseAdmin
    .from("bot_signals")
    .insert({
      user_id: null,
      symbol: signal.symbol,
      direction: signal.direction,
      entry_price: signal.entryPrice,
      stop_loss: signal.stopLoss,
      take_profit: signal.takeProfit,
      signal_quality: targetPlans.join(","),
      confidence: signal.confidence,
      reason: { ...payload, targetPlans, timeframe: signal.timeframe, strategy: signal.strategy, note: signal.note },
      status: signal.status || "delivered",
      created_at: new Date().toISOString(),
    })
    .select("id")
    .maybeSingle();
  if (error) throw new Error(error.message || "Unable to save signal");
  return data?.id || null;
}

function shouldExecuteMt5(payload = {}) {
  const value = payload.executeMt5 ?? payload.executeOnMt5 ?? payload.mt5Execution ?? payload.execute;
  if (value === true) return true;
  return ["true", "1", "yes", "mt5", "execute"].includes(String(value || "").trim().toLowerCase());
}

async function forwardSignalToMt5Bot({ signal, signalId, targetPlans, payload }) {
  if (!shouldExecuteMt5(payload)) return { attempted: false, reason: "not_requested" };
  const baseUrl = String(process.env.BOT_API_INTERNAL || process.env.BOT_API_URL || "").trim().replace(/\/$/, "");
  const token = String(process.env.BOT_API_TOKEN || process.env.ADMIN_API_KEY || "").trim();
  if (!baseUrl) return { attempted: true, ok: false, reason: "BOT_API_URL_not_configured" };
  const endpoint = String(process.env.BOT_EXECUTION_ENDPOINT || `${baseUrl}/signals/execute`).trim();
  try {
    const response = await fetch(endpoint, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}`, "x-bot-api-token": token } : {}),
      },
      body: JSON.stringify({
        signalId,
        symbol: signal.symbol,
        direction: signal.direction,
        entryPrice: signal.entryPrice,
        stopLoss: signal.stopLoss,
        takeProfit: signal.takeProfit,
        confidence: signal.confidence,
        timeframe: signal.timeframe,
        strategy: signal.strategy,
        targetPlans,
        source: "kingsbalfx-web",
        payload,
      }),
    });
    const data = await response.json().catch(() => ({}));
    return {
      attempted: true,
      ok: response.ok,
      status: response.status,
      endpoint,
      data,
      reason: response.ok ? null : data.error || data.message || "bot_execution_failed",
    };
  } catch (error) {
    return { attempted: true, ok: false, endpoint, reason: error.message || "bot_execution_failed" };
  }
}

export async function deliverBotSignal({ supabaseAdmin, payload }) {
  if (!supabaseAdmin) throw new Error("Supabase admin client not configured");
  await assertSignalDeliveryOpen(supabaseAdmin);
  const signal = cleanSignalPayload(payload);
  const targetPlans = normalizeTargetPlans({ targetPlans: payload.targetPlans || payload.plans || payload.plan, minTier: payload.minTier });
  if (!targetPlans.length) throw new Error("No valid target plans selected");
  const audience = await loadAudience(supabaseAdmin, targetPlans);
  const audienceByPlan = summarizeAudience(audience);
  const signalId = await insertMasterSignal(supabaseAdmin, signal, targetPlans, payload);
  const mt5Execution = await forwardSignalToMt5Bot({ signal, signalId, targetPlans, payload });
  const attachment = buildProvidedImageAttachment(payload.imageData || payload.image || payload.screenshot, signal) || buildSignalAttachment(signal);
  const subject = `${signal.symbol} ${signal.direction} signal from KINGSBALFX`;
  const body = `${signal.symbol} ${signal.direction} signal: entry ${signal.entryPrice ?? "market"}, SL ${signal.stopLoss ?? "managed"}, TP ${signal.takeProfit ?? "managed"}.`;
  const html = emailLayout(
    "KINGSBALFX signal alert",
    `<p><strong>${escapeHtml(signal.symbol)} ${escapeHtml(signal.direction)}</strong></p>
     <p>${escapeHtml(body)}</p>
     <p><img src="cid:${attachment.cid}" alt="KINGSBALFX signal card" style="display:block;max-width:100%;border-radius:16px;border:1px solid #dbe4ef" /></p>
     <p style="color:#64748b;font-size:13px">Educational signal only. Confirm risk before execution.</p>`,
    "Open Dashboard",
    "/dashboard#signals",
  );

  let emailed = 0;
  let notified = 0;
  let skippedQuota = 0;
  const errors = [];
  const concurrency = Math.min(Math.max(Number(process.env.SIGNAL_EMAIL_CONCURRENCY || 8), 1), 20);

  await runWithConcurrency(audience, concurrency, async (user) => {
    try {
      const usedToday = await countDeliveriesToday(supabaseAdmin, user.id);
      if (usedToday >= user.dailyLimit && user.dailyLimit < BOT_UNLIMITED_LIMIT) {
        skippedQuota += 1;
        return;
      }
      const dedupeKey = `bot_signal:${signalId}:${user.id}`;
      const emailResult = await sendLifecycleEmail({
        supabaseAdmin,
        email: user.email,
        type: "bot_signal",
        dedupeKey,
        subject,
        text: body,
        html,
        attachments: [attachment],
      });
      if (emailResult.sent) emailed += 1;
      await createInAppNotification({
        supabaseAdmin,
        userId: user.id,
        type: "bot_signal",
        dedupeKey,
        title: subject,
        body,
        link: "/dashboard#signals",
      });
      await supabaseAdmin.from("signal_deliveries").insert({
        signal_id: signalId,
        user_id: user.id,
        email: user.email,
        plan: user.plan,
        daily_limit: user.dailyLimit,
        used_today_before: usedToday,
        channel: "email,in_app",
        status: emailResult.sent ? "sent" : emailResult.reason || "email_not_sent",
        delivered_at: new Date().toISOString(),
      });
      notified += 1;
    } catch (error) {
      errors.push({ userId: user.id, error: error.message || String(error) });
    }
  });

  try {
    await supabaseAdmin.from("bot_logs").insert({
      event: "signal_delivery",
      payload: {
        signalId,
        targetPlans,
        audience: audience.length,
        audienceByPlan,
        emailed,
        notified,
        skippedQuota,
        smtp: getSmtpStatus(),
        mt5Execution,
        errors: errors.slice(0, 10),
      },
    });
  } catch {
    // Signal delivery should not fail just because monitoring logs are unavailable.
  }

  return {
    signalId,
    targetPlans,
    audience: audience.length,
    audienceByPlan,
    emailed,
    notified,
    skippedQuota,
    smtp: getSmtpStatus(),
    mt5Execution,
    errors,
  };
}

export function signalDeliverySqlRequired(error) {
  return error?.code === "42P01" || error?.code === "42703" || /signal_deliveries|column/i.test(String(error?.message || ""));
}
