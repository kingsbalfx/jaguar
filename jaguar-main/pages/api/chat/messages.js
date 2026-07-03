import { createPagesServerClient } from "@supabase/auth-helpers-nextjs";
import { getSupabaseClient } from "../../../lib/supabaseClient";
import { getPaidAccess, ROLE_RANK } from "../../../lib/subscription-status";
import { parseMentorshipSegments } from "../../../lib/mentorship-groups";
import { notifyMentorshipRoomUpdate } from "../../../lib/notifications";

export const config = {
  api: {
    bodyParser: {
      sizeLimit: "8mb",
    },
  },
};

const CHAT_ATTACHMENT_BUCKET = process.env.CHAT_ATTACHMENT_BUCKET || "chat-attachments";
const MAX_CHAT_IMAGE_BYTES = 6 * 1024 * 1024;

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
  const segments = parseMentorshipSegments(room.segment || "all");
  if (segments.includes("all") || segments.includes("free")) return true;
  const access = await getPaidAccess({ supabaseAdmin: ctx.admin, email: ctx.session.user.email, role });
  return segments.some((segment) => access.active && access.rank >= (ROLE_RANK[segment] ?? 99));
}

function parseChatImage({ imageData, imageName }) {
  if (!imageData) return null;
  const match = String(imageData).match(/^data:image\/(png|jpe?g|webp);base64,([A-Za-z0-9+/=\s]+)$/i);
  if (!match) {
    const error = new Error("Only PNG, JPG, JPEG, or WEBP chart images can be sent in live chat.");
    error.status = 400;
    throw error;
  }
  const extension = match[1].toLowerCase().replace("jpeg", "jpg");
  const buffer = Buffer.from(match[2].replace(/\s/g, ""), "base64");
  if (!buffer.length || buffer.length > MAX_CHAT_IMAGE_BYTES) {
    const error = new Error("Chart image must be smaller than 6MB.");
    error.status = 400;
    throw error;
  }
  return {
    buffer,
    extension,
    contentType: `image/${extension === "jpg" ? "jpeg" : extension}`,
    name: String(imageName || `kingsbalfx-chart.${extension}`).slice(0, 160),
  };
}

async function signAttachments(admin, messages) {
  return Promise.all((messages || []).map(async (message) => {
    if (!message.attachment_bucket || !message.attachment_path) return message;
    const { data } = await admin.storage
      .from(message.attachment_bucket)
      .createSignedUrl(message.attachment_path, 60 * 60);
    return {
      ...message,
      attachment_url: data?.signedUrl || null,
    };
  }));
}

async function uploadChatImage(admin, roomKey, parsedImage) {
  if (!parsedImage) return null;
  const safeRoom = roomKey.replace(/[^a-z0-9_-]/gi, "_").slice(0, 80) || "room";
  const fileName = `${Date.now()}-${Math.random().toString(36).slice(2, 10)}.${parsedImage.extension}`;
  const path = `${safeRoom}/${fileName}`;
  const { error } = await admin.storage
    .from(CHAT_ATTACHMENT_BUCKET)
    .upload(path, parsedImage.buffer, {
      contentType: parsedImage.contentType,
      upsert: false,
    });
  if (error) {
    const next = new Error(`Unable to save chart image. Make sure the ${CHAT_ATTACHMENT_BUCKET} storage bucket exists.`);
    next.status = 500;
    throw next;
  }
  return {
    attachment_type: "image",
    attachment_bucket: CHAT_ATTACHMENT_BUCKET,
    attachment_path: path,
    attachment_name: parsedImage.name,
    attachment_size: parsedImage.buffer.length,
    attachment_metadata: {
      contentType: parsedImage.contentType,
      source: "live-chat",
    },
  };
}

export default async function handler(req, res) {
  const ctx = await context(req, res);
  if (!ctx) return res.status(401).json({ error: "not authenticated" });
  const roomKey = String(req.query.roomKey || req.body?.roomKey || "").trim();
  if (!roomKey || !(await allowed(ctx, roomKey))) return res.status(403).json({ error: "You do not have access to this mentorship chat." });

  if (req.method === "GET") {
    const { data, error } = await ctx.admin.from("mentorship_messages").select("*").eq("room_key", roomKey).is("deleted_at", null).order("created_at", { ascending: false }).limit(300);
    if (error) return res.status(500).json({ error: error.message });
    const messages = await signAttachments(ctx.admin, (data || []).reverse());
    return res.status(200).json({ messages });
  }
  if (req.method === "POST") {
    const content = String(req.body?.content || "").trim();
    if (content.length > 10000) return res.status(400).json({ error: "Message must be 10,000 characters or less." });
    let parsedImage = null;
    try {
      parsedImage = parseChatImage({ imageData: req.body?.imageData, imageName: req.body?.imageName });
    } catch (error) {
      return res.status(error.status || 400).json({ error: error.message });
    }
    if (!content && !parsedImage) return res.status(400).json({ error: "Type a message or attach a chart image." });
    const senderIsAdmin = String(ctx.profile.role || "").toLowerCase() === "admin";
    const senderName = senderIsAdmin ? "Admin" : ctx.profile.username || ctx.profile.name || "Subscriber";
    let attachment = null;
    try {
      attachment = await uploadChatImage(ctx.admin, roomKey, parsedImage);
    } catch (error) {
      return res.status(error.status || 500).json({ error: error.message });
    }
    const { data, error } = await ctx.admin.from("mentorship_messages").insert({
      room_key: roomKey,
      sender_id: ctx.session.user.id,
      sender_name: senderName,
      content,
      reply_to: req.body?.replyTo || null,
      ...(attachment || {}),
    }).select("*").single();
    if (error) {
      if (attachment?.attachment_path) {
        await ctx.admin.storage.from(attachment.attachment_bucket).remove([attachment.attachment_path]);
      }
      const missingAttachmentColumns = ["attachment_type", "attachment_bucket", "attachment_path"].some((column) => String(error.message || "").includes(column));
      if (missingAttachmentColumns || error.code === "42703") {
        return res.status(500).json({ error: "Chat image columns are missing. Run sql/2026-07-03_chat_image_attachments.sql in Supabase, then try again." });
      }
      return res.status(500).json({ error: error.message });
    }
    const [message] = await signAttachments(ctx.admin, [data]);
    let notifications = { emailed: 0, notified: 0 };
    if (senderIsAdmin) {
      const { data: liveSession } = await ctx.admin
        .from("live_sessions")
        .select("*")
        .eq("room_name", roomKey)
        .eq("active", true)
        .maybeSingle();
      if (liveSession) {
        notifications = await notifyMentorshipRoomUpdate({
          supabaseAdmin: ctx.admin,
          session: liveSession,
          senderId: ctx.session.user.id,
          senderName,
          content: content || "A KINGSBALFX chart image was shared in the live chat.",
          kind: "chat",
          imageData: parsedImage ? req.body.imageData : "",
        });
      }
    }
    return res.status(200).json({ message, notifications });
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
