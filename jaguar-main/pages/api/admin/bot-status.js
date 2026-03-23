import { createPagesServerClient } from "@supabase/auth-helpers-nextjs";
import { getSupabaseClient } from "../../../lib/supabaseClient";

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

  const role = (profile?.role || "user").toLowerCase();
  if (role !== "admin") {
    res.status(403).json({ error: "forbidden" });
    return null;
  }

  return { supabaseAdmin };
}

export default async function handler(req, res) {
  if (req.method !== "GET") {
    return res.status(405).json({ error: "Method not allowed" });
  }

  const ctx = await requireAdmin(req, res);
  if (!ctx) return;
  const { supabaseAdmin } = ctx;

  try {
    const baseUrl = process.env.BOT_API_INTERNAL || process.env.BOT_API_URL;
    if (!baseUrl) {
      return res.status(500).json({ error: "BOT_API_URL not configured" });
    }

    const [statusRes, logsRes] = await Promise.all([
      fetch(new URL("/status", baseUrl).toString()),
      supabaseAdmin
        .from("bot_logs")
        .select("id,event,payload,created_at")
        .order("created_at", { ascending: false })
        .limit(12),
    ]);

    const botStatus = statusRes.ok ? await statusRes.json() : null;
    const recentLogs = logsRes?.data || [];

    return res.status(200).json({
      bot: botStatus || {
        running: false,
        connected: false,
        last_error: `Bot status request failed with ${statusRes.status}`,
      },
      recentLogs,
      fetchedAt: new Date().toISOString(),
    });
  } catch (e) {
    return res.status(500).json({ error: e.message || String(e) });
  }
}
