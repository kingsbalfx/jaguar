import { getSupabaseClient } from "../../../lib/supabaseClient";
import { emailLayout, sendLifecycleEmail } from "../../../lib/mailer";
import { getURL } from "../../../lib/getURL";

export default async function handler(req, res) {
  if (req.method !== "POST") return res.status(405).json({ error: "Method not allowed" });
  const email = String(req.body?.email || "").trim().toLowerCase();
  if (!email) return res.status(400).json({ error: "Email is required" });
  const supabaseAdmin = getSupabaseClient({ server: true });
  if (!supabaseAdmin) return res.status(500).json({ error: "Supabase admin client not configured" });

  try {
    const redirectTo = `${getURL().replace(/\/$/, "")}/reset-password`;
    const { data, error } = await supabaseAdmin.auth.admin.generateLink({
      type: "recovery",
      email,
      options: { redirectTo },
    });
    if (!error && data?.properties?.action_link) {
      await sendLifecycleEmail({
        supabaseAdmin,
        email,
        type: "password_recovery",
        dedupeKey: `password_recovery:${email}:${new Date().toISOString().slice(0, 13)}`,
        subject: "Reset your KINGSBALFX password",
        text: `Reset your password: ${data.properties.action_link}`,
        html: emailLayout(
          "Reset your password",
          "<p>We received a request to reset your password. If this was not you, you can ignore this email.</p>",
          "Reset password",
          data.properties.action_link,
        ),
      });
    }
    return res.status(200).json({ ok: true });
  } catch (error) {
    console.error("forgot password error:", error);
    return res.status(200).json({ ok: true });
  }
}
