import { createPagesServerClient } from "@supabase/auth-helpers-nextjs";
import { getSupabaseClient } from "../../../lib/supabaseClient";

const BOT_TIMEOUT_MS = Number(process.env.BOT_API_TIMEOUT_MS || 8000);

function botBaseUrl() {
  return String(process.env.BOT_API_INTERNAL || process.env.BOT_API_URL || "")
    .trim()
    .replace(/\/+$/, "");
}

function botToken() {
  return String(
    process.env.BOT_API_TOKEN || process.env.BOT_SIGNAL_SECRET || process.env.ADMIN_API_KEY || "",
  ).trim();
}

async function botRequest(path, { method = "GET", body } = {}) {
  const base = botBaseUrl();
  if (!base) return { ok: false, configured: false, reason: "BOT_API_URL not configured" };
  const token = botToken();
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), BOT_TIMEOUT_MS);
  try {
    const response = await fetch(`${base}${path}`, {
      method,
      headers: {
        "Content-Type": "application/json",
        ...(token ? { "x-bot-api-token": token, Authorization: `Bearer ${token}` } : {}),
      },
      body: body ? JSON.stringify(body) : undefined,
      signal: controller.signal,
      cache: "no-store",
    });
    const data = await response.json().catch(() => ({}));
    return { ok: response.ok, configured: true, status: response.status, data };
  } catch (error) {
    return { ok: false, configured: true, reason: error.message || "bot unreachable" };
  } finally {
    clearTimeout(timer);
  }
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

  return { supabaseAdmin, session };
}

function mergeAccounts(rows) {
  const merged = new Map();
  for (const row of rows) {
    const login = String(row.login || "").trim();
    if (!login) continue;
    const current = merged.get(login) || { login, sources: [] };
    for (const [key, value] of Object.entries(row)) {
      if (value === null || value === undefined || value === "" || key === "sources") continue;
      current[key] = value;
    }
    for (const source of row.sources || []) {
      if (!current.sources.includes(source)) current.sources.push(source);
    }
    merged.set(login, current);
  }
  return [...merged.values()].map((account) => ({
    ...account,
    sources: [...account.sources].sort(),
    enabled: account.disabled ? false : account.enabled !== false,
    running: Boolean(account.running),
  }));
}

async function loadWebRows(supabaseAdmin) {
  const warnings = [];

  const credentialColumns = "login,server,user_id,email,active,enabled,api_port,created_at,updated_at";
  let credentials = await supabaseAdmin
    .from("mt5_credentials")
    .select(credentialColumns)
    .order("updated_at", { ascending: false });
  if (credentials.error) {
    credentials = await supabaseAdmin.from("mt5_credentials").select("login,server,active");
    if (credentials.error) {
      warnings.push(`mt5_credentials: ${credentials.error.message}`);
      credentials = { data: [] };
    } else {
      warnings.push("mt5_credentials is missing some columns (email/api_port/enabled).");
    }
  }

  let submissions = await supabaseAdmin
    .from("mt5_submissions")
    .select("login,server,email,user_id,status,created_at")
    .order("created_at", { ascending: false })
    .limit(50);
  if (submissions.error) {
    submissions = await supabaseAdmin
      .from("mt5_submissions")
      .select("login,server,status,created_at")
      .order("created_at", { ascending: false })
      .limit(50);
    if (submissions.error) {
      warnings.push(`mt5_submissions: ${submissions.error.message}`);
      submissions = { data: [] };
    }
  }

  return {
    credentials: credentials.data || [],
    submissions: submissions.data || [],
    warnings,
  };
}

function buildInventory({ credentials, submissions, botInventory }) {
  const rows = [];

  for (const row of credentials) {
    rows.push({
      login: row.login,
      server: row.server,
      email: row.email || null,
      userId: row.user_id || null,
      apiPort: row.api_port || null,
      webActive: row.active !== false,
      enabled: row.enabled !== false,
      disabled: row.enabled === false,
      sources: ["web"],
      updatedAt: row.updated_at || row.created_at || null,
    });
  }

  for (const account of botInventory?.accounts || []) {
    rows.push({
      login: account.login,
      server: account.server || null,
      email: account.email || null,
      userId: account.user_id || null,
      botId: account.bot_id || null,
      apiPort: account.api_port || null,
      mt5Path: account.mt5_path || null,
      symbols: account.symbols || null,
      sources: account.sources?.length ? account.sources : ["local"],
      running: Boolean(account.running),
      enabled: account.enabled !== false,
      disabled: Boolean(account.disabled),
      disabledReason: account.disabled_reason || null,
      terminalOk: Boolean(account.terminal_ok),
      terminalReason: account.terminal_reason || null,
      hasPassword: Boolean(account.has_password),
      webActive: account.enabled !== false,
    });
  }

  const accounts = mergeAccounts(rows).sort((a, b) => {
    if (a.running !== b.running) return a.running ? -1 : 1;
    return String(a.login).localeCompare(String(b.login));
  });

  const submissionStatusByLogin = new Map();
  for (const submission of submissions) {
    const login = String(submission.login || "").trim();
    if (!login) continue;
    const existing = submissionStatusByLogin.get(login);
    if (!existing || new Date(submission.created_at) > new Date(existing.created_at)) {
      submissionStatusByLogin.set(login, submission);
    }
  }
  for (const account of accounts) {
    const submission = submissionStatusByLogin.get(String(account.login));
    if (submission) {
      account.submissionStatus = submission.status || "pending";
      account.submissionCreatedAt = submission.created_at || null;
      if (!account.sources.includes("submission")) account.sources.push("submission");
    }
    account.sources = [...new Set(account.sources)].sort();
  }

  return { accounts };
}


export default async function handler(req, res) {
  const ctx = await requireAdmin(req, res);
  if (!ctx) return;
  const { supabaseAdmin } = ctx;

  try {
    if (req.method === "GET") {
      const [web, bot] = await Promise.all([
        loadWebRows(supabaseAdmin),
        botRequest("/admin/accounts"),
      ]);
      const botInventory = bot.ok ? bot.data : null;
      const { accounts } = buildInventory({
        credentials: web.credentials,
        submissions: web.submissions,
        botInventory,
      });

      const warnings = [...web.warnings];
      if (!bot.ok) {
        warnings.push(
          bot.configured
            ? `Live bot inventory unavailable (${bot.reason || `status ${bot.status}`}). Showing website submissions only.`
            : "BOT_API_URL is not configured, so local/env accounts cannot be listed.",
        );
      }

      return res.status(200).json({
        accounts,
        submissions: web.submissions,
        summary: {
          total: accounts.length,
          running: accounts.filter((account) => account.running).length,
          disabled: accounts.filter((account) => account.disabled).length,
          pendingSubmissions: web.submissions.filter(
            (submission) => String(submission.status || "").toLowerCase() === "pending",
          ).length,
        },
        bot: bot.ok
          ? {
              reachable: true,
              acceptWeb: botInventory?.accept_web !== false,
              localStore: botInventory?.local_store || null,
              activeRegistry: botInventory?.active_registry || null,
              liveStale: Boolean(botInventory?.live_stale),
            }
          : { reachable: false, configured: bot.configured, reason: bot.reason || null },
        warnings,
        fetchedAt: new Date().toISOString(),
      });
    }

    if (req.method !== "POST") {
      return res.status(405).json({ error: "Method not allowed" });
    }

    const { action, ...body } = req.body || {};

    if (action === "add") {
      const login = String(body.login || "").trim();
      const server = String(body.server || "").trim();
      const password = String(body.password || "");
      if (!login || !server || !password) {
        return res.status(400).json({ error: "login, password and server are required" });
      }
      const forwarded = await botRequest("/admin/accounts", {
        method: "POST",
        body: { ...body, login, server, password, source: body.source || "web" },
      });
      if (forwarded.ok) {
        return res.status(200).json({ ok: true, via: "bot", result: forwarded.data });
      }

      const existing = await supabaseAdmin
        .from("mt5_credentials")
        .select("id")
        .eq("login", login)
        .maybeSingle();
      const payload = {
        login,
        server,
        password,
        active: true,
        updated_at: new Date().toISOString(),
      };
      if (body.apiPort) payload.api_port = String(body.apiPort);
      if (existing.data?.id) {
        const { error } = await supabaseAdmin
          .from("mt5_credentials")
          .update(payload)
          .eq("id", existing.data.id);
        if (error) return res.status(500).json({ error: error.message });
      } else {
        const { error } = await supabaseAdmin
          .from("mt5_credentials")
          .insert({ ...payload, created_at: new Date().toISOString() });
        if (error) return res.status(500).json({ error: error.message });
      }
      return res.status(200).json({
        ok: true,
        via: "supabase",
        warning:
          forwarded.reason ||
          "Bot API unreachable: the account was stored in Supabase and is picked up when the bot restarts.",
      });
    }

    if (action === "sync") {
      const forwarded = await botRequest("/admin/accounts/sync", { method: "POST" });
      if (!forwarded.ok) {
        return res.status(502).json({ error: forwarded.reason || "Bot sync failed" });
      }
      return res.status(200).json({ ok: true, result: forwarded.data });
    }

    if (action === "enable") {
      const forwarded = await botRequest("/admin/accounts", {
        method: "POST",
        body: {
          login: String(body.login || "").trim(),
          server: body.server || "",
          password: body.password || "",
          enabled: true,
        },
      });
      if (!forwarded.ok) {
        return res.status(502).json({
          error:
            forwarded.reason ||
            "The bot must be running (with the account password) to re-enable a disabled login.",
        });
      }
      return res.status(200).json({ ok: true, result: forwarded.data });
    }

    if (action === "disable" || action === "delete") {
      const login = String(body.login || "").trim();
      if (!login) return res.status(400).json({ error: "login is required" });
      const hard = action === "delete" ? "?hard=true" : "";
      const forwarded = await botRequest(
        `/admin/accounts/${encodeURIComponent(login)}${hard}`,
        { method: "DELETE" },
      );
      if (action === "disable") {
        await supabaseAdmin.from("mt5_credentials").update({ active: false }).eq("login", login);
      } else {
        await supabaseAdmin.from("mt5_credentials").delete().eq("login", login);
      }
      if (!forwarded.ok) {
        return res.status(200).json({
          ok: true,
          via: "supabase",
          warning:
            forwarded.reason ||
            "Bot API unreachable: only the Supabase row changed, the local store keeps this login.",
        });
      }
      return res.status(200).json({ ok: true, via: "bot", result: forwarded.data });
    }

    return res.status(400).json({ error: "unknown action" });
  } catch (error) {
    return res.status(500).json({ error: error.message || String(error) });
  }
}

