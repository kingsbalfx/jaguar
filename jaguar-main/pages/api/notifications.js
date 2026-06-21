import { createPagesServerClient } from "@supabase/auth-helpers-nextjs";
import { getSupabaseClient } from "../../lib/supabaseClient";

export default async function handler(req, res) {
  const supabase = createPagesServerClient({ req, res });
  const { data: { session } } = await supabase.auth.getSession();
  if (!session?.user && req.method === "GET") return res.status(200).json({ notifications: [] });
  if (!session?.user) return res.status(401).json({ error: "not authenticated" });
  const admin = getSupabaseClient({ server: true });
  if (!admin) return res.status(500).json({ error: "Supabase admin client not configured" });

  if (req.method === "GET") {
    const { data, error } = await admin
      .from("user_notifications")
      .select("id,title,body,link,notification_type,read_at,created_at")
      .eq("user_id", session.user.id)
      .order("created_at", { ascending: false })
      .limit(20);
    if (error?.code === "42P01" || error?.code === "42703") {
      return res.status(200).json({ notifications: [], missingTable: true });
    }
    if (error) return res.status(500).json({ error: error.message });
    return res.status(200).json({ notifications: data || [] });
  }

  if (req.method === "PUT") {
    const id = String(req.body?.id || "").trim();
    const query = admin
      .from("user_notifications")
      .update({ read_at: new Date().toISOString() })
      .eq("user_id", session.user.id);
    const result = id ? await query.eq("id", id) : await query.is("read_at", null);
    if (result.error?.code === "42P01" || result.error?.code === "42703") return res.status(200).json({ ok: true, missingTable: true });
    if (result.error) return res.status(500).json({ error: result.error.message });
    return res.status(200).json({ ok: true });
  }

  return res.status(405).json({ error: "Method not allowed" });
}
