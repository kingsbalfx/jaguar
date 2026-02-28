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
  const email = (session.user.email || "").toLowerCase();
  const adminEmail =
    (process.env.SUPER_ADMIN_EMAIL || process.env.NEXT_PUBLIC_ADMIN_EMAIL || process.env.ADMIN_EMAIL || "").toLowerCase();
  const isAdminEmail = adminEmail && email === adminEmail;

  if (role !== "admin" && !isAdminEmail) {
    res.status(403).json({ error: "forbidden" });
    return null;
  }

  if (isAdminEmail && role !== "admin") {
    try {
      await supabaseAdmin.from("profiles").upsert({
        id: session.user.id,
        email: session.user.email,
        role: "admin",
        updated_at: new Date().toISOString(),
      });
    } catch (e) {
      console.warn("Failed to promote admin email:", e?.message || e);
    }
  }

  return { supabaseAdmin };
}

export default async function handler(req, res) {
  const ctx = await requireAdmin(req, res);
  if (!ctx) return;
  const { supabaseAdmin } = ctx;
  const { id } = req.query;

  if (!id) {
    return res.status(400).json({ error: "missing id" });
  }

  if (req.method === "PUT") {
    const { content, segment } = req.body || {};
    if (!content) {
      return res.status(400).json({ error: "content is required" });
    }

    const { data, error } = await supabaseAdmin
      .from("messages")
      .update({
        content,
        segment: segment || "all",
      })
      .eq("id", id)
      .select("*")
      .maybeSingle();

    if (error) {
      return res.status(500).json({ error: error.message || "failed to update message" });
    }

    return res.status(200).json({ item: data });
  }

  if (req.method === "DELETE") {
    const { error } = await supabaseAdmin.from("messages").delete().eq("id", id);
    if (error) {
      return res.status(500).json({ error: error.message || "failed to delete" });
    }
    return res.status(200).json({ ok: true });
  }

  return res.status(405).json({ error: "Method not allowed" });
}
