import { createServerSupabaseClient } from "@supabase/auth-helpers-nextjs";
import { getSupabaseClient } from "../../../lib/supabaseClient";

export default async function handler(req, res) {
  if (req.method !== "POST") return res.status(405).end();

  try {
    const supabase = createServerSupabaseClient({ req, res });
    const {
      data: { session },
    } = await supabase.auth.getSession();

    if (!session || !session.user) return res.status(401).json({ error: "not authenticated" });

    const supabaseAdmin = getSupabaseClient({ server: true });
    const userId = session.user.id;
    const { data: profile } = await supabaseAdmin.from("profiles").select("role").eq("id", userId).maybeSingle();
    const role = (profile?.role || "user").toLowerCase();
    if (role !== "admin") return res.status(403).json({ error: "forbidden" });

    const { email, set } = req.body || {};
    if (!email) return res.status(400).json({ error: "email required" });

    // Update profiles.lifetime if column exists, and upsert subscriptions
    try {
      await supabaseAdmin.from("profiles").update({ lifetime: set }).eq("email", email);
    } catch (e) {
      console.warn("Could not update profiles.lifetime:", e.message || e);
    }

    try {
      if (set) {
        await supabaseAdmin.from("subscriptions").upsert({ email, plan: "lifetime", status: "active" }, { onConflict: ["email", "plan"] });
      } else {
        await supabaseAdmin.from("subscriptions").update({ status: "revoked" }).eq("email", email).eq("plan", "lifetime");
      }
    } catch (e) {
      console.warn("Could not upsert subscriptions:", e.message || e);
    }

    return res.status(200).json({ ok: true });
  } catch (e) {
    console.error(e);
    return res.status(500).json({ error: e.message || String(e) });
  }
}
