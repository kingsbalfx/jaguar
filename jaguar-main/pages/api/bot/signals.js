import { getSupabaseClient } from "../../../lib/supabaseClient";
import { deliverBotSignal, signalDeliverySqlRequired } from "../../../lib/signal-delivery";

function authorized(req) {
  const provided =
    String(req.headers["x-admin-api-key"] || "").trim() ||
    String(req.headers["x-bot-api-token"] || "").trim() ||
    String(req.headers["x-bot-signal-secret"] || "").trim();
  const allowed = [
    process.env.ADMIN_API_KEY,
    process.env.BOT_API_TOKEN,
    process.env.BOT_SIGNAL_SECRET,
  ].map((value) => String(value || "").trim()).filter(Boolean);
  return Boolean(provided && allowed.includes(provided));
}

export default async function handler(req, res) {
  if (req.method !== "POST") {
    return res.status(405).json({ error: "Method not allowed" });
  }
  if (!authorized(req)) {
    return res.status(401).json({ error: "Unauthorized signal sender" });
  }

  const supabaseAdmin = getSupabaseClient({ server: true });
  if (!supabaseAdmin) {
    return res.status(500).json({ error: "Supabase admin client not configured" });
  }

  try {
    const result = await deliverBotSignal({
      supabaseAdmin,
      payload: req.body || {},
    });
    return res.status(200).json({ ok: true, ...result });
  } catch (error) {
    if (error.code === "SIGNAL_DELIVERY_PAUSED") {
      return res.status(423).json({ error: error.message, paused: true, gate: error.gate || null });
    }
    if (signalDeliverySqlRequired(error)) {
      return res.status(503).json({
        error: "Signal delivery SQL is not installed. Run jaguar-main/sql/2026-07-02_signal_delivery.sql in Supabase.",
        details: error.message || String(error),
      });
    }
    return res.status(400).json({ error: error.message || "Unable to deliver signal" });
  }
}
