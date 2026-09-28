import { createPagesServerClient } from "@supabase/auth-helpers-nextjs";
import { getSupabaseClient } from "../../../lib/supabaseClient";
import { challengeCredentials } from "../../../lib/challenges";

/**
 * Reveal the decrypted demo credentials for a challenge the caller owns (or any
 * challenge when the caller is an admin). Passwords are never returned in list
 * endpoints, only from here.
 */
export default async function handler(req, res) {
  if (req.method !== "GET") {
    return res.status(405).json({ error: "Method not allowed" });
  }

  const supabase = createPagesServerClient({ req, res });
  const {
    data: { session },
  } = await supabase.auth.getSession();
  if (!session?.user) return res.status(401).json({ error: "not authenticated" });

  const supabaseAdmin = getSupabaseClient({ server: true });
  if (!supabaseAdmin) return res.status(500).json({ error: "Supabase admin client not configured" });

  const id = String(req.query.id || "").trim();
  if (!id) return res.status(400).json({ error: "challenge id is required" });

  try {
    const { data: profile } = await supabaseAdmin
      .from("profiles")
      .select("role")
      .eq("id", session.user.id)
      .maybeSingle();
    const isAdmin = String(profile?.role || "").toLowerCase() === "admin";

    let query = supabaseAdmin.from("challenges").select("*").eq("id", id);
    if (!isAdmin) query = query.eq("user_id", session.user.id);
    const { data: challenge, error } = await query.maybeSingle();

    if (error) {
      const message = String(error.message || "").toLowerCase();
      if (error.code === "42P01" || message.includes("does not exist")) {
        return res.status(503).json({
          error: "Demo challenges are not installed. Run jaguar-main/sql/2026-09-28_student_challenges.sql in Supabase.",
          missingTable: true,
        });
      }
      throw error;
    }
    if (!challenge) return res.status(404).json({ error: "challenge not found" });

    if (!["active", "approved"].includes(challenge.status)) {
      return res.status(409).json({
        error: `Credentials are only available for active challenges (this one is ${challenge.status}).`,
      });
    }

    return res.status(200).json({ credentials: challengeCredentials(challenge) });
  } catch (error) {
    return res.status(500).json({ error: error.message || String(error) });
  }
}
