import { PRICING_TIERS } from "./pricing-config";

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
