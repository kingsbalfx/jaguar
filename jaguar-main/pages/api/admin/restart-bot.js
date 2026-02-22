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

    if (!session || !session.user) {
      return res.status(401).json({ error: "not authenticated" });
    }

    const supabaseAdmin = getSupabaseClient({ server: true });
    const userId = session.user.id;
    const { data: profile } = await supabaseAdmin
      .from("profiles")
      .select("role")
      .eq("id", userId)
      .maybeSingle();

    const role = (profile?.role || "user").toLowerCase();
    if (role !== "admin") {
      return res.status(403).json({ error: "forbidden" });
    }

    const baseUrl = process.env.BOT_API_URL;
    if (!baseUrl) {
      return res.status(500).json({ error: "BOT_API_URL not configured" });
    }

    const restartUrl = new URL("/restart", baseUrl).toString();
    const response = await fetch(restartUrl, { method: "POST" });
    const text = await response.text();
    let payload = { raw: text };
    try {
      payload = text ? JSON.parse(text) : {};
    } catch (e) {
      // keep raw text
    }

    if (!response.ok) {
      return res.status(502).json({ error: "bot restart failed", detail: payload });
    }

    return res.status(200).json({ ok: true, result: payload });
  } catch (e) {
    console.error(e);
    return res.status(500).json({ error: e.message || String(e) });
  }
}
