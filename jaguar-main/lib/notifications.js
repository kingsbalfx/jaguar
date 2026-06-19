import { emailLayout, sendLifecycleEmail } from "./mailer";
import { parseMentorshipSegments, formatMentorshipSegmentList } from "./mentorship-groups";
import { getPaidAccess, ROLE_RANK } from "./subscription-status";

export function notificationAudienceLabel(segmentValue) {
  return formatMentorshipSegmentList(segmentValue || "all");
}

async function userCanAccessSegment({ supabaseAdmin, user, segments }) {
  const role = String(user.role || "user").toLowerCase();
  if (role === "admin") return true;
  if (segments.includes("all") || segments.includes("free")) return true;
  const access = await getPaidAccess({ supabaseAdmin, email: user.email, role });
  return segments.some((segment) => access.active && access.rank >= (ROLE_RANK[segment] ?? 99));
}

export async function getUsersForMentorshipSegments({ supabaseAdmin, segmentValue, targetUserIds = [] }) {
  if (!supabaseAdmin) return [];
  const segments = parseMentorshipSegments(segmentValue || "all");
  let query = supabaseAdmin.from("profiles").select("id,email,name,username,role");
  if (Array.isArray(targetUserIds) && targetUserIds.length) query = query.in("id", targetUserIds);
  const { data, error } = await query;
  if (error) {
    console.error("notification audience load failed:", error.message);
    return [];
  }
  const users = [];
  for (const user of data || []) {
    if (!user.email) continue;
    if (Array.isArray(targetUserIds) && targetUserIds.length) {
      users.push(user);
      continue;
    }
    if (await userCanAccessSegment({ supabaseAdmin, user, segments })) users.push(user);
  }
  return users;
}

export async function createInAppNotification({ supabaseAdmin, userId, title, body, link, type, dedupeKey }) {
  if (!supabaseAdmin || !userId) return;
  const payload = {
    user_id: userId,
    title,
    body,
    link: link || null,
    notification_type: type || "general",
    dedupe_key: dedupeKey || null,
    read_at: null,
    created_at: new Date().toISOString(),
  };
  const insert = await supabaseAdmin.from("user_notifications").insert(payload);
  if (insert.error && insert.error.code !== "23505") {
    console.warn("in-app notification failed:", insert.error.message);
  }
}

export async function notifyMentorshipAudience({ supabaseAdmin, session, phase = "scheduled" }) {
  if (!supabaseAdmin || !session?.id) return { emailed: 0, notified: 0 };
  const users = await getUsersForMentorshipSegments({
    supabaseAdmin,
    segmentValue: session.segment || "all",
    targetUserIds: session.target_user_ids || [],
  });
  const title = session.title || "KINGSBALFX Mentorship Session";
  const starts = session.starts_at ? new Date(session.starts_at).toLocaleString("en-NG") : "soon";
  const audience = notificationAudienceLabel(session.segment);
  const isLive = phase === "live";
  const subject = isLive ? `${title} is live now` : `${title} has been scheduled`;
  const body = isLive
    ? `${title} is live now for ${audience}. Join your dashboard to enter the room.`
    : `${title} has been scheduled for ${starts}. You are receiving this because your account is included in ${audience}.`;
  const html = emailLayout(
    isLive ? "Your mentorship room is live" : "Mentorship session scheduled",
    `<p><strong>${title}</strong></p><p>${body}</p><p>Please arrive early, keep your notebook ready, and protect your account credentials. Educational content is provided under KINGSBALFX Academy terms and should not be redistributed.</p>`,
    isLive ? "Join Live Room" : "Open Dashboard",
    "/dashboard",
  );
  let emailed = 0;
  let notified = 0;
  for (const user of users) {
    const dedupeKey = `mentorship_${phase}:${session.id}:${user.id}`;
    const emailResult = await sendLifecycleEmail({
      supabaseAdmin,
      email: user.email,
      type: `mentorship_${phase}`,
      dedupeKey,
      subject,
      text: body,
      html,
    });
    if (emailResult.sent) emailed += 1;
    await createInAppNotification({
      supabaseAdmin,
      userId: user.id,
      type: `mentorship_${phase}`,
      dedupeKey,
      title: subject,
      body,
      link: "/dashboard",
    });
    notified += 1;
  }
  return { emailed, notified };
}
