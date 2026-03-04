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
    const { data: profiles, error } = await supabaseAdmin
      .from("profiles")
      .select("id,email,name,username,role,lifetime,bot_tier,created_at");
    if (error) return res.status(500).json({ error: "failed to load users" });

    const { data: subs } = await supabaseAdmin
      .from("subscriptions")
      .select("email,plan,status,started_at,ended_at");

    const byEmail = new Map();
    (subs || []).forEach((sub) => {
      const current = byEmail.get(sub.email);
      if (!current) {
        byEmail.set(sub.email, sub);
        return;
      }
      if ((sub.started_at || "") > (current.started_at || "")) {
        byEmail.set(sub.email, sub);
      }
    });

    const users = (profiles || []).map((profile) => {
      const sub = byEmail.get(profile.email);
      return {
        ...profile,
        plan: sub?.plan || profile.role || "user",
        planStatus: sub?.status || "none",
        startedAt: sub?.started_at || null,
        endedAt: sub?.ended_at || null,
      };
    });

    return res.status(200).json({ users });
  }

  if (req.method === "PUT") {
    const { id, role, lifetime, botTier } = req.body || {};
    if (!id) return res.status(400).json({ error: "user id required" });

    const updates = {};
    if (role) updates.role = role;
    if (typeof lifetime === "boolean") updates.lifetime = lifetime;
    if (botTier) updates.bot_tier = botTier;

    const { data, error } = await supabaseAdmin
      .from("profiles")
      .update(updates)
      .eq("id", id)
      .select("id,email,name,username,role,lifetime,bot_tier")
      .maybeSingle();

    if (error) return res.status(500).json({ error: error.message || "failed to update user" });
    return res.status(200).json({ user: data });
  }

  return res.status(405).json({ error: "Method not allowed" });
}
