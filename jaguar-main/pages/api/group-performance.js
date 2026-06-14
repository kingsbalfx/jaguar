import { createPagesServerClient } from "@supabase/auth-helpers-nextjs";
import { getSupabaseClient } from "../../lib/supabaseClient";
import { getPaidAccess } from "../../lib/subscription-status";

export default async function handler(req, res) {
  if (req.method !== "GET") return res.status(405).json({ error: "Method not allowed" });

  const supabase = createPagesServerClient({ req, res });
  const { data: { session } } = await supabase.auth.getSession();
  if (!session?.user) return res.status(401).json({ error: "not authenticated" });

  const admin = getSupabaseClient({ server: true });
  const { data: profile } = await admin.from("profiles").select("role").eq("id", session.user.id).maybeSingle();
  const role = String(profile?.role || "user").toLowerCase();
  const plan = String(req.query.plan || role).toLowerCase();
  const access = await getPaidAccess({ supabaseAdmin: admin, email: session.user.email, role });

  if (role !== "admin" && (!access.active || access.plan !== plan)) {
    return res.status(403).json({ error: "This leaderboard is not available for your plan." });
  }

  const [quizResult, competitionResult] = await Promise.all([
    admin.from("quiz_results").select("id,user_id,email,plan,quiz_title,score,total,completed_at").eq("plan", plan).order("completed_at", { ascending: false }).limit(100),
    admin.from("competition_entries").select("id,user_id,email,plan,competition_title,points,rank,updated_at").eq("plan", plan).order("points", { ascending: false }).limit(100),
  ]);

  const missingTable = [quizResult.error, competitionResult.error].some((error) => error?.code === "42P01");
  if (!missingTable && (quizResult.error || competitionResult.error)) {
    return res.status(500).json({ error: quizResult.error?.message || competitionResult.error?.message });
  }

  return res.status(200).json({
    plan,
    quizzes: quizResult.data || [],
    competitions: competitionResult.data || [],
    setupRequired: missingTable,
  });
}
