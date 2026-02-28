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

  return { supabaseAdmin, session };
}

export default async function handler(req, res) {
  const ctx = await requireAdmin(req, res);
  if (!ctx) return;
  const { supabaseAdmin, session } = ctx;

  if (req.method === "GET") {
    try {
      let { data, error } = await supabaseAdmin
        .from("messages")
        .select("id, content, segment, created_at, created_by")
        .order("created_at", { ascending: false })
        .limit(50);

      if (error && error.code === "42703") {
        ({ data, error } = await supabaseAdmin
          .from("messages")
          .select("id, content, created_at")
          .order("created_at", { ascending: false })
          .limit(50));
      }

      if (error && error.code === "42703") {
        ({ data, error } = await supabaseAdmin
          .from("messages")
          .select("id, content")
          .order("id", { ascending: false })
          .limit(50));
      }

      if (error) {
        return res.status(500).json({ error: "failed to load messages" });
      }

      const items = data || [];
      const authorIds = Array.from(new Set(items.map((item) => item.created_by).filter(Boolean)));
      let authorsById = {};

      if (authorIds.length > 0) {
        const { data: authors, error: authorErr } = await supabaseAdmin
          .from("profiles")
          .select("id, name, username, email")
          .in("id", authorIds);
        if (!authorErr && Array.isArray(authors)) {
          authorsById = authors.reduce((acc, author) => {
            acc[author.id] = author;
            return acc;
          }, {});
        }
      }

      const enriched = items.map((item) => ({
        ...item,
        author: item.created_by ? authorsById[item.created_by] || null : null,
      }));

      return res.status(200).json({ items: enriched });
    } catch (err) {
      return res.status(500).json({ error: err.message || "server error" });
    }
  }

  if (req.method === "POST") {
    const { content, segment } = req.body || {};
    if (!content) {
      return res.status(400).json({ error: "content is required" });
    }

    const payload = {
      content,
      segment: segment || "all",
      created_at: new Date().toISOString(),
      created_by: session?.user?.id || null,
    };

    let { data, error } = await supabaseAdmin
      .from("messages")
      .insert(payload)
      .select("*")
      .maybeSingle();

    if (error && error.code === "42703") {
      const fallbackPayload = {
        content,
        created_at: new Date().toISOString(),
      };
      ({ data, error } = await supabaseAdmin
        .from("messages")
        .insert(fallbackPayload)
        .select("*")
        .maybeSingle());
    }

    if (error) {
      return res.status(500).json({ error: error.message || "failed to save message" });
    }

    return res.status(200).json({ item: data });
  }

  return res.status(405).json({ error: "Method not allowed" });
}
