import { createPagesServerClient } from "@supabase/auth-helpers-nextjs";
import { getSupabaseClient } from "../../../lib/supabaseClient";

export default async function handler(req, res) {
  if (req.method !== "GET") return res.status(405).end();

  try {
    const supabase = createPagesServerClient({ req, res });
    const {
      data: { session },
    } = await supabase.auth.getSession();

    if (!session || !session.user) return res.status(401).json({ error: "not authenticated" });

    const supabaseAdmin = getSupabaseClient({ server: true });
    const userId = session.user.id;
    const { data: profile } = await supabaseAdmin.from("profiles").select("role").eq("id", userId).maybeSingle();
    const role = (profile?.role || "user").toLowerCase();
    if (role !== "admin") return res.status(403).json({ error: "forbidden" });

    const limit = Number(req.query.limit) || 100;
    const { data, error } = await supabaseAdmin.from("bot_logs").select("*").order("created_at", { ascending: false }).limit(limit);

    if (error) {
      return res.status(500).json({ error: "failed to fetch logs" });
    }

    return res.status(200).json({ logs: data || [] });
  } catch (e) {
    console.error(e);
    return res.status(500).json({ error: e.message || String(e) });
  }
}
