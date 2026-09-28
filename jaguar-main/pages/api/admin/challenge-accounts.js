import { createPagesServerClient } from "@supabase/auth-helpers-nextjs";
import { getSupabaseClient } from "../../../lib/supabaseClient";
import { encryptMt5Password } from "../../../lib/mt5-crypto";
import { publicDemoAccount } from "../../../lib/challenges";

function missingTable(error) {
  const message = String(error?.message || "").toLowerCase();
  return error?.code === "42P01" || message.includes("does not exist") || message.includes("schema cache");
}

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

  const role = String(profile?.role || "user").toLowerCase();
  const adminEmail = (
    process.env.SUPER_ADMIN_EMAIL ||
    process.env.NEXT_PUBLIC_ADMIN_EMAIL ||
    ""
  ).toLowerCase();
  const userEmail = String(session.user.email || "").toLowerCase();
  if (role !== "admin" && !(adminEmail && userEmail === adminEmail)) {
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
      const { data, error } = await supabaseAdmin
        .from("challenge_demo_accounts")
        .select("*")
        .order("created_at", { ascending: false })
        .limit(200);
      if (error) throw error;
      return res.status(200).json({ accounts: (data || []).map(publicDemoAccount) });
    }

    if (req.method !== "POST") {
      return res.status(405).json({ error: "Method not allowed" });
    }

    const { action } = req.body || {};
    if (!action) return res.status(400).json({ error: "action is required" });

    if (action === "add") {
      const platform = String(req.body.platform || "").trim().toLowerCase();
      if (!["mt5", "tradingview"].includes(platform)) {
        return res.status(400).json({ error: "platform must be mt5 or tradingview" });
      }
      const login = String(req.body.login || "").trim();
      const password = String(req.body.password || "");
      const tradingviewUrl = String(req.body.tradingviewUrl || "").trim();
      if (platform === "mt5" && (!login || !password)) {
        return res.status(400).json({ error: "MT5 demo accounts need a login and password" });
      }
      if (platform === "tradingview" && !tradingviewUrl && !req.body.tradingviewUsername) {
        return res.status(400).json({ error: "TradingView entries need an invite link or a username" });
      }
      if (password && !process.env.MT5_CREDENTIALS_SECRET && process.env.NODE_ENV === "production") {
        return res.status(503).json({ error: "credential encryption is not configured" });
      }

      const now = new Date().toISOString();
      const payload = {
        platform,
        label: String(req.body.label || "").trim().slice(0, 120) || null,
        login: login || null,
        server: String(req.body.server || "").trim().slice(0, 120) || null,
        tradingview_url: tradingviewUrl || null,
        tradingview_username: String(req.body.tradingviewUsername || "").trim().slice(0, 120) || null,
        notes: String(req.body.notes || "").trim().slice(0, 400) || null,
        status: "available",
        created_at: now,
        updated_at: now,
      };
      if (password) Object.assign(payload, encryptMt5Password(password));

      const { data, error } = await supabaseAdmin
        .from("challenge_demo_accounts")
        .insert(payload)
        .select("*")
        .maybeSingle();
      if (error) {
        if (String(error.code) === "23505") {
          return res.status(409).json({ error: "That login already exists in the pool" });
        }
        return res.status(500).json({ error: error.message });
      }
      return res.status(200).json({ ok: true, account: publicDemoAccount(data) });
    }

    const id = String(req.body.id || "").trim();
    if (!id) return res.status(400).json({ error: "id is required" });

    if (action === "retire" || action === "activate") {
      const { data: existing } = await supabaseAdmin
        .from("challenge_demo_accounts")
        .select("*")
        .eq("id", id)
        .maybeSingle();
      if (!existing) return res.status(404).json({ error: "demo account not found" });
      if (action === "activate" && existing.status === "assigned") {
        return res.status(409).json({ error: "This demo account is assigned to an active challenge" });
      }

      const { data, error } = await supabaseAdmin
        .from("challenge_demo_accounts")
        .update({
          status: action === "retire" ? "retired" : "available",
          assigned_challenge_id: action === "retire" ? existing.assigned_challenge_id : null,
          updated_at: new Date().toISOString(),
        })
        .eq("id", id)
        .select("*")
        .maybeSingle();
      if (error) return res.status(500).json({ error: error.message });
      return res.status(200).json({ ok: true, account: publicDemoAccount(data) });
    }

    if (action === "delete") {
      const { error } = await supabaseAdmin.from("challenge_demo_accounts").delete().eq("id", id);
      if (error) return res.status(500).json({ error: error.message });
      return res.status(200).json({ ok: true });
    }

    return res.status(400).json({ error: "unknown action" });
  } catch (error) {
    if (missingTable(error)) {
      return res.status(503).json({
        error:
          "Demo challenges are not installed. Run jaguar-main/sql/2026-09-28_student_challenges.sql in Supabase.",
        missingTable: true,
      });
    }
    return res.status(500).json({ error: error.message || String(error) });
  }
}

