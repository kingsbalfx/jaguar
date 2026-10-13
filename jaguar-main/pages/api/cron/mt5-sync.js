import { getSupabaseClient } from "../../../lib/supabaseClient";
import { MAX_LINKS_PER_RUN, syncAllLinks } from "../../../services/mt5Sync";

/**
 * Vercel cron entry point for the MT5 trade-history sync.
 * Auth: Authorization: Bearer $CRON_SECRET (same contract as
 * /api/cron/subscription-notifications).
 *
 * Optional query params:
 *   limit  - max links to process (default 50)
 *   ids    - comma separated mt5_account_links ids to sync only those accounts
 */
export default async function handler(req, res) {
  if (req.method !== "GET" && req.method !== "POST") {
    return res.status(405).json({ error: "Method not allowed" });
  }

  const token = String(req.headers.authorization || "").replace(/^Bearer\s+/i, "");
  if (!process.env.CRON_SECRET || token !== process.env.CRON_SECRET) {
    return res.status(401).json({ error: "unauthorized" });
  }

  const supabaseAdmin = getSupabaseClient({ server: true });
  if (!supabaseAdmin) return res.status(500).json({ error: "Supabase admin client not configured" });

  try {
    const parsedLimit = Number.parseInt(String(req.query.limit || ""), 10);
    const limit = Number.isFinite(parsedLimit) && parsedLimit > 0 ? Math.min(parsedLimit, MAX_LINKS_PER_RUN) : MAX_LINKS_PER_RUN;
    const linkIds = String(req.query.ids || "")
      .split(",")
      .map((value) => value.trim())
      .filter(Boolean);

    const result = await syncAllLinks({
      supabaseAdmin,
      trigger: "cron",
      limit,
      linkIds: linkIds.length ? linkIds : null,
    });

    if (result.status === "skipped") {
      return res.status(200).json({ ok: true, skipped: true, reason: result.reason, bridge: result.bridge });
    }
    return res.status(result.ok ? 200 : 207).json(result);
  } catch (error) {
    console.error("mt5 cron sync failed:", error);
    return res.status(500).json({ error: error?.message || "mt5 sync failed" });
  }
}
