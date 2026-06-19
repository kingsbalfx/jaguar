import { createPagesServerClient } from "@supabase/auth-helpers-nextjs";
import { getSupabaseClient } from "../../lib/supabaseClient";
import { getPaidAccess, ROLE_RANK } from "../../lib/subscription-status";

export default async function handler(req, res) {
  if (req.method !== "GET") return res.status(405).json({ error: "Method not allowed" });
  const supabase = createPagesServerClient({ req, res });
  const { data: { session } } = await supabase.auth.getSession();
  if (!session?.user) return res.status(401).json({ error: "not authenticated" });

  const supabaseAdmin = getSupabaseClient({ server: true });
  if (!supabaseAdmin) return res.status(500).json({ error: "Supabase admin client not configured" });
  const { data: profile } = await supabaseAdmin.from("profiles").select("role,name,username,email").eq("id", session.user.id).maybeSingle();
  const role = String(profile?.role || "user").toLowerCase();
  const access = await getPaidAccess({ supabaseAdmin, email: session.user.email, role });
  const { data, error } = await supabaseAdmin
    .from("live_sessions").select("*").eq("active", true).order("starts_at", { ascending: true }).limit(25);
  if (error && error.code !== "42P01") return res.status(500).json({ error: "failed to load live session" });
  const displayName = role === "admin" ? "Admin" : profile?.username || profile?.name || "Subscriber";
  if (!data?.length) return res.status(200).json({ session: null, role, displayName, accessStatus: access.status });

  const allowedSession = (data || []).find((item) => {
    const segment = String(item.segment || "all").toLowerCase();
    const targets = Array.isArray(item.target_user_ids) ? item.target_user_ids : [];
    const segmentAllowed = segment === "all" || segment === "free" || (access.active && access.rank >= (ROLE_RANK[segment] ?? 99));
    const targetAllowed = targets.length === 0 || targets.includes(session.user.id);
    return role === "admin" || (segmentAllowed && targetAllowed);
  });
  if (!allowedSession) {
    return res.status(200).json({ session: null, role, displayName, accessStatus: access.status });
  }
  return res.status(200).json({ session: allowedSession, role, displayName, accessStatus: access.status });
}
