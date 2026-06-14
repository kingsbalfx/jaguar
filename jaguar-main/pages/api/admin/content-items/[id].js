import { createPagesServerClient } from "@supabase/auth-helpers-nextjs";
import { getSupabaseClient } from "../../../../lib/supabaseClient";

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
  const adminEmail = (process.env.NEXT_PUBLIC_ADMIN_EMAIL || process.env.SUPER_ADMIN_EMAIL || "").toLowerCase();
  const userEmail = (session.user.email || "").toLowerCase();
  const isAdminEmail = adminEmail && userEmail === adminEmail;

  if (isAdminEmail && role !== "admin") {
    try {
      await supabaseAdmin.from("profiles").update({ role: "admin" }).eq("id", session.user.id);
    } catch {
      // allow override even if profile update fails
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
  const { id } = req.query;

  if (!id) return res.status(400).json({ error: "missing id" });

  if (req.method === "PUT") {
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

    const updates = {
      title,
      description: description || null,
      segment: segment || "all",
      media_type: mediaType,
      media_url: mediaUrl || null,
      body: body || null,
      is_published: isPublished !== false,
      updated_at: new Date().toISOString(),
    };

    // Editing lesson details without uploading a replacement must keep the
    // existing storage file available to subscribers.
    if (storagePath) updates.storage_path = storagePath;
    if (publicUrl) updates.public_url = publicUrl;

    const { data, error } = await supabaseAdmin
      .from("content_items")
      .update(updates)
      .eq("id", id)
      .select("*")
      .maybeSingle();

    if (error) return res.status(500).json({ error: error.message || "failed to update" });
    return res.status(200).json({ item: data });
  }

  if (req.method === "DELETE") {
    const { error } = await supabaseAdmin.from("content_items").delete().eq("id", id);
    if (error) return res.status(500).json({ error: error.message || "failed to delete" });
    return res.status(200).json({ ok: true });
  }

  return res.status(405).json({ error: "Method not allowed" });
}
