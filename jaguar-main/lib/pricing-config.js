/**
 * Public mentorship-first launch pricing. All prices are stored in NGN.
 */
export const PRICING_TIERS = {
  FREE: {
    id: "free",
    name: "Free",
    displayName: "Free",
    price: 0,
    currency: "NGN",
    description: "Intro lessons, risk guidance, and sample academy content.",
    features: {
      signals: true,
      signalQuality: "sample",
      maxSignalsPerDay: 1,
      mentorship: false,
      lessonAccess: true,
      sampleContent: true,
      riskWarning: true,
      botAccess: false,
      challengeAccess: false,
      challengeDays: 0,
      challengePlatforms: [],
      challengesPerMonth: 0,
      challengeMaxConcurrent: 0,
    },
    color: "yellow",
    badge: "Start Here",
  },
  PREMIUM: {
    id: "premium",
    name: "Academy",
    displayName: "Academy",
    price: 25000,
    currency: "NGN",
    billingCycle: "monthly",
    description: "Structured group learning for disciplined traders.",
    features: {
      signals: true,
      signalQuality: "academy",
      maxSignalsPerDay: 3,
      maxConcurrentTrades: 0,
      structuredLessons: true,
      pdfResources: true,
      communityAccess: "group",
      weeklyLiveClass: true,
      basicAssignmentAccess: true,
      mentorship: true,
      mentorshipType: "group",
      groupSessionsPerMonth: 4,
      botAccess: false,
      challengeAccess: true,
      challengeDays: 14,
      challengePlatforms: ["mt5"],
      challengesPerMonth: 1,
      challengeMaxConcurrent: 1,
    },
    color: "blue",
    badge: "Academy",
  },
  VIP: {
    id: "vip",
    name: "VIP",
    displayName: "VIP",
    price: 75000,
    currency: "NGN",
    billingCycle: "monthly",
    description: "Group mentorship with assignment and journal review.",
    features: {
      signals: true,
      signalQuality: "vip",
      maxSignalsPerDay: 8,
      maxConcurrentTrades: 2,
      structuredLessons: true,
      pdfResources: true,
      communityAccess: "vip",
      mentorship: true,
      mentorshipType: "group_review",
      groupSessionsPerMonth: 8,
      assignmentReview: true,
      tradingJournalReview: true,
      priorityQA: true,
      botAccess: false,
      privateTestingOnly: true,
      challengeAccess: true,
      challengeDays: 30,
      challengePlatforms: ["mt5", "tradingview"],
      challengesPerMonth: 2,
      challengeMaxConcurrent: 1,
    },
    color: "purple",
    badge: "Review & Mentorship",
  },
  PRO: {
    id: "pro",
    name: "Pro Mentorship",
    displayName: "Pro",
    price: 150000,
    currency: "NGN",
    billingCycle: "monthly",
    description: "Private mentorship, deeper strategy correction, and risk review.",
    features: {
      signals: true,
      signalQuality: "pro",
      maxSignalsPerDay: 15,
      maxConcurrentTrades: 5,
      structuredLessons: true,
      pdfResources: true,
      communityAccess: "pro",
      mentorship: true,
      mentorshipType: "one-on-one",
      oneOnOneSessionsPerMonth: 2,
      groupSessionsPerMonth: 8,
      assignmentReview: true,
      tradingJournalReview: true,
      strategyCorrection: true,
      riskReview: true,
      botAccess: false,
      privateTestingOnly: true,
      challengeAccess: true,
      challengeDays: 30,
      challengePlatforms: ["mt5", "tradingview"],
      challengesPerMonth: 4,
      challengeMaxConcurrent: 2,
    },
    color: "indigo",
    badge: "Private Mentorship",
  },
  LIFETIME: {
    id: "lifetime",
    name: "Lifetime Academy",
    displayName: "Lifetime",
    price: 500000,
    currency: "NGN",
    billingCycle: "one-time",
    description: "Lifetime access to recorded lessons, PDFs, course updates, and community.",
    features: {
      signals: true,
      signalQuality: "lifetime",
      maxSignalsPerDay: 5,
      maxConcurrentTrades: 1,
      recordedLessons: true,
      pdfResources: true,
      communityAccess: "lifetime",
      futureUpdates: true,
      mentorship: false,
      mentorshipType: "content_access",
      oneOnOneSessionsPerMonth: 0,
      botAccess: false,
      challengeAccess: true,
      challengeDays: 30,
      challengePlatforms: ["mt5", "tradingview"],
      challengesPerMonth: 4,
      challengeMaxConcurrent: 2,
    },
    color: "pink",
    badge: "Lifetime Content",
  },
};

/**
 * Plan ids accepted by the bot / admin panel that are not purchasable tiers.
 *
 * The MT5 bot ships with `BOT_SIGNAL_TARGET_PLANS=premium,vip,pro,lifetime,Academy`
 * and admins type things like "Academy" or "Mentorship" in the admin panel. Without
 * this map those ids were silently dropped, so subscribers holding an `academy`
 * subscription or profile role never received a single signal email.
 */
export const PLAN_ALIASES = {
  academy: "premium",
  "academy-student": "premium",
  "academy-students": "premium",
  student: "premium",
  students: "premium",
  mentorship: "premium",
  "group-mentorship": "premium",
  "pro-mentorship": "pro",
  "private-mentorship": "pro",
  "vip-desk": "vip",
  "lifetime-academy": "lifetime",
  lifetime_academy: "lifetime",
};

export const PLAN_RANK = {
  free: 0,
  user: 0,
  premium: 1,
  academy: 1,
  vip: 2,
  pro: 3,
  lifetime: 4,
  admin: 99,
};

/**
 * Canonical tier id for anything an admin/bot may send us.
 * Returns "" when the value is not a known plan or alias.
 */
export function resolvePlanId(value) {
  const raw = String(value ?? "")
    .trim()
    .toLowerCase()
    .replace(/\s+/g, "-");
  if (!raw) return "";
  const tier = getPricingTier(raw);
  if (tier) return tier.id;
  const alias = PLAN_ALIASES[raw];
  if (alias && getPricingTier(alias)) return alias;
  return "";
}

/** Every stored spelling that should match a canonical plan id. */
export function planAliasesFor(value) {
  const canonical = resolvePlanId(value);
  if (!canonical) return [];
  const aliases = Object.entries(PLAN_ALIASES)
    .filter(([, target]) => target === canonical)
    .map(([alias]) => alias);
  return [...new Set([canonical, ...aliases])];
}

/** Rank of a plan id (aliases included). Unknown values rank 0. */
export function planRank(value) {
  const canonical = resolvePlanId(value);
  if (canonical) return PLAN_RANK[canonical] ?? 0;
  return PLAN_RANK[String(value || "").trim().toLowerCase()] ?? 0;
}

export function isPaidPlan(value) {
  return planRank(value) > 0;
}

/** Demo-challenge limits for a plan, defaulting to "no access". */
export function getChallengeRules(planOrTier) {
  const tier =
    typeof planOrTier === "string"
      ? getPricingTier(resolvePlanId(planOrTier) || planOrTier)
      : planOrTier;
  const features = tier?.features || {};
  const platforms = Array.isArray(features.challengePlatforms)
    ? features.challengePlatforms
    : [];
  return {
    plan: tier?.id || "",
    enabled: Boolean(features.challengeAccess) && platforms.length > 0,
    days: normalizeBotLimit(features.challengeDays, 0),
    platforms,
    perMonth: normalizeBotLimit(features.challengesPerMonth, 0),
    maxConcurrent: normalizeBotLimit(features.challengeMaxConcurrent, 0),
  };
}

export const BOT_UNLIMITED_LIMIT = 1000000;

export function normalizeBotLimit(value, fallback = 0) {
  if (value === "unlimited" || value === Infinity) return BOT_UNLIMITED_LIMIT;
  const numeric = Number(value);
  if (!Number.isFinite(numeric) || numeric < 0) return fallback;
  return Math.floor(numeric);
}

export function getPricingTier(tierId) {
  return PRICING_TIERS[String(tierId || "").toUpperCase()] || null;
}

export function getBotTierDefaults(tierId) {
  const tier = getPricingTier(tierId || "free") || PRICING_TIERS.FREE;
  const features = tier.features || {};
  return {
    botTier: tier.id,
    botMaxSignalsPerDay: normalizeBotLimit(features.maxSignalsPerDay, 0),
    botMaxConcurrentTrades: normalizeBotLimit(features.maxConcurrentTrades, 0),
    botSignalQuality: features.signalQuality || "none",
  };
}

export function getAllPricingTiers() {
  return Object.values(PRICING_TIERS);
}

export function hasFeatureAccess(userTier, featureName) {
  const tier = typeof userTier === "string" ? getPricingTier(userTier) : userTier;
  return Boolean(tier?.features?.[featureName]);
}

export function getBotSignalQuality(userTier) {
  const tier = typeof userTier === "string" ? getPricingTier(userTier) : userTier;
  return tier?.features?.signalQuality || "none";
}

export function getMaxConcurrentTrades(userTier) {
  const tier = typeof userTier === "string" ? getPricingTier(userTier) : userTier;
  return normalizeBotLimit(tier?.features?.maxConcurrentTrades, 0);
}

export function formatPrice(price) {
  if (price === 0) return "Free";
  return `NGN ${Number(price).toLocaleString("en-NG")}`;
}

export function getTierForDisplay(tierId) {
  const tier = getPricingTier(tierId);
  if (!tier) return null;
  return {
    id: tier.id,
    title: tier.displayName,
    price: formatPrice(tier.price),
    description: tier.description,
    features: Object.entries(tier.features)
      .filter(([, value]) => value === true || typeof value === "string")
      .map(([key]) => key),
    color: tier.color,
    badge: tier.badge,
  };
}

export default PRICING_TIERS;
