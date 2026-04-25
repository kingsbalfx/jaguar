/**
 * TradingView webhook receiver.
 *
 * Use a per-user token to map unauthenticated webhooks -> Supabase user_id.
 *
 * POST /api/webhook/tradingview?token=...
 * Body JSON:
 *   { "symbol": "EURUSD", "direction": "BUY", "strategy": "my-strategy", ... }
 */

import { getSupabaseClient } from "../../../lib/supabaseClient";

function normalizeDirection(value) {
  const dir = String(value || "").trim().toUpperCase();
  if (dir === "BUY" || dir === "SELL") return dir;
  return null;
}

function normalizeSymbol(value) {
  const symbol = String(value || "").trim().toUpperCase();
  return symbol || null;
}

export default async function handler(req, res) {
  if (req.method !== "POST") {
    return res.status(405).json({ error: "Method not allowed" });
  }

  const supabaseAdmin = getSupabaseClient({ server: true });
  if (!supabaseAdmin) {
    return res.status(500).json({ error: "Supabase admin client not configured" });
  }

  const token =
    String(req.query.token || "").trim() ||
    String(req.body?.token || "").trim() ||
    String(req.headers["x-webhook-token"] || "").trim();

  const symbol = normalizeSymbol(req.body?.symbol);
  const direction = normalizeDirection(req.body?.direction);

  if (!symbol || !direction) {
    return res.status(400).json({ error: "symbol and direction are required (direction must be BUY or SELL)" });
  }

  let userId = null;
  if (token) {
    const { data, error } = await supabaseAdmin
      .from("profiles")
      .select("id")
      .eq("tradingview_webhook_token", token)
      .maybeSingle();

    if (error) {
      if (error.code === "42703") {
        return res.status(500).json({ error: "tradingview_webhook_token column missing; run migration 006" });
      }
      return res.status(500).json({ error: error.message || "failed to resolve token" });
    }
    userId = data?.id || null;
  }

  if (!userId) {
    return res.status(401).json({ error: "Invalid or missing token" });
  }

  try {
    const payload = req.body && typeof req.body === "object" ? req.body : {};
    const { error } = await supabaseAdmin.from("tradingview_signals").insert({
      user_id: userId,
      symbol,
      direction,
      payload,
      status: "pending",
      received_at: new Date().toISOString(),
    });

    if (error) {
      return res.status(500).json({ error: error.message || "failed to enqueue signal" });
    }

    return res.status(200).json({ ok: true, status: "queued", userId, symbol, direction });
  } catch (err) {
    return res.status(500).json({ error: err.message || "server error" });
  }
}

