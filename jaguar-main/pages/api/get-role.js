import { getSupabaseClient } from "../../lib/supabaseClient";

export default async function handler(req, res) {
  if (req.method !== "POST") {
    return res.status(405).json({ error: "Method not allowed" });
  }
  const { userId, userEmail } = req.body || {};
  if (!userId) return res.status(400).json({ error: "Missing userId" });

  const supabase = getSupabaseClient({ server: true });
  if (!supabase) {
    return res.status(500).json({ error: "Supabase not configured on server" });
  }

  try {
    const { data, error } = await supabase
      .from("profiles")
      .select("role")
      .eq("id", userId)
      .maybeSingle();

    if (error) {
      console.error("get-role supabase error:", error);
      return res.status(500).json({ error: error.message });
    }

    const adminEmail =
      (process.env.SUPER_ADMIN_EMAIL || process.env.NEXT_PUBLIC_ADMIN_EMAIL || process.env.ADMIN_EMAIL || "").toLowerCase();
    const isAdminEmail = adminEmail && String(userEmail || "").toLowerCase() === adminEmail;
    const role = isAdminEmail ? "admin" : data?.role ?? null;
    return res.status(200).json({ role });
  } catch (err) {
    console.error("get-role server error:", err);
    return res.status(500).json({ error: "Unexpected server error" });
  }
}
