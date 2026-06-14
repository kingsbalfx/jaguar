import { createPagesServerClient } from "@supabase/auth-helpers-nextjs";
import { getSupabaseClient } from "../../../lib/supabaseClient";
import { getPaidAccess, ROLE_RANK } from "../../../lib/subscription-status";
import { addContentMediaUrls } from "../../../lib/content-storage";

export default async function handler(req, res) {
  if (req.method !== "GET") return res.status(405).json({ error: "Method not allowed" });
  const supabase = createPagesServerClient({ req, res });
  const { data: { session } } = await supabase.auth.getSession();
  if (!session?.user) return res.status(401).json({ error: "not authenticated" });

  const supabaseAdmin = getSupabaseClient({ server: true });
  if (!supabaseAdmin) return res.status(500).json({ error: "Supabase admin client not configured" });
  const { data: profile } = await supabaseAdmin.from("profiles").select("role").eq("id", session.user.id).maybeSingle();
  const role = String(profile?.role || "user").toLowerCase();
  const access = await getPaidAccess({ supabaseAdmin, email: session.user.email, role });
  const profileRank = ROLE_RANK[role] || 0;
  const effectiveRank = Math.max(profileRank, access.active ? access.rank : 0);
  const { data, error } = await supabaseAdmin
    .from("content_items").select("*").eq("is_published", true).order("created_at", { ascending: false });
  if (error) return res.status(500).json({ error: "failed to load content" });

  const allowedItems = (data || []).filter((item) => {
    const segment = String(item.segment || "all").toLowerCase();
    return segment === "all" || segment === "free" || effectiveRank >= (ROLE_RANK[segment] ?? 99);
  });
  const items = await Promise.all(allowedItems.map((item) => addContentMediaUrls(supabaseAdmin, item)));
  return res.status(200).json({ items, role, accessStatus: access.status, effectiveRank });
}
