/**
 * BOT MANAGEMENT API
 * Comprehensive bot control and monitoring
 * Endpoint: https://kingsbalfx.name.ng/api/admin/bot-control
 */

import { getSupabaseClient } from "../../../lib/supabaseClient";

export default async function handler(req, res) {
  // Verify admin API key
  const adminKey = req.headers["x-admin-api-key"];
  if (adminKey !== process.env.ADMIN_API_KEY) {
    return res.status(401).json({ error: "Unauthorized" });
  }

  const { action, userId, tier, forceSync } = req.body || {};

  try {
    const supabase = getSupabaseClient({ server: true });

    // ========== BOT STATUS ==========
    if (req.method === "GET" && !action) {
      // Get overall bot health
      try {
        const botBaseUrl =
          process.env.BOT_API_INTERNAL ||
          process.env.BOT_API_URL ||
          "https://your-bot-host:8000";
        const botHealth = await fetch(`${botBaseUrl}/health`);
        const botStatus = await botHealth.json();

        const { data: botLogs, error: logsError } = await supabase
          .from("bot_logs")
          .select("event,created_at")
          .order("created_at", { ascending: false })
          .limit(10);

        const { data: signals, error: signalsError } = await supabase
          .from("bot_signals")
          .select("id,status")
          .order("created_at", { ascending: false })
          .limit(1);

        return res.status(200).json({
          status: "ok",
          bot: {
            running: botStatus.running,
            health: botStatus.status,
            lastActivity: botLogs?.[0]?.created_at,
            recentEvents: botLogs?.length || 0,
            pendingSignals: signals?.filter((s) => s.status === "pending")?.length || 0,
          },
          timestamp: new Date().toISOString(),
        });
      } catch (botError) {
        console.error("Bot health check failed:", botError);
        return res.status(200).json({
          status: "ok",
          bot: {
            running: false,
            health: "offline",
            error: botError.message,
          },
        });
      }
    }

    // ========== SYNC USER PRICING ==========
    if (action === "sync-pricing" && userId && tier) {
      const tierUpper = tier.toUpperCase();

      // Update or create pricing sync in database
      const { error: syncError } = await supabase
        .from("profiles")
        .update({
          bot_tier: tier.toLowerCase(),
          bot_tier_updated_at: new Date().toISOString(),
        })
        .eq("id", userId);

      if (syncError) throw syncError;

      // Log the sync event
      await supabase.from("bot_logs").insert({
        event: "pricing_sync",
        payload: {
          admin_sync: true,
          userId,
          tier: tier.toLowerCase(),
        },
      });

      return res.status(200).json({
        status: "ok",
        message: "User pricing synchronized",
        userId,
        tier: tier.toLowerCase(),
      });
    }

    // ========== SYNC ALL USERS ==========
    if (action === "sync-all-users") {
      // Get all users with subscriptions
      const { data: subscriptions, error: subsError } = await supabase
        .from("subscriptions")
        .select("email,plan,status")
        .eq("status", "active");

      if (subsError) throw subsError;

      let synced = 0;
      for (const sub of subscriptions || []) {
        const { data: profile } = await supabase
          .from("profiles")
          .select("id")
          .eq("email", sub.email)
          .single();

        if (profile) {
          await supabase
            .from("profiles")
            .update({
              bot_tier: sub.plan.toLowerCase(),
              bot_tier_updated_at: new Date().toISOString(),
            })
            .eq("id", profile.id);

          synced++;
        }
      }

      await supabase.from("bot_logs").insert({
        event: "bulk_pricing_sync",
        payload: {
          admin_action: "sync_all_users",
          synced_count: synced,
        },
      });

      return res.status(200).json({
        status: "ok",
        message: "All users synced",
        totalSynced: synced,
      });
    }

    // ========== GET BOT LOGS ==========
    if (action === "get-logs") {
      const limit = req.body.limit || 100;
      const { data: logs, error: logsError } = await supabase
        .from("bot_logs")
        .select("id,event,payload,created_at")
        .order("created_at", { ascending: false })
        .limit(limit);

      if (logsError) throw logsError;

      return res.status(200).json({
        status: "ok",
        logs: logs || [],
        count: logs?.length || 0,
      });
    }

    // ========== GET BOT SIGNALS ==========
    if (action === "get-signals") {
      const limit = req.body.limit || 50;
      const status = req.body.status || null;

      let query = supabase
        .from("bot_signals")
        .select("id,symbol,direction,entry_price,stop_loss,take_profit,signal_quality,status,created_at")
        .order("created_at", { ascending: false })
        .limit(limit);

      if (status) {
        query = query.eq("status", status);
      }

      const { data: signals, error: signalsError } = await query;

      if (signalsError) throw signalsError;

      return res.status(200).json({
        status: "ok",
        signals: signals || [],
        count: signals?.length || 0,
      });
    }

    // ========== GET BOT ERRORS ==========
    if (action === "get-errors") {
      const limit = req.body.limit || 50;
      const { data: errors, error: errorsError } = await supabase
        .from("bot_errors")
        .select("id,error_type,error_message,severity,created_at")
        .order("created_at", { ascending: false })
        .limit(limit);

      if (errorsError) throw errorsError;

      return res.status(200).json({
        status: "ok",
        errors: errors || [],
        count: errors?.length || 0,
        criticalCount: errors?.filter((e) => e.severity === "critical")?.length || 0,
      });
    }

    // ========== GET USER BOT CONFIG ==========
    if (action === "get-user-config" && userId) {
      const { data: profile, error: profileError } = await supabase
        .from("profiles")
        .select("bot_tier,bot_max_signals_per_day,bot_max_concurrent_trades,bot_signal_quality")
        .eq("id", userId)
        .single();

      if (profileError) throw profileError;

      return res.status(200).json({
        status: "ok",
        config: profile || null,
        userId,
      });
    }

    // ========== GET TRADING STATISTICS ==========
    if (action === "get-stats") {
      const { data: signals } = await supabase
        .from("bot_signals")
        .select("id,status,direction")
        .order("created_at", { ascending: false })
        .limit(1000);

      const { data: logs } = await supabase
        .from("bot_logs")
        .select("event")
        .order("created_at", { ascending: false })
        .limit(1000);

      const stats = {
        totalSignals: signals?.length || 0,
        pendingSignals: signals?.filter((s) => s.status === "pending")?.length || 0,
        executedSignals: signals?.filter((s) => s.status === "executed")?.length || 0,
        closedSignals: signals?.filter((s) => s.status === "closed")?.length || 0,
        buySignals: signals?.filter((s) => s.direction === "buy")?.length || 0,
        sellSignals: signals?.filter((s) => s.direction === "sell")?.length || 0,
        eventBreakdown: logs?.reduce((acc, log) => {
          acc[log.event] = (acc[log.event] || 0) + 1;
          return acc;
        }, {}),
      };

      return res.status(200).json({
        status: "ok",
        stats,
      });
    }

    return res.status(400).json({ error: "Invalid action" });
  } catch (error) {
    console.error("[bot-control] Error:", error);
    return res.status(500).json({
      error: "Internal server error",
      message: error.message,
    });
  }
}
