import { getURL } from "../../../lib/getURL";
import { PRICING_TIERS } from "../../../lib/pricing-config";
import { initKorapayCharge } from "../../../lib/korapay";

function getTierById(plan) {
  if (!plan) return null;
  const planId = String(plan).toLowerCase();
  return Object.values(PRICING_TIERS).find((tier) => tier.id === planId) || null;
}

function generateReference(plan) {
  const suffix = Math.random().toString(36).slice(2, 8).toUpperCase();
  return `KBS_${plan}_${Date.now()}_${suffix}`;
}

export default async function handler(req, res) {
  if (req.method !== "POST") {
    res.setHeader("Allow", "POST");
    return res.status(405).json({ error: "Method not allowed" });
  }

  const { plan, email, userId } = req.body || {};
  const tier = getTierById(plan);
  if (!tier) return res.status(400).json({ error: "Invalid plan" });
  if (!email) {
    return res.status(400).json({ error: "Buyer email required" });
  }
  if (!tier.price || tier.price <= 0) {
    return res.status(400).json({ error: "Selected plan is free" });
  }

  try {
    const baseUrl = getURL().replace(/\/$/, "");
    const reference = generateReference(tier.id);

    const redirectUrl = `${baseUrl}/checkout/success?plan=${encodeURIComponent(
      tier.id
    )}&reference=${encodeURIComponent(reference)}`;

    const init = await initKorapayCharge({
      amount: tier.price,
      currency: tier.currency || "NGN",
      email,
      reference,
      redirectUrl,
      metadata: {
        plan: tier.id,
        planName: tier.name,
        planPrice: tier.price,
        email,
        userId,
      },
    });

    if (!init.ok) {
      return res.status(500).json({ error: init.error || "Korapay initialization failed", details: init.raw });
    }

    return res.status(200).json({
      checkout_url: init.checkoutUrl,
      reference: init.reference || reference,
    });
  } catch (err) {
    console.error("korapay/init exception:", err);
    return res.status(500).json({ error: "Server error" });
  }
}
