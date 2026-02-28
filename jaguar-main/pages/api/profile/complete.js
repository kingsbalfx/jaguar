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

    const { name, phone, username, address, country, ageConfirmed } = req.body || {};
    if (!name || !phone || !address || !country || !username) {
      return res.status(400).json({ error: "name, phone, username, address, and country are required" });
    }
    if (!ageConfirmed) {
      return res.status(400).json({ error: "You must confirm you are at least 16 years old" });
    }
    const normalizedUsername = String(username || "").trim().toLowerCase();
    if (!/^[a-z0-9_.-]{3,20}$/.test(normalizedUsername)) {
      return res.status(400).json({ error: "Invalid username format" });
    }

    const supabaseAdmin = getSupabaseClient({ server: true });
    const client = supabaseAdmin || supabase;
    if (!client) {
      return res.status(500).json({ error: "Supabase client not available" });
    }

    if (supabaseAdmin) {
      const { data: existing } = await supabaseAdmin
        .from("profiles")
        .select("id")
        .eq("username", normalizedUsername)
        .maybeSingle();

      if (existing?.id && existing.id !== session.user.id) {
        return res.status(409).json({ error: "Username already taken" });
      }
    }

    const payload = {
      id: session.user.id,
      email: session.user.email,
      name,
      phone,
      username: normalizedUsername,
      address,
      country,
      age_confirmed: true,
      role: "user",
      updated_at: new Date().toISOString(),
    };

    let error = null;
    try {
      const resUpsert = await client.from("profiles").upsert(payload);
      error = resUpsert.error || null;
    } catch (e) {
      error = e;
    }

    if (error && error.code === "42703") {
      const { error: fallbackErr } = await client.from("profiles").upsert({
        id: session.user.id,
        email: session.user.email,
        name,
        phone,
        role: "user",
        updated_at: new Date().toISOString(),
      });
      error = fallbackErr || null;
    }

    if (error) {
      return res.status(500).json({ error: "failed to save profile" });
    }

    return res.status(200).json({ ok: true });
  } catch (e) {
    console.error(e);
    return res.status(500).json({ error: e.message || String(e) });
  }
}
