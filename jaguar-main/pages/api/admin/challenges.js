import { createPagesServerClient } from "@supabase/auth-helpers-nextjs";
import { getSupabaseClient } from "../../../lib/supabaseClient";
import {
  approveChallenge,
  cancelChallenge,
  expireOverdueChallenges,
  publicChallenge,
  publicDemoAccount,
  rejectChallenge,
} from "../../../lib/challenges";

function missingTable(error) {
  const message = String(error?.message || "").toLowerCase();
  return error?.code === "42P01" || message.includes("does not exist") || message.includes("schema cache");
}

function missingTableFromText(message) {
  return /does not exist|schema cache|42p01/i.test(String(message || ""));
}

async function requireAdmin(req, res) {
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
    .select("role")
    .eq("id", session.user.id)
    .maybeSingle();

  const role = String(profile?.role || "user").toLowerCase();
  const adminEmail = (
    process.env.SUPER_ADMIN_EMAIL ||
    process.env.NEXT_PUBLIC_ADMIN_EMAIL ||
    ""
  ).toLowerCase();
  const userEmail = String(session.user.email || "").toLowerCase();
  if (role !== "admin" && !(adminEmail && userEmail === adminEmail)) {
    res.status(403).json({ error: "forbidden" });
    return null;
  }

  return { supabaseAdmin, adminId: session.user.id };
}

async function loadChallenge(supabaseAdmin, id) {
  const { data } = await supabaseAdmin.from("challenges").select("*").eq("id", id).maybeSingle();
  return data || null;
}

export default async function handler(req, res) {
  const ctx = await requireAdmin(req, res);
  if (!ctx) return;
  const { supabaseAdmin, adminId } = ctx;

  try {
    if (req.method === "GET") {
      let expired = 0;
      try {
        expired = await expireOverdueChallenges(supabaseAdmin);
      } catch (error) {
        if (missingTable(error)) {
          return res.status(503).json({
            error:
              "Demo challenges are not installed. Run jaguar-main/sql/2026-09-28_student_challenges.sql in Supabase.",
            missingTable: true,
          });
        }
      }

      const [{ data: challenges, error }, { data: pool, error: poolError }] = await Promise.all([
        supabaseAdmin
          .from("challenges")
          .select("*")
          .order("created_at", { ascending: false })
          .limit(200),
        supabaseAdmin
          .from("challenge_demo_accounts")
          .select("*")
          .order("created_at", { ascending: false })
          .limit(200),
      ]);
      if (error) throw error;
      if (poolError && !missingTable(poolError)) throw poolError;

      const accounts = pool || [];
      const warnings = [];
      for (const platform of ["mt5", "tradingview"]) {
        const available = accounts.filter(
          (account) => account.platform === platform && account.status === "available",
        ).length;
        if (available === 0) {
          warnings.push(
            `No available ${platform.toUpperCase()} demo accounts in the pool — approvals cannot hand out credentials.`,
          );
        }
      }

      return res.status(200).json({
        challenges: (challenges || []).map(publicChallenge),
        pool: accounts.map(publicDemoAccount),
        stats: {
          pending: (challenges || []).filter((item) => item.status === "pending").length,
          active: (challenges || []).filter((item) => item.status === "active").length,
          expiredNow: expired,
          poolTotal: accounts.length,
          poolAvailable: accounts.filter((item) => item.status === "available").length,
        },
        warnings,
        fetchedAt: new Date().toISOString(),
      });
    }

    if (req.method !== "POST") {
      return res.status(405).json({ error: "Method not allowed" });
    }

    const { action, id } = req.body || {};
    if (!action) return res.status(400).json({ error: "action is required" });

    if (action === "expire") {
      const expired = await expireOverdueChallenges(supabaseAdmin);
      return res.status(200).json({ ok: true, expired });
    }

    const challenge = id ? await loadChallenge(supabaseAdmin, id) : null;
    if (!challenge) return res.status(404).json({ error: "challenge not found" });

    if (action === "approve") {
      const result = await approveChallenge({
        supabaseAdmin,
        challenge,
        adminId,
        durationDays: req.body.durationDays,
        note: req.body.note,
        accountId: req.body.accountId,
      });
      if (result.error) {
        if (missingTableFromText(result.error)) {
          return res.status(503).json({
            error:
              "Demo challenges are not installed. Run jaguar-main/sql/2026-09-28_student_challenges.sql in Supabase.",
            missingTable: true,
          });
        }
        return res.status(result.status || 500).json({ error: result.error });
      }
      return res.status(200).json({ ok: true, ...result });
    }

    if (action === "reject") {
      const result = await rejectChallenge({
        supabaseAdmin,
        challenge,
        adminId,
        reason: req.body.reason,
        note: req.body.note,
      });
      if (result.error) {
        if (missingTableFromText(result.error)) {
          return res.status(503).json({
            error:
              "Demo challenges are not installed. Run jaguar-main/sql/2026-09-28_student_challenges.sql in Supabase.",
            missingTable: true,
          });
        }
        return res.status(result.status || 500).json({ error: result.error });
      }
      return res.status(200).json({ ok: true, challenge: result.challenge });
    }

    if (action === "cancel") {
      const result = await cancelChallenge({
        supabaseAdmin,
        challenge,
        reason: req.body.reason || "Cancelled by admin",
      });
      if (result.error) {
        if (missingTableFromText(result.error)) {
          return res.status(503).json({
            error:
              "Demo challenges are not installed. Run jaguar-main/sql/2026-09-28_student_challenges.sql in Supabase.",
            missingTable: true,
          });
        }
        return res.status(result.status || 500).json({ error: result.error });
      }
      return res.status(200).json({ ok: true, challenge: result.challenge });
    }

    if (action === "note") {
      const { data, error } = await supabaseAdmin
        .from("challenges")
        .update({
          admin_note: String(req.body.note || "").trim().slice(0, 600) || null,
          updated_at: new Date().toISOString(),
        })
        .eq("id", challenge.id)
        .select("*")
        .maybeSingle();
      if (error) return res.status(500).json({ error: error.message });
      return res.status(200).json({ ok: true, challenge: publicChallenge(data) });
    }

    return res.status(400).json({ error: "unknown action" });
  } catch (error) {
    if (missingTable(error)) {
      return res.status(503).json({
        error:
          "Demo challenges are not installed. Run jaguar-main/sql/2026-09-28_student_challenges.sql in Supabase.",
        missingTable: true,
      });
    }
    return res.status(500).json({ error: error.message || String(error) });
  }
}

