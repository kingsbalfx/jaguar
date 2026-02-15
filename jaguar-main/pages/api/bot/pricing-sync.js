/**
 * BOT-WEB PRICING SYNCHRONIZATION API
 * Ensures bot signal quality and trade limits match web tier pricing
 * Domain: https://kingsbalfx.name.ng/api/bot/pricing-sync
 */

import { getSupabaseClient } from "../../lib/supabaseClient";
import { PRICING_TIERS } from "../../lib/pricing-config";

export default async function handler(req, res) {
  // Only allow GET and POST
  if (!["GET", "POST"].includes(req.method)) {
    return res.status(405).json({ error: "Method not allowed" });
  }

  try {
    // Verify admin API key for sensitive operations
    if (req.method === "POST") {
      const adminKey = req.headers["x-admin-api-key"];
      if (adminKey !== process.env.ADMIN_API_KEY) {
        return res.status(401).json({ error: "Unauthorized" });
      }
    }

    // GET /api/bot/pricing-sync - Fetch current pricing config
    if (req.method === "GET") {
      const supabase = getSupabaseClient({ server: true });

      // Get all pricing tiers from database if custom configured
      const { data: customTiers, error: tiersError } = await supabase
        .from("pricing_tiers")
        .select("*");

      if (tiersError && tiersError.code !== "PGRST116") {
        // PGRST116 = table doesn't exist, which is okay
        throw tiersError;
      }

      // Return current pricing config
      return res.status(200).json({
        status: "ok",
        timestamp: new Date().toISOString(),
        tiers: Object.values(PRICING_TIERS).map((t) => ({
          id: t.id,
          name: t.name,
          price: t.price,
          currency: t.currency,
          features: {
            maxSignalsPerDay: t.features.maxSignalsPerDay,
            maxConcurrentTrades: t.features.maxConcurrentTrades,
            signalQuality: t.features.signalQuality,
          },
        })),
      });
    }

    // POST /api/bot/pricing-sync - Sync user tier with bot settings
    if (req.method === "POST") {
      const { userId, tier } = req.body;

      if (!userId || !tier) {
        return res.status(400).json({
          error: "Missing required fields: userId, tier",
        });
      }

      const supabase = getSupabaseClient({ server: true });
      const tierConfig = PRICING_TIERS[tier.toUpperCase()];

      if (!tierConfig) {
        return res.status(404).json({ error: "Tier not found" });
      }

      // Update user's bot configuration in database
      const { error: updateError } = await supabase
        .from("profiles")
        .update({
          bot_tier: tier.toLowerCase(),
          bot_max_signals_per_day: tierConfig.features.maxSignalsPerDay,
          bot_max_concurrent_trades: tierConfig.features.maxConcurrentTrades,
          bot_signal_quality: tierConfig.features.signalQuality,
          bot_tier_updated_at: new Date().toISOString(),
        })
        .eq("id", userId);

      if (updateError) throw updateError;

      // Log the sync event
      await supabase.from("bot_logs").insert({
        event: "pricing_sync",
        payload: {
          userId,
          tier,
          tier_config: {
            maxSignals: tierConfig.features.maxSignalsPerDay,
            maxTrades: tierConfig.features.maxConcurrentTrades,
            quality: tierConfig.features.signalQuality,
          },
        },
      });

      return res.status(200).json({
        status: "ok",
        message: "Pricing synchronized",
        tier: tier.toLowerCase(),
        config: {
          maxSignalsPerDay: tierConfig.features.maxSignalsPerDay,
          maxConcurrentTrades: tierConfig.features.maxConcurrentTrades,
          signalQuality: tierConfig.features.signalQuality,
        },
      });
    }
  } catch (error) {
    console.error("[pricing-sync] Error:", error);
    return res.status(500).json({
      error: "Internal server error",
      message: error.message,
    });
  }
}
