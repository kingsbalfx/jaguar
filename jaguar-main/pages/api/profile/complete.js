import { createPagesServerClient } from "@supabase/auth-helpers-nextjs";
import { getSupabaseClient } from "../../../lib/supabaseClient";

export default async function handler(req, res) {
  if (req.method !== "POST") {
    return res.status(405).end();
  }

  try {
    const supabase = createPagesServerClient({ req, res });
    const {
      data: { session },
    } = await supabase.auth.getSession();

    if (!session?.user) {
      return res.status(401).json({ error: "not authenticated" });
    }

    const { name, phone } = req.body || {};
    if (!name || !phone) {
      return res.status(400).json({ error: "name and phone are required" });
    }

    const supabaseAdmin = getSupabaseClient({ server: true });
    const { error } = await supabaseAdmin.from("profiles").upsert({
      id: session.user.id,
      email: session.user.email,
      name,
      phone,
      role: "user",
      updated_at: new Date().toISOString(),
    });

    if (error) {
      return res.status(500).json({ error: "failed to save profile" });
    }

    return res.status(200).json({ ok: true });
  } catch (e) {
    console.error(e);
    return res.status(500).json({ error: e.message || String(e) });
  }
}
