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
      .from("mt5_submissions")
      .select("id, user_id, email, login, server, status, created_at, updated_at")
      .order("created_at", { ascending: false })
      .limit(25);

    if (error) {
      return res.status(500).json({ error: "failed to load submissions" });
    }

    return res.status(200).json({ submissions: data || [] });
  }

  if (req.method === "POST") {
    const { id } = req.body || {};
    if (!id) {
      return res.status(400).json({ error: "id required" });
    }

    const { data: submission, error: loadErr } = await supabaseAdmin
      .from("mt5_submissions")
      .select("id, login, password, server")
      .eq("id", id)
      .maybeSingle();

    if (loadErr || !submission) {
      return res.status(404).json({ error: "submission not found" });
    }

    await supabaseAdmin.from("mt5_credentials").update({ active: false }).eq("active", true);

    const { error: insertError } = await supabaseAdmin
      .from("mt5_credentials")
      .insert({
        login: submission.login,
        password: submission.password,
        server: submission.server,
        active: true,
        updated_at: new Date().toISOString(),
      });

    if (insertError) {
      return res.status(500).json({ error: "failed to activate credentials" });
    }

    await supabaseAdmin
      .from("mt5_submissions")
      .update({ status: "activated", updated_at: new Date().toISOString() })
      .eq("id", submission.id);

    return res.status(200).json({ ok: true });
  }

  return res.status(405).json({ error: "Method not allowed" });
}
