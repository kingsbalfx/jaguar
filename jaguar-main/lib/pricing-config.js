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
      mentorship: false,
      lessonAccess: true,
      sampleContent: true,
      riskWarning: true,
      botAccess: false,
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
      structuredLessons: true,
      pdfResources: true,
      communityAccess: "group",
      weeklyLiveClass: true,
      basicAssignmentAccess: true,
      mentorship: true,
      mentorshipType: "group",
      groupSessionsPerMonth: 4,
      botAccess: false,
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
      recordedLessons: true,
      pdfResources: true,
      communityAccess: "lifetime",
      futureUpdates: true,
      mentorship: false,
      mentorshipType: "content_access",
      oneOnOneSessionsPerMonth: 0,
      botAccess: false,
    },
    color: "pink",
    badge: "Lifetime Content",
  },
};

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
