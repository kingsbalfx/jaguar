import { PRICING_TIERS } from "./pricing-config.js";

export const SUCCESSFUL_PAYMENT_STATUSES = new Set(["success", "successful", "completed", "paid", "approved"]);

export function normalizePaymentAmount(amount, plan) {
  const numeric = Number(amount);
  const planPrice = PRICING_TIERS[String(plan || "").toUpperCase()]?.price || 0;
  if (!Number.isFinite(numeric) || numeric <= 0) return planPrice;
  if (planPrice && numeric === planPrice) return numeric;
  if (planPrice && numeric === planPrice * 100) return planPrice;
  const looksLikeKobo = Number.isInteger(numeric) && numeric >= 1000000 && numeric % 100 === 0;
  return looksLikeKobo ? numeric / 100 : numeric;
}

export function validatePlanPayment({ amount, currency, plan }) {
  const tier = PRICING_TIERS[String(plan || "").toUpperCase()];
  const numeric = Number(amount);
  if (!tier || !tier.price || !Number.isFinite(numeric) || numeric <= 0) {
    return { valid: false, error: "Invalid paid plan or payment amount" };
  }
  if (currency && String(currency).toUpperCase() !== "NGN") {
    return { valid: false, error: "Payment currency does not match the selected plan" };
  }
  const normalizedAmount = normalizePaymentAmount(numeric, plan);
  if (normalizedAmount !== tier.price) {
    return { valid: false, error: "Payment amount does not match the selected plan" };
  }
  return { valid: true, tier, normalizedAmount };
}
