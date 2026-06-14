import { createPagesServerClient } from "@supabase/auth-helpers-nextjs";
import { getSupabaseClient } from "../../../../lib/supabaseClient";

const ALLOWED_BUCKETS = new Set([
  process.env.NEXT_PUBLIC_STORAGE_BUCKET || "public",
  process.env.NEXT_PUBLIC_STORAGE_BUCKET_PREMIUM || "premium",
  process.env.NEXT_PUBLIC_STORAGE_BUCKET_VIP || "vip",
  process.env.NEXT_PUBLIC_STORAGE_BUCKET_PRO || "pro",
  process.env.NEXT_PUBLIC_STORAGE_BUCKET_LIFETIME || "lifetime",
]);

function sanitizeFileName(fileName = "") {
  return String(fileName)
    .replace(/\s+/g, "_")
    .replace(/[^a-zA-Z0-9._-]/g, "")
    .slice(-140);
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
  const adminEmail = (process.env.NEXT_PUBLIC_ADMIN_EMAIL || process.env.SUPER_ADMIN_EMAIL || "").toLowerCase();
  const userEmail = (session.user.email || "").toLowerCase();
  const isAdminEmail = adminEmail && userEmail === adminEmail;

  if (isAdminEmail && role !== "admin") {
    try {
      await supabaseAdmin.from("profiles").update({ role: "admin" }).eq("id", session.user.id);
    } catch {
      // allow override even if profile update fails
    }
  }

  if (role !== "admin" && !isAdminEmail) {
    res.status(403).json({ error: "forbidden" });
    return null;
  }

  return { supabaseAdmin };
}

export default async function handler(req, res) {
  if (req.method !== "POST") {
    return res.status(405).json({ error: "Method not allowed" });
  }

  const ctx = await requireAdmin(req, res);
  if (!ctx) return;

  const { supabaseAdmin } = ctx;
  const { bucket, segment, fileName } = req.body || {};

  if (!bucket || !ALLOWED_BUCKETS.has(bucket)) {
    return res.status(400).json({ error: "invalid bucket" });
  }
  if (!fileName) {
    return res.status(400).json({ error: "fileName is required" });
  }

  const safeFileName = sanitizeFileName(fileName);
  if (!safeFileName) {
    return res.status(400).json({ error: "invalid fileName" });
  }

  const seg = String(segment || "all").replace(/[^a-zA-Z0-9_-]/g, "");
  const path = `content/${seg}/${Date.now()}_${safeFileName}`;

  const { data, error } = await supabaseAdmin.storage.from(bucket).createSignedUploadUrl(path);
  if (error) {
    return res.status(500).json({ error: error.message || "failed to create upload url" });
  }

  const publicUrl = supabaseAdmin.storage.from(bucket).getPublicUrl(path).data.publicUrl;
  const playbackUrl = supabaseAdmin.storage.from(bucket).createSignedUrl(path, 60 * 60 * 6);
  const { data: playback } = await playbackUrl;

  return res.status(200).json({
    bucket,
    path,
    token: data?.token,
    signedUrl: data?.signedUrl,
    publicUrl,
    playbackUrl: playback?.signedUrl || null,
  });
}
