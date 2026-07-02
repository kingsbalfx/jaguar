import { createPagesServerClient } from "@supabase/auth-helpers-nextjs";
import { getSupabaseClient } from "../../../lib/supabaseClient";
import { defaultSignalPauseMessage, getSignalGate, isSignalGateActive, saveSignalGate } from "../../../lib/signal-gate";

async function requireAdmin(req, res) {
  const supabase = createPagesServerClient({ req, res });
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session?.user) {
    res.status(401).json({ error: "not authenticated" });
    return null;
  }

  const supabaseAdmin = getSupabaseClient({ server: true });
  if (!supabaseAdmin) {
    res.status(500).json({ error: "Supabase admin client not configured" });
    return null;
  }

  const { data: profile } = await supabaseAdmin
    .from("profiles")
    .select("role")
    .eq("id", session.user.id)
    .maybeSingle();

  if (String(profile?.role || "user").toLowerCase() !== "admin") {
    res.status(403).json({ error: "forbidden" });
    return null;
  }

  return { supabaseAdmin };
}

export default async function handler(req, res) {
  const ctx = await requireAdmin(req, res);
  if (!ctx) return;

  try {
    if (req.method === "GET") {
      const { gate, active, missingTable } = await getSignalGate(ctx.supabaseAdmin);
      return res.status(200).json({ gate, active, missingTable });
    }

    if (req.method === "POST") {
      const { paused, resumeAt, message } = req.body || {};
      const gate = await saveSignalGate(ctx.supabaseAdmin, {
        paused: Boolean(paused),
        resume_at: resumeAt || null,
        message: String(message || "").trim() || defaultSignalPauseMessage(resumeAt),
      });
      return res.status(200).json({ gate, active: isSignalGateActive(gate) });
    }

    return res.status(405).json({ error: "Method not allowed" });
  } catch (error) {
    const msg = String(error?.message || "").toLowerCase();
    if (error?.code === "42P01" || msg.includes("does not exist") || msg.includes("schema cache")) {
      return res.status(500).json({
        error: "Signal pause settings table is missing. Run jaguar-main/sql/2026-07-02_signal_delivery.sql in Supabase.",
        missingTable: true,
      });
    }
    return res.status(500).json({ error: error.message || "Unable to update signal pause settings" });
  }
}
