import { createPagesServerClient } from "@supabase/auth-helpers-nextjs";
import { getSupabaseClient } from "../../../lib/supabaseClient";

function parseIso(value) {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  return date.toISOString();
}

export default async function handler(req, res) {
  if (req.method !== "GET" && req.method !== "POST") {
    return res.status(405).json({ error: "Method not allowed" });
  }

  try {
    const supabase = createPagesServerClient({ req, res });
    const {
      data: { session },
    } = await supabase.auth.getSession();

    if (!session?.user) {
      return res.status(401).json({ error: "not authenticated" });
    }

    const supabaseAdmin = getSupabaseClient({ server: true });
    if (!supabaseAdmin) {
      return res.status(500).json({ error: "Supabase admin client not configured" });
    }

    const userId = session.user.id;
    const { data: profile } = await supabaseAdmin
      .from("profiles")
      .select("role")
      .eq("id", userId)
      .maybeSingle();

    const role = (profile?.role || "user").toLowerCase();
    if (role !== "admin") {
      return res.status(403).json({ error: "forbidden" });
    }

    if (req.method === "GET") {
      const { data, error } = await supabaseAdmin
        .from("live_sessions")
        .select("id, title, starts_at, ends_at, timezone, status, active, updated_at")
        .eq("active", true)
        .order("starts_at", { ascending: true })
        .limit(1)
        .maybeSingle();

      if (error && error.code !== "42P01") {
        return res.status(500).json({ error: "failed to load live session" });
      }
      return res.status(200).json({ session: data || null });
    }

    const { title, startsAt, endsAt, timezone, status } = req.body || {};
    const starts_at = parseIso(startsAt);
    const ends_at = parseIso(endsAt);

    if (!title || !starts_at) {
      return res.status(400).json({ error: "title and startsAt are required" });
    }

    await supabaseAdmin.from("live_sessions").update({ active: false }).eq("active", true);

    const { data: inserted, error: insertError } = await supabaseAdmin
      .from("live_sessions")
      .insert({
        title: String(title).trim(),
        starts_at,
        ends_at,
        timezone: timezone || "Africa/Lagos",
        status: status || "scheduled",
        active: true,
        updated_at: new Date().toISOString(),
      })
      .select("id, title, starts_at, ends_at, timezone, status, active, updated_at")
      .maybeSingle();

    if (insertError) {
      return res.status(500).json({ error: "failed to save live session" });
    }

    return res.status(200).json({ session: inserted });
  } catch (e) {
    console.error(e);
    return res.status(500).json({ error: e.message || String(e) });
  }
}
