import { createPagesServerClient } from "@supabase/auth-helpers-nextjs";
import { getSupabaseClient } from "../../../../lib/supabaseClient";
import { deliverBotSignal, signalDeliverySqlRequired } from "../../../../lib/signal-delivery";

export default async function handler(req, res) {
  if (req.method !== "POST") {
    return res.status(405).json({ error: "Method not allowed" });
  }

  const supabase = createPagesServerClient({ req, res });
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session?.user) return res.status(401).json({ error: "not authenticated" });

  const supabaseAdmin = getSupabaseClient({ server: true });
  if (!supabaseAdmin) return res.status(500).json({ error: "Supabase admin client not configured" });

  const { data: profile } = await supabaseAdmin
    .from("profiles")
    .select("role")
    .eq("id", session.user.id)
    .maybeSingle();

  if (String(profile?.role || "user").toLowerCase() !== "admin") {
    return res.status(403).json({ error: "forbidden" });
  }

  try {
    const result = await deliverBotSignal({ supabaseAdmin, payload: req.body || {} });
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
