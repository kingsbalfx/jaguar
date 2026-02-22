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
  const ctx = await requireAdmin(req, res);
  if (!ctx) return;
  const { supabaseAdmin } = ctx;

  if (req.method === "GET") {
    const { data, error } = await supabaseAdmin
      .from("content_items")
      .select("*")
      .order("created_at", { ascending: false });
    if (error) return res.status(500).json({ error: "failed to load content" });
    return res.status(200).json({ items: data || [] });
  }

  if (req.method === "POST") {
    const {
      title,
      description,
      segment,
      mediaType,
      mediaUrl,
      storagePath,
      publicUrl,
      body,
      isPublished,
    } = req.body || {};

    if (!title || !mediaType) {
      return res.status(400).json({ error: "title and mediaType are required" });
    }

    const { data, error } = await supabaseAdmin
      .from("content_items")
      .insert({
        title,
        description: description || null,
        segment: segment || "all",
        media_type: mediaType,
        media_url: mediaUrl || null,
        storage_path: storagePath || null,
        public_url: publicUrl || null,
        body: body || null,
        is_published: isPublished !== false,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      })
      .select("*")
      .maybeSingle();

    if (error) return res.status(500).json({ error: error.message || "failed to save content" });
    return res.status(200).json({ item: data });
  }

  return res.status(405).json({ error: "Method not allowed" });
}
