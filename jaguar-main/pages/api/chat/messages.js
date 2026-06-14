import { createPagesServerClient } from "@supabase/auth-helpers-nextjs";
import { getSupabaseClient } from "../../../lib/supabaseClient";
import { getPaidAccess, ROLE_RANK } from "../../../lib/subscription-status";

async function context(req, res) {
  const supabase = createPagesServerClient({ req, res });
  const { data: { session } } = await supabase.auth.getSession();
  const admin = getSupabaseClient({ server: true });
  if (!session?.user || !admin) return null;
  const { data: profile } = await admin.from("profiles").select("role,name,username,email").eq("id", session.user.id).maybeSingle();
  return { admin, session, profile: profile || {} };
}

async function allowed(ctx, roomKey) {
  const role = String(ctx.profile.role || "user").toLowerCase();
  if (role === "admin") return true;
  const { data: room } = await ctx.admin.from("live_sessions").select("segment,target_user_ids").eq("room_name", roomKey).eq("active", true).maybeSingle();
  if (!room) return false;
  const targets = Array.isArray(room.target_user_ids) ? room.target_user_ids : [];
  if (targets.includes(ctx.session.user.id)) return true;
  if (targets.length) return false;
  const segment = String(room.segment || "all").toLowerCase();
  if (["all", "free"].includes(segment)) return true;
  const access = await getPaidAccess({ supabaseAdmin: ctx.admin, email: ctx.session.user.email, role });
  return access.active && access.rank >= (ROLE_RANK[segment] ?? 99);
}

export default async function handler(req, res) {
  const ctx = await context(req, res);
  if (!ctx) return res.status(401).json({ error: "not authenticated" });
  const roomKey = String(req.query.roomKey || req.body?.roomKey || "").trim();
  if (!roomKey || !(await allowed(ctx, roomKey))) return res.status(403).json({ error: "You do not have access to this mentorship chat." });

  if (req.method === "GET") {
    const { data, error } = await ctx.admin.from("mentorship_messages").select("*").eq("room_key", roomKey).is("deleted_at", null).order("created_at", { ascending: false }).limit(300);
    return error ? res.status(500).json({ error: error.message }) : res.status(200).json({ messages: (data || []).reverse() });
  }
  if (req.method === "POST") {
    const content = String(req.body?.content || "").trim();
    if (!content || content.length > 10000) return res.status(400).json({ error: "Message must be between 1 and 10,000 characters." });
    const { data, error } = await ctx.admin.from("mentorship_messages").insert({
      room_key: roomKey,
      sender_id: ctx.session.user.id,
      sender_name: ctx.profile.name || ctx.profile.username || ctx.profile.email || ctx.session.user.email,
      content,
      reply_to: req.body?.replyTo || null,
    }).select("*").single();
    return error ? res.status(500).json({ error: error.message }) : res.status(200).json({ message: data });
  }
  if (req.method === "PUT" || req.method === "DELETE") {
    const id = String(req.body?.id || "").trim();
    if (!id) return res.status(400).json({ error: "Message id is required." });
    const content = String(req.body?.content || "").trim();
    if (req.method === "PUT" && (!content || content.length > 10000)) {
      return res.status(400).json({ error: "Message must be between 1 and 10,000 characters." });
    }
    const updates = req.method === "DELETE"
      ? { deleted_at: new Date().toISOString() }
      : { content, edited_at: new Date().toISOString() };
    let query = ctx.admin.from("mentorship_messages").update(updates).eq("id", id).eq("room_key", roomKey);
    if (String(ctx.profile.role || "").toLowerCase() !== "admin") query = query.eq("sender_id", ctx.session.user.id);
    const { data, error } = await query.select("*").maybeSingle();
    if (error) return res.status(500).json({ error: error.message });
    if (!data) return res.status(404).json({ error: "Message not found or cannot be changed." });
    return res.status(200).json({ message: data });
  }
  return res.status(405).json({ error: "Method not allowed" });
}
