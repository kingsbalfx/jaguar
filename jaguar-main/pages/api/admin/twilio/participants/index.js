import Twilio from "twilio";
import { createPagesServerClient } from "@supabase/auth-helpers-nextjs";
import { getSupabaseClient } from "../../../../../lib/supabaseClient";

function getTwilioClient() {
  const { TWILIO_ACCOUNT_SID, TWILIO_API_KEY_SID, TWILIO_API_KEY_SECRET } = process.env;
  if (!TWILIO_ACCOUNT_SID || !TWILIO_API_KEY_SID || !TWILIO_API_KEY_SECRET) return null;
  return Twilio(TWILIO_API_KEY_SID, TWILIO_API_KEY_SECRET, { accountSid: TWILIO_ACCOUNT_SID });
}

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

  return true;
}

export default async function handler(req, res) {
  if (req.method !== "GET") {
    return res.status(405).json({ error: "Method not allowed" });
  }

  const ok = await requireAdmin(req, res);
  if (!ok) return;

  const client = getTwilioClient();
  if (!client) {
    return res.status(500).json({ error: "Twilio env vars not configured" });
  }

  const roomName =
    (typeof req.query?.roomName === "string" && req.query.roomName) ||
    (typeof req.query?.room === "string" && req.query.room) ||
    "";
  if (!roomName) {
    return res.status(400).json({ error: "roomName is required" });
  }

  const status = typeof req.query?.status === "string" ? req.query.status : "connected";

  try {
    const participants = await client.video.v1.rooms(roomName).participants.list({ status });
    const output = participants.map((p) => ({
      sid: p.sid,
      identity: p.identity,
      status: p.status,
      muted: p.muted,
      dateCreated: p.dateCreated,
    }));
    return res.status(200).json({ participants: output });
  } catch (err) {
    console.error("Twilio participants list error:", err);
    return res.status(500).json({ error: "Failed to list participants" });
  }
}
