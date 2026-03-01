import { createPagesServerClient } from "@supabase/auth-helpers-nextjs";
import { getSupabaseClient } from "../../../lib/supabaseClient";

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

    const { login, password, server } = req.body || {};
    if (!login || !password || !server) {
      return res.status(400).json({ error: "login, password, and server are required" });
    }

    const supabaseAdmin = getSupabaseClient({ server: true });
    if (!supabaseAdmin) {
      return res.status(500).json({ error: "Supabase admin client not configured" });
    }

    const payload = {
      user_id: session.user.id,
      email: session.user.email,
      login: String(login).trim(),
      password: String(password),
      server: String(server).trim(),
      status: "pending",
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };

    const { error } = await supabaseAdmin.from("mt5_submissions").insert(payload);
    if (error) {
      return res.status(500).json({ error: error.message || "failed to submit credentials" });
    }

    return res.status(200).json({ ok: true });
  } catch (err) {
    console.error("mt5 submission error:", err);
    return res.status(500).json({ error: err.message || "server error" });
  }
}
