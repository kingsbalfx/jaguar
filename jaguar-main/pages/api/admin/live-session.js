import { createPagesServerClient } from "@supabase/auth-helpers-nextjs";
import { getSupabaseClient } from "../../../lib/supabaseClient";
import { isSubscriptionActive } from "../../../lib/subscription-status";
import { notifyMentorshipAudience } from "../../../lib/notifications";

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
      const [{ data, error }, { data: users }, { data: subscriptions }] = await Promise.all([
        supabaseAdmin
        .from("live_sessions")
        .select("*")
        .eq("active", true)
        .order("starts_at", { ascending: true })
        .limit(1)
        .maybeSingle(),
        supabaseAdmin.from("profiles").select("id,email,role,name,username").order("email"),
        supabaseAdmin.from("subscriptions").select("email,plan,status,ended_at,started_at").order("started_at", { ascending: false }),
      ]);

      if (error && error.code !== "42P01") {
        return res.status(500).json({ error: "failed to load live session" });
      }
      const activeByEmail = new Map();
      for (const subscription of subscriptions || []) {
        const email = String(subscription.email || "").toLowerCase();
        if (isSubscriptionActive(subscription) && !activeByEmail.has(email)) {
          activeByEmail.set(email, subscription.plan);
        }
      }
      const segmentedUsers = (users || []).map((user) => {
        const email = String(user.email || "").toLowerCase();
        const profilePlan = String(user.role || "user").toLowerCase();
        const activePlan = activeByEmail.get(email) || (profilePlan === "user" ? "free" : profilePlan);
        return {
          ...user,
          activePlan,
          accessStatus: activeByEmail.has(email) || profilePlan === "lifetime" ? "active" : "profile role",
        };
      });
      return res.status(200).json({ session: data || null, users: segmentedUsers });
    }

    const {
      title,
      sessionId,
      startsAt,
      endsAt,
      timezone,
      status,
      mediaType,
      mediaUrl,
      roomName,
      segment,
      audioOnly,
      roomMode,
      targetUserIds,
    } = req.body || {};
    const starts_at = parseIso(startsAt);
    const ends_at = parseIso(endsAt);

    if (!title || !starts_at) {
      return res.status(400).json({ error: "title and startsAt are required" });
    }
    if (roomMode === "one_to_one" && (!Array.isArray(targetUserIds) || targetUserIds.length !== 1)) {
      return res.status(400).json({ error: "one-to-one rooms require exactly one selected subscriber" });
    }

    let deactivateQuery = supabaseAdmin.from("live_sessions").update({ active: false }).eq("active", true);
    if (sessionId) deactivateQuery = deactivateQuery.neq("id", sessionId);
    await deactivateQuery;

    let inserted = null;
    let insertError = null;

    const payload = {
        title: String(title).trim(),
        starts_at,
        ends_at,
        timezone: timezone || "Africa/Lagos",
        status: status || "scheduled",
        media_type: "webrtc",
        media_url: mediaUrl || null,
        room_name: roomName || "global-room",
        segment: segment || "all",
        audio_only: Boolean(audioOnly),
        room_mode: roomMode === "one_to_one" ? "one_to_one" : "group",
        target_user_ids: Array.isArray(targetUserIds) ? targetUserIds : [],
        active: status !== "completed",
        updated_at: new Date().toISOString(),
      };
    const writeQuery = sessionId
      ? supabaseAdmin.from("live_sessions").update(payload).eq("id", sessionId)
      : supabaseAdmin.from("live_sessions").insert(payload);
    const fullInsert = await writeQuery
      .select("*")
      .maybeSingle();

    inserted = fullInsert.data || null;
    insertError = fullInsert.error || null;

    if (insertError) {
      return res.status(500).json({ error: "failed to save live session; run the WebRTC mentorship SQL migration", details: insertError.message });
    }

    let notificationResult = { emailed: 0, notified: 0 };
    if (inserted?.active) {
      notificationResult = await notifyMentorshipAudience({
        supabaseAdmin,
        session: inserted,
        phase: inserted.status === "live" ? "live" : "scheduled",
      });
    }

    return res.status(200).json({ session: inserted, notifications: notificationResult });
  } catch (e) {
    console.error(e);
    return res.status(500).json({ error: e.message || String(e) });
  }
}
