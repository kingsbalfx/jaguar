import { createPagesServerClient } from "@supabase/auth-helpers-nextjs";
import { getSupabaseClient } from "../../../lib/supabaseClient";
import {
  CHALLENGE_PLATFORMS,
  cancelChallenge,
  createChallenge,
  expireOverdueChallenges,
  getChallengeContext,
  listChallenges,
  publicChallenge,
} from "../../../lib/challenges";

async function requireUser(req, res) {
  const supabase = createPagesServerClient({ req, res });
  const {
    data: { session },
  } = await supabase.auth.getSession();
  if (!session?.user) {
    res.status(401).json({ error: "not authenticated" });
    return null;
  }

  const supabaseAdmin = getSupabaseClient({ server: true });
  if (!supabaseAdmin) {
    res.status(500).json({ error: "Supabase admin client not configured" });
    return null;
  }

  const { data: profile } = await supabaseAdmin
    .from("profiles")
    .select("id,email,name,username,role,bot_tier")
    .eq("id", session.user.id)
    .maybeSingle();

  return {
    supabaseAdmin,
    user: {
      id: session.user.id,
      email: session.user.email,
      name: profile?.name || session.user.user_metadata?.full_name || null,
      username: profile?.username || null,
    },
    role: String(profile?.role || "user").toLowerCase(),
    botTier: profile?.bot_tier || "",
  };
}

function missingTable(error) {
  const message = String(error?.message || "").toLowerCase();
  return error?.code === "42P01" || message.includes("does not exist") || message.includes("schema cache");
}

const SQL_HINT =
  "Demo challenges are not installed. Run jaguar-main/sql/2026-09-28_student_challenges.sql in Supabase.";

function missingTableFromText(message) {
  return /does not exist|schema cache|42p01/i.test(String(message || ""));
}

export default async function handler(req, res) {
  const ctx = await requireUser(req, res);
  if (!ctx) return;
  const { supabaseAdmin, user, role, botTier } = ctx;

  try {
    if (req.method === "GET") {
      try {
        await expireOverdueChallenges(supabaseAdmin, { userId: user.id });
      } catch (error) {
        if (missingTable(error)) {
          return res.status(503).json({
            error: "Demo challenges are not installed. Run jaguar-main/sql/2026-09-28_student_challenges.sql in Supabase.",
            missingTable: true,
          });
        }
        throw error;
      }

      const context = await getChallengeContext({
        supabaseAdmin,
        userId: user.id,
        email: user.email,
        role,
        botTier,
      });
      const rows = await listChallenges(supabaseAdmin, { userId: user.id, limit: 20 });

      return res.status(200).json({
        context,
        platforms: CHALLENGE_PLATFORMS.filter((platform) =>
          context.rules.platforms.includes(platform.id),
        ),
        challenges: rows.map(publicChallenge),
      });
    }

    if (req.method === "POST") {
      const { platform, goal, experience } = req.body || {};
      const context = await getChallengeContext({
        supabaseAdmin,
        userId: user.id,
        email: user.email,
        role,
        botTier,
      });

      const result = await createChallenge({
        supabaseAdmin,
        user,
        platform,
        goal,
        experience,
        context,
      });

      if (result.error) {
        if (missingTableFromText(result.error)) {
          return res.status(503).json({ error: SQL_HINT, missingTable: true });
        }
        return res.status(result.status || 400).json({ error: result.error, context });
      }
      return res.status(200).json({ ok: true, challenge: result.challenge, context });
    }

    if (req.method === "DELETE" || req.method === "PATCH") {
      const id = String(req.query.id || req.body?.id || "").trim();
      if (!id) return res.status(400).json({ error: "challenge id is required" });

      const { data: challenge } = await supabaseAdmin
        .from("challenges")
        .select("*")
        .eq("id", id)
        .eq("user_id", user.id)
        .maybeSingle();
      if (!challenge) return res.status(404).json({ error: "challenge not found" });
      if (!["pending", "active"].includes(challenge.status)) {
        return res.status(409).json({ error: `A ${challenge.status} challenge cannot be cancelled` });
      }

      const result = await cancelChallenge({
        supabaseAdmin,
        challenge,
        reason: req.body?.reason || "Cancelled by the student",
      });
      if (result.error) {
        if (missingTableFromText(result.error)) {
          return res.status(503).json({ error: SQL_HINT, missingTable: true });
        }
        return res.status(result.status || 500).json({ error: result.error });
      }
      return res.status(200).json({ ok: true, challenge: result.challenge });
    }

    return res.status(405).json({ error: "Method not allowed" });
  } catch (error) {
    if (missingTable(error)) {
      return res.status(503).json({
        error: "Demo challenges are not installed. Run jaguar-main/sql/2026-09-28_student_challenges.sql in Supabase.",
        missingTable: true,
      });
    }
    return res.status(500).json({ error: error.message || String(error) });
  }
}
