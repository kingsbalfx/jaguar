import { createPagesServerClient } from "@supabase/auth-helpers-nextjs";
import { getSupabaseClient } from "../../lib/supabaseClient";

const ROLE_RANK = {
  free: 0,
  user: 0,
  premium: 1,
  vip: 2,
  pro: 3,
  lifetime: 4,
  admin: 99,
  all: 0,
};

function canAccess(role, segment) {
  const r = ROLE_RANK[role] ?? 0;
  const s = ROLE_RANK[segment] ?? 0;
  return r >= s;
}

export default async function handler(req, res) {
  if (req.method !== "GET") {
    return res.status(405).json({ error: "Method not allowed" });
  }

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

  const { data: profile } = await supabaseAdmin
    .from("profiles")
    .select("role")
    .eq("id", session.user.id)
    .maybeSingle();

  const role = (profile?.role || "user").toLowerCase();

  const { data, error } = await supabaseAdmin
    .from("live_sessions")
    .select("*")
    .eq("active", true)
    .order("starts_at", { ascending: true })
    .limit(1)
    .maybeSingle();

  if (error && error.code !== "42P01") {
    return res.status(500).json({ error: "failed to load live session" });
  }

  const sessionData = data || null;
  if (!sessionData) {
    return res.status(200).json({ session: null, role });
  }

  const segment = sessionData.segment || "all";
  if (!canAccess(role, segment)) {
    return res.status(200).json({ session: null, role });
  }

  return res.status(200).json({ session: sessionData, role });
}
