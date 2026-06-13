import { createPagesServerClient } from "@supabase/auth-helpers-nextjs";
import { getSupabaseClient } from "../../../lib/supabaseClient";
import { encryptMt5Password } from "../../../lib/mt5-crypto";
import { getPaidAccess } from "../../../lib/subscription-status";
import { getPricingTier } from "../../../lib/pricing-config";

export default async function handler(req, res) {
  if (req.method !== "POST") return res.status(405).json({ error: "Method not allowed" });
  try {
    const supabase = createPagesServerClient({ req, res });
    const { data: { session } } = await supabase.auth.getSession();
    if (!session?.user) return res.status(401).json({ error: "not authenticated" });
    const { login, password, server, consentAccepted } = req.body || {};
    if (consentAccepted !== true) return res.status(400).json({ error: "risk consent is required" });
    if (![login, password, server].every((value) => String(value || "").trim())) {
      return res.status(400).json({ error: "login, password, and server are required" });
    }
    if (!process.env.MT5_CREDENTIALS_SECRET && process.env.NODE_ENV === "production") {
      return res.status(503).json({ error: "credential encryption is not configured" });
    }
    const supabaseAdmin = getSupabaseClient({ server: true });
    if (!supabaseAdmin) return res.status(500).json({ error: "Supabase admin client not configured" });
    const { data: profile } = await supabaseAdmin
      .from("profiles")
      .select("role")
      .eq("id", session.user.id)
      .maybeSingle();
    const role = String(profile?.role || "user").toLowerCase();
    const access = await getPaidAccess({ supabaseAdmin, email: session.user.email, role });
    const testingAllowed = access.plans?.some((plan) => {
      const tier = getPricingTier(plan);
      return tier?.features?.botAccess || tier?.features?.privateTestingOnly;
    });
    if (!access.active || !testingAllowed) {
      return res.status(403).json({ error: "Private bot testing is not included in your active plan" });
    }
    const forwarded = String(req.headers["x-forwarded-for"] || "").split(",")[0].trim();
    const now = new Date().toISOString();
    const payload = {
      user_id: session.user.id,
      email: session.user.email,
      login: String(login).trim(),
      server: String(server).trim(),
      status: "pending",
      consent_accepted: true,
      risk_notice_version: "2026-06-13",
      submitted_ip: forwarded || req.socket?.remoteAddress || null,
      user_agent: req.headers["user-agent"] || null,
      ...encryptMt5Password(password),
      created_at: now,
      updated_at: now,
    };
    const { error } = await supabaseAdmin.from("mt5_submissions").insert(payload);
    if (error) return res.status(500).json({ error: error.message || "failed to submit credentials" });
    return res.status(200).json({ ok: true });
  } catch (err) {
    console.error("mt5 submission error:", err);
    return res.status(500).json({ error: err.message || "server error" });
  }
}
