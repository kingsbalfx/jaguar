import { createPagesServerClient } from "@supabase/auth-helpers-nextjs";
import { getSupabaseClient } from "../../../../lib/supabaseClient";

const ALLOWED_BUCKETS = new Set([
  process.env.NEXT_PUBLIC_STORAGE_BUCKET || "public",
  process.env.NEXT_PUBLIC_STORAGE_BUCKET_PREMIUM || "premium",
  process.env.NEXT_PUBLIC_STORAGE_BUCKET_VIP || "vip",
  process.env.NEXT_PUBLIC_STORAGE_BUCKET_PRO || "pro",
  process.env.NEXT_PUBLIC_STORAGE_BUCKET_LIFETIME || "lifetime",
]);

export default async function handler(req, res) {
  if (req.method !== "POST") return res.status(405).json({ error: "Method not allowed" });

  const supabase = createPagesServerClient({ req, res });
  const { data: { session } } = await supabase.auth.getSession();
  if (!session?.user) return res.status(401).json({ error: "not authenticated" });

  const supabaseAdmin = getSupabaseClient({ server: true });
  if (!supabaseAdmin) return res.status(500).json({ error: "Supabase admin client not configured" });

  const { data: profile } = await supabaseAdmin.from("profiles").select("role").eq("id", session.user.id).maybeSingle();
  const adminEmail = String(process.env.NEXT_PUBLIC_ADMIN_EMAIL || process.env.SUPER_ADMIN_EMAIL || "").toLowerCase();
  const isAdmin = String(profile?.role || "").toLowerCase() === "admin" || String(session.user.email || "").toLowerCase() === adminEmail;
  if (!isAdmin) return res.status(403).json({ error: "forbidden" });

  const bucket = String(req.body?.bucket || "");
  const path = String(req.body?.path || "").replace(/^\/+/, "");
  if (!ALLOWED_BUCKETS.has(bucket) || !path) return res.status(400).json({ error: "Valid bucket and path are required." });

  const { data, error } = await supabaseAdmin.storage.from(bucket).createSignedUrl(path, 60 * 60 * 6);
  if (error || !data?.signedUrl) return res.status(404).json({ error: error?.message || "File not found." });
  return res.status(200).json({ playbackUrl: data.signedUrl });
}
