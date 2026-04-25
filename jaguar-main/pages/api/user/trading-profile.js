import crypto from "crypto";
import { createPagesServerClient } from "@supabase/auth-helpers-nextjs";
import { getSupabaseClient } from "../../../lib/supabaseClient";

const ALLOWED_PROFILES = new Set(["aggressive", "balanced", "conservative"]);

function normalizeProfile(value) {
  const normalized = String(value || "balanced").trim().toLowerCase();
  return ALLOWED_PROFILES.has(normalized) ? normalized : "balanced";
}

function buildToken() {
  return crypto.randomBytes(16).toString("hex");
}

export default async function handler(req, res) {
  const supabase = createPagesServerClient({ req, res });
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session?.user) {
    return res.status(401).json({ error: "not authenticated" });
  }

  const supabaseAdmin = getSupabaseClient({ server: true });
  const client = supabaseAdmin || supabase;
  if (!client) {
    return res.status(500).json({ error: "Supabase client not configured" });
  }

  if (req.method === "GET") {
    try {
      const { data, error } = await client
        .from("profiles")
        .select("trading_profile,tradingview_webhook_token")
        .eq("id", session.user.id)
        .maybeSingle();

      if (error) {
        if (error.code === "42703") {
          return res.status(200).json({
            tradingProfile: "balanced",
            token: null,
            columnsMissing: true,
          });
        }
        return res.status(500).json({ error: error.message || "failed to load profile" });
      }

      return res.status(200).json({
        tradingProfile: normalizeProfile(data?.trading_profile),
        token: data?.tradingview_webhook_token || null,
      });
    } catch (err) {
      return res.status(500).json({ error: err.message || "server error" });
    }
  }

  if (req.method === "POST") {
    const { tradingProfile, generateToken } = req.body || {};
    const updates = {};

    if (tradingProfile !== undefined) {
      updates.trading_profile = normalizeProfile(tradingProfile);
    }

    if (generateToken) {
      updates.tradingview_webhook_token = buildToken();
    }

    if (Object.keys(updates).length === 0) {
      return res.status(400).json({ error: "No updates provided" });
    }

    try {
      const { data, error } = await client
        .from("profiles")
        .update({ ...updates, updated_at: new Date().toISOString() })
        .eq("id", session.user.id)
        .select("trading_profile,tradingview_webhook_token")
        .maybeSingle();

      if (error) {
        if (error.code === "42703") {
          return res.status(200).json({
            ok: false,
            tradingProfile: "balanced",
            token: null,
            columnsMissing: true,
          });
        }
        return res.status(500).json({ error: error.message || "failed to update profile" });
      }

      return res.status(200).json({
        ok: true,
        tradingProfile: normalizeProfile(data?.trading_profile),
        token: data?.tradingview_webhook_token || null,
      });
    } catch (err) {
      return res.status(500).json({ error: err.message || "server error" });
    }
  }

  return res.status(405).json({ error: "Method not allowed" });
}

