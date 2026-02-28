import { getSupabaseClient } from "../../../lib/supabaseClient";

export default async function handler(req, res) {
  if (req.method !== "POST") {
    return res.status(405).json({ error: "Method not allowed" });
  }

  const {
    email,
    password,
    fullName,
    phone,
    address,
    country,
    ageConfirmed,
  } = req.body || {};

  if (!email || !password || !fullName || !phone || !address || !country) {
    return res.status(400).json({ error: "Missing required fields" });
  }
  if (!ageConfirmed) {
    return res.status(400).json({ error: "Age confirmation required" });
  }

  const supabaseAdmin = getSupabaseClient({ server: true });
  if (!supabaseAdmin) {
    return res.status(500).json({
      error: "Supabase admin client not configured (SUPABASE_SERVICE_ROLE_KEY required)",
    });
  }

  try {
    const { data, error } = await supabaseAdmin.auth.admin.createUser({
      email,
      password,
      email_confirm: true,
      user_metadata: {
        full_name: fullName,
        phone,
        address,
        country,
        age_confirmed: true,
      },
    });

    if (error) {
      const msg = error.message || "Failed to create user";
      if (msg.toLowerCase().includes("already registered")) {
        return res.status(409).json({ error: "User already exists" });
      }
      return res.status(500).json({ error: msg });
    }

    const userId = data?.user?.id;
    if (userId) {
      const payload = {
        id: userId,
        email,
        name: fullName,
        phone,
        address,
        country,
        age_confirmed: true,
        role: "user",
        updated_at: new Date().toISOString(),
      };
      let profileErr = null;
      try {
        const { error: upErr } = await supabaseAdmin.from("profiles").upsert(payload);
        profileErr = upErr || null;
      } catch (e) {
        profileErr = e;
      }

      if (profileErr && profileErr.code === "42703") {
        await supabaseAdmin.from("profiles").upsert({
          id: userId,
          email,
          name: fullName,
          phone,
          role: "user",
          updated_at: new Date().toISOString(),
        });
      }
    }

    return res.status(200).json({ ok: true, userId: userId || null });
  } catch (err) {
    console.error("signup api error:", err);
    return res.status(500).json({ error: err.message || "Unexpected error" });
  }
}
