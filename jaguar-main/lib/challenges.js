import { decryptMt5Password, encryptMt5Password, maskPassword } from "./mt5-crypto.js";
import { getChallengeRules } from "./pricing-config.js";
import { resolveEffectivePlan } from "./subscription-status.js";

export const CHALLENGE_PLATFORMS = [
  {
    id: "mt5",
    label: "MT5 demo challenge",
    description: "Trade a funded-style MT5 demo account and journal your progress.",
  },
  {
    id: "tradingview",
    label: "TradingView challenge",
    description: "Mark up the pairs on TradingView and submit your analysis for review.",
  },
];

export const CHALLENGE_OPEN_STATUSES = ["pending", "approved", "active"];
export const CHALLENGE_STATUSES = [
  "pending",
  "approved",
  "active",
  "rejected",
  "expired",
  "cancelled",
];

export function isChallengePlatform(value) {
  const platform = String(value || "").trim().toLowerCase();
  return CHALLENGE_PLATFORMS.some((item) => item.id === platform) ? platform : "";
}

export function monthStartIso(reference = new Date()) {
  const date = new Date(reference);
  date.setDate(1);
  date.setHours(0, 0, 0, 0);
  return date.toISOString();
}

/**
 * Everything a user (or the admin panel) needs to know about challenge access:
 * the plan rules, current usage and whether a new challenge can be created.
 */
export async function getChallengeContext({ supabaseAdmin, userId, email, role, botTier = "" }) {
  const effective = await resolveEffectivePlan({ supabaseAdmin, email, role, botTier });
  const rules = getChallengeRules(effective.plan);

  let active = 0;
  let usedThisMonth = 0;
  if (supabaseAdmin && userId) {
    const [openRows, monthRows] = await Promise.all([
      supabaseAdmin.from("challenges").select("id").eq("user_id", userId).in("status", CHALLENGE_OPEN_STATUSES),
      supabaseAdmin
        .from("challenges")
        .select("id")
        .eq("user_id", userId)
        .gte("created_at", monthStartIso()),
    ]);
    active = (openRows.data || []).length;
    usedThisMonth = (monthRows.data || []).length;
  }

  const reasons = [];
  if (!rules.enabled) reasons.push("plan_not_eligible");
  if (rules.enabled && rules.maxConcurrent > 0 && active >= rules.maxConcurrent)
    reasons.push("max_concurrent_reached");
  if (rules.enabled && rules.perMonth > 0 && usedThisMonth >= rules.perMonth)
    reasons.push("monthly_quota_reached");

  return {
    plan: effective.plan,
    planSource: effective.source,
    rules,
    usage: {
      active,
      usedThisMonth,
      remainingThisMonth: rules.perMonth > 0 ? Math.max(rules.perMonth - usedThisMonth, 0) : null,
    },
    canCreate: reasons.length === 0,
    reasons,
  };
}

/** Remove encrypted password fields before sending a challenge to the browser. */
export function publicChallenge(row) {
  if (!row) return null;
  const {
    demo_password_encrypted,
    demo_password_iv,
    demo_password_tag,
    ...rest
  } = row;
  return {
    ...rest,
    hasCredentials: Boolean(demo_password_encrypted),
  };
}

export function publicDemoAccount(row) {
  if (!row) return null;
  return {
    id: row.id,
    platform: row.platform,
    label: row.label,
    login: row.login,
    server: row.server,
    passwordMask: maskPassword(row.password_last4),
    tradingviewUrl: row.tradingview_url,
    tradingviewUsername: row.tradingview_username,
    status: row.status,
    assignedChallengeId: row.assigned_challenge_id,
    notes: row.notes,
    createdAt: row.created_at,
  };
}

export { encryptMt5Password, decryptMt5Password };

const REASON_MESSAGES = {
  plan_not_eligible: "Demo challenges are not included in your current plan.",
  max_concurrent_reached: "You already have an open challenge — finish or cancel it first.",
  monthly_quota_reached: "You have used every challenge included in your plan this month.",
};

export function describeChallengeReasons(reasons = []) {
  return (reasons || []).map((reason) => REASON_MESSAGES[reason] || reason).join(" ");
}

function truncate(value, max) {
  return String(value || "").trim().slice(0, max);
}

export async function listChallenges(supabaseAdmin, { userId = null, limit = 50 } = {}) {
  let query = supabaseAdmin
    .from("challenges")
    .select("*")
    .order("created_at", { ascending: false })
    .limit(limit);
  if (userId) query = query.eq("user_id", userId);
  const { data, error } = await query;
  if (error) throw error;
  return data || [];
}

export async function createChallenge({ supabaseAdmin, user, platform, goal, experience, context }) {
  const selected = isChallengePlatform(platform);
  if (!selected) return { error: "platform must be mt5 or tradingview", status: 400 };
  if (!context?.rules?.enabled) {
    return { error: describeChallengeReasons(["plan_not_eligible"]), status: 403 };
  }
  if (!context.rules.platforms.includes(selected)) {
    return { error: `${selected.toUpperCase()} challenges are not included in your plan.`, status: 403 };
  }
  if (!context.canCreate) {
    return { error: describeChallengeReasons(context.reasons), status: 409 };
  }

  const now = new Date().toISOString();
  const payload = {
    user_id: user.id,
    email: String(user.email || "").trim().toLowerCase(),
    full_name: truncate(user.name || user.username || "", 120) || null,
    plan: context.plan,
    platform: selected,
    status: "pending",
    duration_days: context.rules.days || 14,
    goal: truncate(goal, 600) || null,
    experience: truncate(experience, 200) || null,
    created_at: now,
    updated_at: now,
  };

  const { data, error } = await supabaseAdmin
    .from("challenges")
    .insert(payload)
    .select("*")
    .maybeSingle();

  if (error) {
    if (String(error.code) === "23505") {
      return { error: "You already have an open challenge.", status: 409 };
    }
    return { error: error.message || "Unable to create the challenge", status: 500 };
  }
  return { challenge: publicChallenge(data) };
}

async function claimDemoAccount(supabaseAdmin, platform) {
  const { data, error } = await supabaseAdmin
    .from("challenge_demo_accounts")
    .select("*")
    .eq("platform", platform)
    .eq("status", "available")
    .order("created_at", { ascending: true })
    .limit(1);
  if (error) return { error: error.message };
  return { account: (data || [])[0] || null };
}


export async function approveChallenge({
  supabaseAdmin,
  challenge,
  adminId = null,
  durationDays = null,
  note = "",
  accountId = null,
}) {
  if (!challenge) return { error: "challenge not found", status: 404 };
  if (["rejected", "cancelled"].includes(challenge.status)) {
    return { error: `A ${challenge.status} challenge cannot be approved`, status: 409 };
  }

  const days = Math.min(
    Math.max(Number(durationDays) || Number(challenge.duration_days) || 14, 1),
    365,
  );

  let account = null;
  if (accountId) {
    const { data } = await supabaseAdmin
      .from("challenge_demo_accounts")
      .select("*")
      .eq("id", accountId)
      .maybeSingle();
    account = data || null;
  }
  if (!account) {
    const claimed = await claimDemoAccount(supabaseAdmin, challenge.platform);
    if (claimed.error) return { error: claimed.error, status: 500 };
    account = claimed.account;
  }

  const now = new Date();
  const patch = {
    status: "active",
    duration_days: days,
    started_at: now.toISOString(),
    expires_at: new Date(now.getTime() + days * 86400000).toISOString(),
    reviewed_by: adminId,
    reviewed_at: now.toISOString(),
    admin_note: truncate(note, 600) || challenge.admin_note || null,
    rejection_reason: null,
    updated_at: now.toISOString(),
  };

  if (account) {
    patch.account_id = account.id;
    patch.demo_login = account.login || null;
    patch.demo_server = account.server || null;
    patch.demo_password_encrypted = account.password_encrypted || null;
    patch.demo_password_iv = account.password_iv || null;
    patch.demo_password_tag = account.password_tag || null;
    patch.demo_password_last4 = account.password_last4 || null;
    patch.tradingview_url = account.tradingview_url || null;
    patch.tradingview_username = account.tradingview_username || null;
  }

  const { data, error } = await supabaseAdmin
    .from("challenges")
    .update(patch)
    .eq("id", challenge.id)
    .select("*")
    .maybeSingle();
  if (error) return { error: error.message || "Unable to approve the challenge", status: 500 };

  if (account) {
    await supabaseAdmin
      .from("challenge_demo_accounts")
      .update({
        status: "assigned",
        assigned_challenge_id: challenge.id,
        updated_at: now.toISOString(),
      })
      .eq("id", account.id);
  }

  return {
    challenge: publicChallenge(data),
    accountAssigned: Boolean(account),
    warning: account
      ? null
      : "No demo account was available for this platform — add one to the demo pool and approve again.",
  };
}

async function releaseDemoAccount(supabaseAdmin, challenge) {
  if (!challenge?.account_id) return;
  await supabaseAdmin
    .from("challenge_demo_accounts")
    .update({ status: "available", assigned_challenge_id: null, updated_at: new Date().toISOString() })
    .eq("id", challenge.account_id);
}

export async function rejectChallenge({ supabaseAdmin, challenge, adminId = null, reason = "", note = "" }) {
  if (!challenge) return { error: "challenge not found", status: 404 };
  await releaseDemoAccount(supabaseAdmin, challenge);
  const now = new Date().toISOString();
  const { data, error } = await supabaseAdmin
    .from("challenges")
    .update({
      status: "rejected",
      rejection_reason: truncate(reason, 400) || "Not approved",
      admin_note: truncate(note, 600) || challenge.admin_note || null,
      reviewed_by: adminId,
      reviewed_at: now,
      updated_at: now,
    })
    .eq("id", challenge.id)
    .select("*")
    .maybeSingle();
  if (error) return { error: error.message, status: 500 };
  return { challenge: publicChallenge(data) };
}

export async function cancelChallenge({ supabaseAdmin, challenge, reason = "" }) {
  if (!challenge) return { error: "challenge not found", status: 404 };
  await releaseDemoAccount(supabaseAdmin, challenge);
  const now = new Date().toISOString();
  const { data, error } = await supabaseAdmin
    .from("challenges")
    .update({
      status: "cancelled",
      admin_note: truncate(reason, 600) || challenge.admin_note || null,
      updated_at: now,
    })
    .eq("id", challenge.id)
    .select("*")
    .maybeSingle();
  if (error) return { error: error.message, status: 500 };
  return { challenge: publicChallenge(data) };
}

/** Mark overdue active challenges as expired and release their demo accounts. */
export async function expireOverdueChallenges(supabaseAdmin, { userId = null } = {}) {
  let query = supabaseAdmin
    .from("challenges")
    .select("id,account_id,user_id,status,expires_at")
    .eq("status", "active")
    .lt("expires_at", new Date().toISOString());
  if (userId) query = query.eq("user_id", userId);
  const { data, error } = await query;
  if (error) throw error;

  for (const challenge of data || []) {
    await supabaseAdmin
      .from("challenges")
      .update({ status: "expired", updated_at: new Date().toISOString() })
      .eq("id", challenge.id);
    await releaseDemoAccount(supabaseAdmin, challenge);
  }
  return (data || []).length;
}

export function challengeCredentials(challenge) {
  if (!challenge) return { available: false };
  const password = decryptMt5Password({
    password_encrypted: challenge.demo_password_encrypted,
    password_iv: challenge.demo_password_iv,
    password_tag: challenge.demo_password_tag,
  });
  return {
    available: Boolean(
      challenge.demo_login || challenge.tradingview_url || challenge.tradingview_username,
    ),
    platform: challenge.platform,
    login: challenge.demo_login || null,
    server: challenge.demo_server || null,
    password: password || null,
    passwordMask: maskPassword(challenge.demo_password_last4),
    tradingviewUrl: challenge.tradingview_url || null,
    tradingviewUsername: challenge.tradingview_username || null,
    expiresAt: challenge.expires_at || null,
    status: challenge.status,
  };
}

