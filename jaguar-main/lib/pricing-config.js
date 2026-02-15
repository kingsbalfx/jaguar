/**
 * PRICING CONFIGURATION - Centralized Pricing System
 * Aligns pricing across web (Paystack), bot signals, and mentorship
 * Domain: kingsbalfx.name.ng
 * All prices in NGN (₦)
 */

export const PRICING_TIERS = {
  FREE: {
    id: "free",
    name: "Free Trial",
    displayName: "Trial",
    price: 0,
    currency: "NGN",
    description: "Get started with trading signals",
    features: {
      signals: true,
      signalQuality: "standard",
      maxSignalsPerDay: 3,
      mentorship: false,
      communityAccess: "limited",
      lessonAccess: true,
      lessonFrequency: "weekly",
      tradingHistory: false,
      performanceAnalytics: false,
      prioritySupport: false,
      botAccess: false,
      maxConcurrentTrades: 0,
    },
    color: "yellow",
    badge: "Getting Started",
  },

  PREMIUM: {
    id: "premium",
    name: "Premium",
    displayName: "Premium",
    price: 90000,
    currency: "NGN",
    billingCycle: "monthly",
    description: "Professional trader toolkit",
    features: {
      signals: true,
      signalQuality: "premium",
      maxSignalsPerDay: 15,
      mentorship: false,
      communityAccess: "full",
      lessonAccess: true,
      lessonFrequency: "daily",
      tradingHistory: true,
      performanceAnalytics: true,
      prioritySupport: true,
      botAccess: true,
      maxConcurrentTrades: 5,
      botUpdates: "weekly",
    },
    color: "blue",
    badge: "Most Popular",
  },

  VIP: {
    id: "vip",
    name: "VIP",
    displayName: "VIP",
    price: 150000,
    currency: "NGN",
    billingCycle: "monthly",
    description: "Elite mentorship & trading",
    features: {
      signals: true,
      signalQuality: "vip",
      maxSignalsPerDay: 30,
      mentorship: true,
      mentorshipType: "group",
      groupSessionsPerMonth: 4,
      communityAccess: "vip",
      lessonAccess: true,
      lessonFrequency: "daily",
      tradingHistory: true,
      performanceAnalytics: true,
      prioritySupport: true,
      botAccess: true,
      maxConcurrentTrades: 10,
      botUpdates: "daily",
      strategyFeedback: true,
    },
    color: "purple",
    badge: "Elite",
  },

  PRO: {
    id: "pro",
    name: "Pro Trader",
    displayName: "Pro",
    price: 250000,
    currency: "NGN",
    billingCycle: "monthly",
    description: "Complete professional setup",
    features: {
      signals: true,
      signalQuality: "pro",
      maxSignalsPerDay: "unlimited",
      mentorship: true,
      mentorshipType: "one-on-one",
      oneOnOneSessionsPerMonth: 2,
      groupSessionsPerMonth: 8,
      communityAccess: "pro",
      lessonAccess: true,
      lessonFrequency: "daily",
      tradingHistory: true,
      performanceAnalytics: true,
      advancedAnalytics: true,
      prioritySupport: true,
      dedicatedSupport: true,
      botAccess: true,
      maxConcurrentTrades: 20,
      botUpdates: "hourly",
      strategyFeedback: true,
      customStrategies: true,
      apiAccess: true,
    },
    color: "indigo",
    badge: "Professional",
  },

  LIFETIME: {
    id: "lifetime",
    name: "Lifetime",
    displayName: "Lifetime",
    price: 500000,
    currency: "NGN",
    billingCycle: "one-time",
    description: "Lifetime access to everything",
    features: {
      signals: true,
      signalQuality: "pro",
      maxSignalsPerDay: "unlimited",
      mentorship: true,
      mentorshipType: "one-on-one",
      oneOnOneSessionsPerMonth: "unlimited",
      groupSessionsPerMonth: "unlimited",
      communityAccess: "lifetime",
      lessonAccess: true,
      lessonFrequency: "daily",
      tradingHistory: true,
      performanceAnalytics: true,
      advancedAnalytics: true,
      prioritySupport: true,
      dedicatedSupport: true,
      botAccess: true,
      maxConcurrentTrades: "unlimited",
      botUpdates: "real-time",
      strategyFeedback: true,
      customStrategies: true,
      apiAccess: true,
      futureUpdates: true,
    },
    color: "pink",
    badge: "Lifetime",
  },
};

/**
 * Get pricing tier by ID
 */
export function getPricingTier(tierId) {
  return PRICING_TIERS[tierId.toUpperCase()] || null;
}

/**
 * Get all pricing tiers
 */
export function getAllPricingTiers() {
  return Object.values(PRICING_TIERS);
}

/**
 * Check if user has feature access
 */
export function hasFeatureAccess(userTier, featureName) {
  const tier = typeof userTier === "string" ? getPricingTier(userTier) : userTier;
  if (!tier) return false;
  return tier.features[featureName] || false;
}

/**
 * Get bot signal quality based on tier
 */
export function getBotSignalQuality(userTier) {
  const tier = typeof userTier === "string" ? getPricingTier(userTier) : userTier;
  if (!tier) return "none";
  return tier.features.signalQuality || "none";
}

/**
 * Get max concurrent trades for tier
 */
export function getMaxConcurrentTrades(userTier) {
  const tier = typeof userTier === "string" ? getPricingTier(userTier) : userTier;
  if (!tier) return 0;
  const max = tier.features.maxConcurrentTrades;
  return max === "unlimited" ? Infinity : max || 0;
}

/**
 * Format price for display
 */
export function formatPrice(price, currency = "NGN") {
  if (price === 0) return "Free";
  return `₦${price.toLocaleString("en-NG")}`;
}

/**
 * Get tier for display on pricing page
 */
export function getTierForDisplay(tierId) {
  const tier = getPricingTier(tierId);
  if (!tier) return null;
  return {
    id: tier.id,
    title: tier.displayName,
    price: tier.price === 0 ? "Free" : formatPrice(tier.price),
    description: tier.description,
    features: Object.entries(tier.features)
      .filter(([key, val]) => val === true || typeof val === "string")
      .map(([key]) => key),
    color: tier.color,
    badge: tier.badge,
  };
}

export default PRICING_TIERS;
