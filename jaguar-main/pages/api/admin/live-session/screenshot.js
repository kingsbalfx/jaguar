import { createPagesServerClient } from "@supabase/auth-helpers-nextjs";
import { getSupabaseClient } from "../../../../lib/supabaseClient";
import { notifyMentorshipRoomUpdate } from "../../../../lib/notifications";

export const config = {
  api: {
    bodyParser: {
      sizeLimit: "7mb",
    },
  },
};

export default async function handler(req, res) {
  if (req.method !== "POST") {
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

    const { data: profile } = await supabaseAdmin
      .from("profiles")
      .select("role")
      .eq("id", session.user.id)
      .maybeSingle();

    if (String(profile?.role || "user").toLowerCase() !== "admin") {
      return res.status(403).json({ error: "forbidden" });
    }

    const roomName = String(req.body?.roomName || "").trim();
    const imageData = String(req.body?.imageData || "").trim();
    const note = String(req.body?.note || "").trim();
    if (!roomName) return res.status(400).json({ error: "roomName is required" });
    if (!/^data:image\/(png|jpe?g|webp);base64,/i.test(imageData)) {
      return res.status(400).json({ error: "A valid screen screenshot is required" });
    }
    if (imageData.length > 6_500_000) {
      return res.status(413).json({ error: "Screenshot is too large. Try again after reducing screen resolution or zoom." });
    }

    const { data: liveSession, error } = await supabaseAdmin
      .from("live_sessions")
      .select("*")
      .eq("room_name", roomName)
      .eq("active", true)
      .maybeSingle();

    if (error) return res.status(500).json({ error: error.message });
    if (!liveSession) return res.status(404).json({ error: "Active live room not found" });

    const notifications = await notifyMentorshipRoomUpdate({
      supabaseAdmin,
      session: liveSession,
      senderId: session.user.id,
      senderName: "Admin",
      content: note || `Admin shared a screen screenshot from ${liveSession.title || roomName}.`,
      kind: "screenshot",
      imageData,
    });

    return res.status(200).json({ notifications });
  } catch (error) {
    console.error("live screen screenshot notification failed:", error);
    return res.status(500).json({ error: error.message || "Unable to send screen screenshot" });
  }
}
