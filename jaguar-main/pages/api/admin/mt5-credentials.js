import { createServerSupabaseClient } from "@supabase/auth-helpers-nextjs";
import { getSupabaseClient } from "../../../lib/supabaseClient";

export default async function handler(req, res) {
  if (req.method !== "GET" && req.method !== "POST") {
    return res.status(405).end();
  }

  try {
    const supabase = createServerSupabaseClient({ req, res });
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

    if (req.method === "GET") {
      const { data, error } = await supabaseAdmin
        .from("mt5_credentials")
        .select("login, server, updated_at")
        .eq("active", true)
        .order("updated_at", { ascending: false })
        .limit(1);

      if (error) {
        return res.status(500).json({ error: "failed to load credentials" });
      }

      const row = Array.isArray(data) ? data[0] : null;
      return res.status(200).json({
        credentials: row
          ? {
              login: row.login || "",
              server: row.server || "",
              updated_at: row.updated_at || null,
              hasPassword: true,
            }
          : {
              login: "",
              server: "",
              updated_at: null,
              hasPassword: false,
            },
      });
    }

    const { login, password, server } = req.body || {};
    if (!login || !password || !server) {
      return res.status(400).json({ error: "login, password, and server are required" });
    }

    await supabaseAdmin.from("mt5_credentials").update({ active: false }).eq("active", true);

    const { error: insertError } = await supabaseAdmin
      .from("mt5_credentials")
      .insert({
        login: String(login).trim(),
        password: String(password),
        server: String(server).trim(),
        active: true,
        updated_at: new Date().toISOString(),
      });

    if (insertError) {
      return res.status(500).json({ error: "failed to save credentials" });
    }

    return res.status(200).json({ ok: true });
  } catch (e) {
    console.error(e);
    return res.status(500).json({ error: e.message || String(e) });
  }
}
