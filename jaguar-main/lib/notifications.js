import { emailLayout, sendLifecycleEmail } from "./mailer";
import { parseMentorshipSegments, formatMentorshipSegmentList } from "./mentorship-groups";
import { getPaidAccess, ROLE_RANK } from "./subscription-status";

function escapeHtml(value) {
  return String(value || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function compactText(value, maxLength = 600) {
  const text = String(value || "").replace(/\s+/g, " ").trim();
  return text.length > maxLength ? `${text.slice(0, maxLength - 1)}...` : text;
}

function inlineImageAttachment(imageData) {
  const match = String(imageData || "").match(/^data:image\/(png|jpe?g|webp);base64,(.+)$/i);
  if (!match) return null;
  const extension = match[1].toLowerCase().replace("jpeg", "jpg");
  return {
    filename: `kingsbalfx-live-screenshot.${extension}`,
    content: Buffer.from(match[2], "base64"),
    cid: "kingsbalfx-live-screenshot",
    contentType: `image/${extension === "jpg" ? "jpeg" : extension}`,
  };
}

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

export async function notifyMentorshipRoomUpdate({
  supabaseAdmin,
  session,
  senderId = "",
  senderName = "Admin",
  content = "",
  kind = "chat",
  imageData = "",
}) {
  if (!supabaseAdmin || !session?.id) return { emailed: 0, notified: 0 };
  const users = await getUsersForMentorshipSegments({
    supabaseAdmin,
    segmentValue: session.segment || "all",
    targetUserIds: session.target_user_ids || [],
  });
  const filteredUsers = users.filter((user) => user.id !== senderId);
  const title = session.title || "KINGSBALFX Mentorship Session";
  const roomLabel = notificationAudienceLabel(session.segment);
  const isScreenshot = kind === "screenshot";
  const snippet = compactText(content || (isScreenshot ? "A live screen screenshot was shared from the mentorship room." : "A new live-room message is available."));
  const subject = isScreenshot
    ? `${title}: live screen screenshot shared`
    : `${title}: new message from ${senderName || "Admin"}`;
  const body = isScreenshot
    ? `A KINGSBALFX live screen screenshot was shared for ${roomLabel}. Open your dashboard to view or join the room.`
    : `${senderName || "Admin"} sent a message in ${title}: ${snippet}`;
  const screenshotAttachment = inlineImageAttachment(imageData);
  const imageHtml = screenshotAttachment
    ? `<p style="margin-top:18px"><img src="cid:${screenshotAttachment.cid}" alt="KINGSBALFX live screen screenshot" style="display:block;max-width:100%;border-radius:14px;border:1px solid #dbe4ef" /></p>`
    : "";
  const html = emailLayout(
    isScreenshot ? "Live screen screenshot shared" : "New live room message",
    `<p><strong>${escapeHtml(title)}</strong></p><p>${escapeHtml(body)}</p>${imageHtml}<p style="color:#64748b;font-size:14px">This update was sent because your account is included in ${escapeHtml(roomLabel)}.</p>`,
    "Open Live Room",
    "/dashboard",
  );
  const uniqueStamp = `${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
  let emailed = 0;
  let notified = 0;
  for (const user of filteredUsers) {
    const dedupeKey = `mentorship_${kind}:${session.id}:${uniqueStamp}:${user.id}`;
    const emailResult = await sendLifecycleEmail({
      supabaseAdmin,
      email: user.email,
      type: `mentorship_${kind}`,
      dedupeKey,
      subject,
      text: body,
      html,
      attachments: screenshotAttachment ? [screenshotAttachment] : undefined,
    });
    if (emailResult.sent) emailed += 1;
    await createInAppNotification({
      supabaseAdmin,
      userId: user.id,
      type: `mentorship_${kind}`,
      dedupeKey,
      title: subject,
      body,
      link: "/dashboard",
    });
    notified += 1;
  }
  return { emailed, notified };
}
