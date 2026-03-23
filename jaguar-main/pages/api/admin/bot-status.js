import { createPagesServerClient } from "@supabase/auth-helpers-nextjs";
import { getSupabaseClient } from "../../../lib/supabaseClient";

function buildBotUrl(baseUrl, endpoint) {
  const cleanBase = String(baseUrl || "").replace(/\/+$/, "");
  const cleanEndpoint = String(endpoint || "").replace(/^\/+/, "");
  return `${cleanBase}/${cleanEndpoint}`;
}

async function loadBotLogs(supabaseAdmin) {
  const primary = await supabaseAdmin
    .from("bot_logs")
    .select("id,event,payload,created_at")
    .order("created_at", { ascending: false })
    .limit(12);

  if (!primary.error) {
    return primary.data || [];
  }

  const msg = String(primary.error?.message || "").toLowerCase();
  if (!msg.includes("created_at")) {
    throw new Error(primary.error.message || "failed to load bot logs");
  }

  const fallback = await supabaseAdmin
    .from("bot_logs")
    .select("id,event,payload")
    .limit(12);

  if (fallback.error) {
    throw new Error(fallback.error.message || "failed to load bot logs");
  }

  return fallback.data || [];
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

    const [statusRes, recentLogs] = await Promise.all([
      fetch(buildBotUrl(baseUrl, "status")),
      loadBotLogs(supabaseAdmin),
    ]);

    const botStatus = statusRes.ok ? await statusRes.json() : null;

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
