import { requireAdmin, toPositiveInt } from "../../../lib/api-auth";
import { getSyncSnapshot, syncLink } from "../../../services/mt5Sync";

const LINK_COLUMNS =
  "id,user_id,email,login,server,label,currency,leverage,provider,bridge_account_id,bridge_region,provisioning_status,provisioning_error,sync_enabled,sync_status,sync_error,last_synced_at,last_deal_time,last_sync_deals,total_synced_deals,sync_lookback_days,password_last4,created_at,updated_at";

/**
 * Admin account-link management (never returns credentials, only the password hint).
 *
 *   GET    ?userId=&login=&syncEnabled=&status=&limit=&withCounts=1
 *   POST   { id, reset?, lookbackDays?, provider? }  -> trigger a sync now
 *   PATCH  { id, sync_enabled?, label?, sync_lookback_days?, provider? }
 *   DELETE { id } | ?id=
 */
export default async function handler(req, res) {
  if (!["GET", "POST", "PATCH", "DELETE"].includes(req.method)) {
    return res.status(405).json({ error: "Method not allowed" });
  }

  const auth = await requireAdmin(req, res);
  if (!auth.ok) return res.status(auth.status).json({ error: auth.error });
  const { supabaseAdmin } = auth;

  try {
    if (req.method === "GET") {
      const limit = toPositiveInt(req.query.limit, 50, { min: 1, max: 200 });
      let query = supabaseAdmin
        .from("mt5_account_links")
        .select(LINK_COLUMNS)
        .order("created_at", { ascending: false })
        .limit(limit);

      const userId = String(req.query.userId || req.query.user_id || "").trim();
      const login = String(req.query.login || "").trim();
      const status = String(req.query.status || "").trim();
      if (userId) query = query.eq("user_id", userId);
      if (login) query = query.eq("login", login);
      if (status) query = query.eq("sync_status", status);
      if (req.query.syncEnabled === "true") query = query.eq("sync_enabled", true);
      if (req.query.syncEnabled === "false") query = query.eq("sync_enabled", false);

      const { data, error } = await query;
      if (error) {
        if (error.code === "42P01" || /does not exist/i.test(error.message || "")) {
          return res.status(200).json({ ok: true, setupRequired: true, links: [] });
        }
        return res.status(500).json({ error: error.message });
      }

      const links = data || [];
      if (req.query.withCounts === "1" && links.length) {
        await Promise.all(
          links.map(async (link) => {
            const { count } = await supabaseAdmin
              .from("trade_history")
              .select("id", { count: "exact", head: true })
              .eq("link_id", link.id);
            link.tradeCount = count || 0;
          }),
        );
      }

      const snapshot = await getSyncSnapshot(supabaseAdmin, { isAdmin: true, limit: 10 });
      return res.status(200).json({
        ok: true,
        setupRequired: false,
        bridge: snapshot.bridge,
        links,
        runs: snapshot.runs,
        totals: snapshot.totals,
      });
    }

    const body = req.body || {};
    const linkId = String(body.id || body.linkId || req.query.id || "").trim();

    if (req.method === "DELETE") {
      if (!linkId) return res.status(400).json({ error: "id is required" });
      const { error } = await supabaseAdmin.from("mt5_account_links").delete().eq("id", linkId);
      if (error) return res.status(500).json({ error: error.message });
      return res.status(200).json({ ok: true, removed: linkId });
    }

    if (req.method === "PATCH") {
      if (!linkId) return res.status(400).json({ error: "id is required" });
      const patch = {};
      if (body.sync_enabled !== undefined) patch.sync_enabled = Boolean(body.sync_enabled);
      if (body.label !== undefined) patch.label = body.label ? String(body.label).slice(0, 80) : null;
      if (body.provider !== undefined) patch.provider = String(body.provider).slice(0, 40);
      if (body.lookbackDays !== undefined || body.sync_lookback_days !== undefined) {
        const days = Number(body.lookbackDays ?? body.sync_lookback_days);
        if (Number.isFinite(days) && days > 0) patch.sync_lookback_days = Math.min(Math.round(days), 3650);
      }
      if (!Object.keys(patch).length) return res.status(400).json({ error: "nothing to update" });

      const { data, error } = await supabaseAdmin
        .from("mt5_account_links")
        .update({ ...patch, updated_at: new Date().toISOString() })
        .eq("id", linkId)
        .select(LINK_COLUMNS)
        .maybeSingle();
      if (error) return res.status(500).json({ error: error.message });
      if (!data) return res.status(404).json({ error: "account link not found" });
      return res.status(200).json({ ok: true, link: data });
    }

    if (!linkId) return res.status(400).json({ error: "id is required" });

    if (body.reset) {
      await supabaseAdmin
        .from("mt5_account_links")
        .update({ last_deal_time: null, last_synced_at: null, updated_at: new Date().toISOString() })
        .eq("id", linkId);
    }

    const { data: link, error } = await supabaseAdmin
      .from("mt5_account_links")
      .select(LINK_COLUMNS)
      .eq("id", linkId)
      .maybeSingle();
    if (error) return res.status(500).json({ error: error.message });
    if (!link) return res.status(404).json({ error: "account link not found" });

    const result = await syncLink({
      supabaseAdmin,
      link,
      trigger: "admin",
      provider: body.provider || undefined,
      lookbackDays: body.lookbackDays ? Number(body.lookbackDays) : undefined,
    });
    return res.status(result.ok ? 200 : result.status === "partial" ? 207 : 502).json({ ...result, link });
  } catch (error) {
    console.error("admin mt5 links failed:", error);
    return res.status(500).json({ error: error?.message || "failed to manage MT5 links" });
  }
}
