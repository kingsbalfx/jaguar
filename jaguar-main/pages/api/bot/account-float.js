import { createPagesServerClient } from "@supabase/auth-helpers-nextjs";
import { getSupabaseClient } from "../../../lib/supabaseClient";

function latestByAccount(rows) {
  const byKey = new Map();
  for (const row of rows || []) {
    const payload = row.payload || {};
    const key =
      payload.bot_id ||
      payload.account_login ||
      payload.login ||
      row.id;
    if (!byKey.has(key)) {
      byKey.set(key, { id: row.id, created_at: row.created_at, ...payload });
    }
  }
  return Array.from(byKey.values());
}

async function getActivatedLogins(supabaseAdmin, userId) {
  const { data } = await supabaseAdmin
    .from("mt5_submissions")
    .select("login")
    .eq("user_id", userId)
    .eq("status", "activated");
  const logins = new Set((data || []).map((row) => String(row.login || "").trim()).filter(Boolean));

  try {
    const credentials = await supabaseAdmin
      .from("mt5_credentials")
      .select("login")
      .eq("user_id", userId);
    for (const row of credentials.data || []) {
      const login = String(row.login || "").trim();
      if (login) logins.add(login);
    }
  } catch {
    // Older schemas may not have mt5_credentials.user_id yet.
  }

  return logins;
}

export default async function handler(req, res) {
  if (req.method !== "GET") {
    return res.status(405).json({ error: "Method not allowed" });
  }

  const supabase = createPagesServerClient({ req, res });
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session?.user) {
    return res.status(401).json({ error: "not authenticated" });
  }

  const supabaseAdmin = getSupabaseClient({ server: true });
  if (!supabaseAdmin) {
    return res.status(500).json({ error: "Supabase admin client not configured" });
  }

  const { data: profile } = await supabaseAdmin
    .from("profiles")
    .select("role")
    .eq("id", session.user.id)
    .maybeSingle();

  const role = (profile?.role || "user").toLowerCase();
  const adminScope = role === "admin" && req.query.scope === "all";

  const { data, error } = await supabaseAdmin
    .from("bot_logs")
    .select("id,event,payload,created_at")
    .eq("event", "account_snapshot")
    .order("created_at", { ascending: false })
    .limit(adminScope ? 300 : 150);

  if (error) {
    return res.status(500).json({ error: error.message || "failed to load account snapshots" });
  }

  let accounts = latestByAccount(data || []);

  if (!adminScope) {
    const activatedLogins = await getActivatedLogins(supabaseAdmin, session.user.id);
    accounts = accounts.filter((account) => {
      const login = String(account.account_login || account.login || "").trim();
      return account.user_id === session.user.id || (login && activatedLogins.has(login));
    });
  }

  const totalFloatingProfit = accounts.reduce(
    (sum, account) => sum + Number(account.floating_profit || 0),
    0
  );
  const totalBalance = accounts.reduce((sum, account) => sum + Number(account.balance || 0), 0);
  const totalEquity = accounts.reduce((sum, account) => sum + Number(account.equity || 0), 0);

  return res.status(200).json({
    accounts,
    totals: {
      floatingProfit: Number(totalFloatingProfit.toFixed(2)),
      balance: Number(totalBalance.toFixed(2)),
      equity: Number(totalEquity.toFixed(2)),
      count: accounts.length,
    },
    scope: adminScope ? "all" : "own",
  });
}
