import { authenticateRequest } from "../../../lib/api-auth";
import { encryptMt5Password } from "../../../lib/mt5-crypto";
import { ensureMetaApiAccount, getBridgeHealth, resolveBridgeProvider } from "../../../lib/mt5-bridge";
import { getPaidAccess } from "../../../lib/subscription-status";
import { getPricingTier } from "../../../lib/pricing-config";
import { getSyncSnapshot, syncLink } from "../../../services/mt5Sync";

const LINK_COLUMNS =
  "id,user_id,login,server,label,currency,leverage,provider,bridge_account_id,bridge_region,provisioning_status,provisioning_error,sync_enabled,sync_status,sync_error,last_synced_at,last_deal_time,last_sync_deals,total_synced_deals,sync_lookback_days,created_at,updated_at";

async function assertBotTestingAccess(auth) {
  const { supabaseAdmin, role, isAdmin, email } = auth;
  const access = await getPaidAccess({ supabaseAdmin, email, role });
  const testingAllowed =
    isAdmin ||
    access.plans?.some((plan) => {
      const tier = getPricingTier(plan);
      return tier?.features?.botAccess || tier?.features?.privateTestingOnly;
    });
  if (!access.active) return { ok: false, status: 403, error: "active subscription required" };
  if (!testingAllowed) {
    return { ok: false, status: 403, error: "private bot testing is not included in your active plan" };
  }
  return { ok: true };
}

async function loadOwnedLink(supabaseAdmin, { linkId, userId }) {
  const { data, error } = await supabaseAdmin
    .from("mt5_account_links")
    .select(LINK_COLUMNS)
    .eq("id", linkId)
    .eq("user_id", userId)
    .maybeSingle();
  if (error) throw error;
  return data || null;
}

/** GET = sync status snapshot, POST = link an account (and sync it), DELETE = unlink. */
export default async function handler(req, res) {
  if (req.method !== "GET" && req.method !== "POST" && req.method !== "DELETE") {
    return res.status(405).json({ error: "Method not allowed" });
  }

  const auth = await authenticateRequest(req, res);
  if (!auth.ok) return res.status(auth.status).json({ error: auth.error });
  const { supabaseAdmin, session, email } = auth;

  try {
    if (req.method === "GET") {
      const snapshot = await getSyncSnapshot(supabaseAdmin, { userId: session.user.id, isAdmin: auth.isAdmin });
      return res.status(200).json(snapshot);
    }

    if (req.method === "DELETE") {
      const linkId = String(req.body?.linkId || req.query.linkId || "").trim();
      if (!linkId) return res.status(400).json({ error: "linkId is required" });
      const { error } = await supabaseAdmin
        .from("mt5_account_links")
        .delete()
        .eq("id", linkId)
        .eq("user_id", session.user.id);
      if (error) return res.status(500).json({ error: error.message || "failed to remove account link" });
      return res.status(200).json({ ok: true, removed: linkId });
    }

    return await linkAccount(req, res, { auth, supabaseAdmin, session, email });
  } catch (error) {
    console.error("mt5 user sync failed:", error);
    return res.status(500).json({ error: error?.message || "mt5 sync failed" });
  }
}

/** Provision (idempotently) the hosted terminal that backs a MetaApi link. */
async function provisionLink(supabaseAdmin, link, password, label) {
  if (!link || link.provider !== "metaapi" || !process.env.METAAPI_TOKEN) return link;
  try {
    const provisioning = await ensureMetaApiAccount({
      login: link.login,
      server: link.server,
      region: link.bridge_region || process.env.METAAPI_REGION || undefined,
      accountId: link.bridge_account_id || undefined,
      name: label || link.label || `kingsbalfx-${link.login}`,
      password: password || undefined,
    });
    const account = provisioning.account || {};
    const { data } = await supabaseAdmin
      .from("mt5_account_links")
      .update({
        bridge_account_id: account._id || account.id || link.bridge_account_id || null,
        bridge_region: account.region || link.bridge_region || null,
        provisioning_status: String(account.state || "").toUpperCase() === "DEPLOYED" ? "ready" : "provisioning",
        provisioning_error: null,
        updated_at: new Date().toISOString(),
      })
      .eq("id", link.id)
      .select(LINK_COLUMNS)
      .maybeSingle();
    return data || link;
  } catch (error) {
    await supabaseAdmin
      .from("mt5_account_links")
      .update({ provisioning_status: "error", provisioning_error: String(error?.message || error).slice(0, 500) })
      .eq("id", link.id);
    return link;
  }
}

/** Create or refresh the caller's account link, then sync it immediately. */
async function linkAccount(req, res, { auth, supabaseAdmin, session, email }) {
  const body = req.body || {};
  const accessCheck = await assertBotTestingAccess(auth);
  if (!accessCheck.ok) return res.status(accessCheck.status).json({ error: accessCheck.error });

  const now = new Date().toISOString();
  let link = null;
  let password = String(body.password || "");

  if (body.linkId) {
    link = await loadOwnedLink(supabaseAdmin, { linkId: String(body.linkId), userId: session.user.id });
    if (!link) return res.status(404).json({ error: "account link not found" });
    const patch = { updated_at: now };
    if (password) Object.assign(patch, encryptMt5Password(password));
    if (body.syncEnabled !== undefined) patch.sync_enabled = Boolean(body.syncEnabled);
    if (body.label !== undefined) patch.label = body.label ? String(body.label).slice(0, 80) : null;
    if (body.lookbackDays) patch.sync_lookback_days = Math.max(1, Math.min(Number(body.lookbackDays) || 0, 3650));
    if (Object.keys(patch).length > 1) {
      const { data } = await supabaseAdmin
        .from("mt5_account_links")
        .update(patch)
        .eq("id", link.id)
        .select(LINK_COLUMNS)
        .maybeSingle();
      link = data || link;
    }
  } else {
    const login = String(body.login || "").trim();
    const server = String(body.server || "").trim();
    if (!login || !server) return res.status(400).json({ error: "login and server are required" });
    if (!process.env.MT5_CREDENTIALS_SECRET && process.env.NODE_ENV === "production") {
      return res.status(503).json({ error: "credential encryption is not configured" });
    }

    const existing = await supabaseAdmin
      .from("mt5_account_links")
      .select(LINK_COLUMNS)
      .eq("user_id", session.user.id)
      .eq("login", login)
      .eq("server", server)
      .maybeSingle();
    if (existing.error && !/does not exist/i.test(existing.error.message || "")) {
      return res.status(500).json({ error: existing.error.message || "failed to load account link" });
    }

    const resolved = resolveBridgeProvider(body.provider);
    const payload = {
      user_id: session.user.id,
      email,
      login,
      server,
      label: body.label ? String(body.label).slice(0, 80) : null,
      sync_enabled: body.syncEnabled === false ? false : true,
      provider: resolved.provider || existing.data?.provider || "metaapi",
      ...(body.lookbackDays
        ? { sync_lookback_days: Math.max(1, Math.min(Number(body.lookbackDays) || 0, 3650)) }
        : {}),
      ...(password ? encryptMt5Password(password) : {}),
      updated_at: now,
    };

    if (!payload.password_encrypted && !existing.data?.password_encrypted) {
      return res.status(400).json({ error: "password is required for first-time setup" });
    }
    if (!resolved.configured) {
      payload.provisioning_status = "error";
      payload.provisioning_error = resolved.reason || "MT5 bridge is not configured";
    }

    if (existing.data?.id) {
      const { data, error } = await supabaseAdmin
        .from("mt5_account_links")
        .update(payload)
        .eq("id", existing.data.id)
        .select(LINK_COLUMNS)
        .maybeSingle();
      if (error) return res.status(500).json({ error: error.message || "failed to update account link" });
      link = data || existing.data;
    } else {
      const { data, error } = await supabaseAdmin
        .from("mt5_account_links")
        .insert({ ...payload, created_at: now, provisioning_status: payload.provisioning_status || "pending" })
        .select(LINK_COLUMNS)
        .maybeSingle();
      if (error) {
        if (error.code === "42P01" || /does not exist/i.test(error.message || "")) {
          return res
            .status(503)
            .json({ error: "MT5 sync tables are missing. Apply sql/2026-10-13_mt5_trade_sync.sql." });
        }
        return res.status(500).json({ error: error.message || "failed to create account link" });
      }
      link = data;
    }

    if (body.provision !== false) {
      link = await provisionLink(supabaseAdmin, link, password, payload.label);
    }
  }

  const result = await syncLink({ supabaseAdmin, link, trigger: "manual" });
  const snapshot = await getSyncSnapshot(supabaseAdmin, { userId: session.user.id, isAdmin: auth.isAdmin });
  return res.status(result.ok ? 200 : result.status === "partial" ? 207 : 502).json({
    ...result,
    bridge: getBridgeHealth(),
    link,
    links: snapshot.links,
    runs: snapshot.runs,
  });
}

