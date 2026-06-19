import { createPagesServerClient } from "@supabase/auth-helpers-nextjs";
import { getSupabaseClient } from "../../../lib/supabaseClient";
import { defaultClosureMessage, getRegistrationGate, isRegistrationGateActive, saveRegistrationGate } from "../../../lib/registration-gate";

async function requireAdmin(req, res) {
  const supabase = createPagesServerClient({ req, res });
  const { data: { session } } = await supabase.auth.getSession();
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

  const role = String(profile?.role || "user").toLowerCase();
  const adminEmail = String(process.env.NEXT_PUBLIC_ADMIN_EMAIL || process.env.SUPER_ADMIN_EMAIL || process.env.ADMIN_EMAIL || "").toLowerCase();
  const userEmail = String(session.user.email || "").toLowerCase();
  const isAdminEmail = adminEmail && userEmail === adminEmail;

  if (isAdminEmail && role !== "admin") {
    try {
      await supabaseAdmin.from("profiles").upsert({
        id: session.user.id,
        email: session.user.email,
        role: "admin",
        updated_at: new Date().toISOString(),
      });
    } catch {
      // allow admin email override even if profile write fails
    }
  }

  if (role !== "admin" && !isAdminEmail) {
    res.status(403).json({ error: "forbidden" });
    return null;
  }

  return { supabaseAdmin };
}

export default async function handler(req, res) {
  const ctx = await requireAdmin(req, res);
  if (!ctx) return;
  const { supabaseAdmin } = ctx;

  try {
    if (req.method === "GET") {
      const { gate, missingTable } = await getRegistrationGate(supabaseAdmin);
      return res.status(200).json({ gate, active: isRegistrationGateActive(gate), missingTable });
    }

    if (req.method === "POST") {
      const { paused, reopenAt, message } = req.body || {};
      const normalized = {
        paused: Boolean(paused),
        reopen_at: reopenAt || null,
        message: String(message || "").trim() || defaultClosureMessage(reopenAt),
      };
      const gate = await saveRegistrationGate(supabaseAdmin, normalized);
      return res.status(200).json({ gate, active: isRegistrationGateActive(gate) });
    }

    return res.status(405).json({ error: "Method not allowed" });
  } catch (err) {
    const msg = String(err?.message || "");
    if (err?.code === "42P01" || msg.toLowerCase().includes("does not exist") || msg.toLowerCase().includes("schema cache")) {
      return res.status(500).json({
        error: "Registration gate table is missing. Run sql/2026-06-19_registration_gate.sql in Supabase.",
        missingTable: true,
      });
    }
    console.error("admin registration gate error:", err);
    return res.status(500).json({ error: err.message || "failed to update registration gate" });
  }
}
