import { createPagesServerClient } from "@supabase/auth-helpers-nextjs";
import { getSupabaseClient } from "../../lib/supabaseClient";
import { getPaidAccess, ROLE_RANK } from "../../lib/subscription-status";
import { parseMentorshipSegments } from "../../lib/mentorship-groups";

async function fetchMessagesWithFallback(client) {
  let { data, error } = await client
    .from("messages")
    .select("*")
    .order("created_at", { ascending: false })
    .limit(20);

  if (error && error.code === "42703") {
    ({ data, error } = await client
      .from("messages")
      .select("*")
      .order("id", { ascending: false })
      .limit(20));
  }

  return { data, error };
}

export default async function handler(req, res) {
  if (req.method !== "GET") return res.status(405).json({ error: "Method not allowed" });
  const supabaseAdmin = getSupabaseClient({ server: true });
  if (!supabaseAdmin) return res.status(500).json({ error: "Supabase admin client not configured" });

  const authClient = createPagesServerClient({ req, res });
  const { data: { session } } = await authClient.auth.getSession();

  const [{ data: messages, error: messageError }, liveResult] = await Promise.all([
    fetchMessagesWithFallback(supabaseAdmin),
    supabaseAdmin
      .from("live_sessions")
      .select("*")
      .eq("active", true)
      .order("starts_at", { ascending: true })
      .limit(25),
  ]);

  if (messageError) return res.status(500).json({ error: "failed to load landing messages" });
  if (liveResult.error && liveResult.error.code !== "42P01") {
    return res.status(500).json({ error: "failed to load live session" });
  }

  let role = "user";
  let canViewLive = false;
  let displayName = "Subscriber";
  let liveSession = null;

  if (session?.user) {
    const { data: profile } = await supabaseAdmin
      .from("profiles")
      .select("role,name,username,email")
      .eq("id", session.user.id)
      .maybeSingle();
    role = String(profile?.role || "user").toLowerCase();
    displayName = role === "admin" ? "Admin" : profile?.username || profile?.name || "Subscriber";
    const access = await getPaidAccess({ supabaseAdmin, email: session.user.email, role });
    liveSession = (liveResult.data || []).find((item) => {
      const segments = parseMentorshipSegments(item.segment || "all");
      const targets = Array.isArray(item.target_user_ids) ? item.target_user_ids : [];
      const segmentAllowed = segments.includes("all") ||
        segments.includes("free") ||
        segments.some((segment) => access.active && access.rank >= (ROLE_RANK[segment] ?? 99));
      const targetAllowed = targets.length === 0 || targets.includes(session.user.id);
      return role === "admin" || (segmentAllowed && targetAllowed);
    }) || null;
    canViewLive = Boolean(liveSession);
  }

  res.setHeader("Cache-Control", "no-store");
  return res.status(200).json({
    messages: messages || [],
    liveSession,
    canViewLive,
    isAuthenticated: Boolean(session?.user),
    role,
    displayName,
  });
}
