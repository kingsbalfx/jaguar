import { createPagesServerClient } from "@supabase/auth-helpers-nextjs";
import { getSupabaseClient } from "../../../lib/supabaseClient";

function startOfToday() {
  const date = new Date();
  date.setHours(0, 0, 0, 0);
  return date;
}

function topPairs(rows, since = null) {
  const counts = new Map();
  for (const row of rows || []) {
    const deliveredAt = row.delivered_at ? new Date(row.delivered_at) : null;
    if (since && (!deliveredAt || deliveredAt < since)) continue;
    const symbol = row.bot_signals?.symbol || "UNKNOWN";
    counts.set(symbol, (counts.get(symbol) || 0) + 1);
  }
  return Array.from(counts.entries())
    .map(([symbol, count]) => ({ symbol, count }))
    .sort((a, b) => b.count - a.count || a.symbol.localeCompare(b.symbol))
    .slice(0, 10);
}

function buildSignalStats(deliveries = []) {
  const today = startOfToday();
  const week = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000);
  const todayRows = deliveries.filter((row) => row.delivered_at && new Date(row.delivered_at) >= today);
  const weekRows = deliveries.filter((row) => row.delivered_at && new Date(row.delivered_at) >= week);
  const signalIds = new Set(deliveries.map((row) => row.signal_id).filter(Boolean));
  const todaySignalIds = new Set(todayRows.map((row) => row.signal_id).filter(Boolean));
  const weekSignalIds = new Set(weekRows.map((row) => row.signal_id).filter(Boolean));
  const sentRows = deliveries.filter((row) => String(row.status || "").toLowerCase() === "sent");
  return {
    deliveredToday: todayRows.length,
    deliveredWeek: weekRows.length,
    deliveredTotal: deliveries.length,
    sentToday: todayRows.filter((row) => String(row.status || "").toLowerCase() === "sent").length,
    sentWeek: weekRows.filter((row) => String(row.status || "").toLowerCase() === "sent").length,
    sentTotal: sentRows.length,
    signalsToday: todaySignalIds.size,
    signalsWeek: weekSignalIds.size,
    signalsTotal: signalIds.size,
    topPairsToday: topPairs(deliveries, today),
    topPairsWeek: topPairs(deliveries, week),
    topPairsTotal: topPairs(deliveries),
  };
}

export default async function handler(req, res) {
  if (req.method !== "GET") return res.status(405).end();

  try {
    const supabase = createPagesServerClient({ req, res });
    const {
      data: { session },
    } = await supabase.auth.getSession();

    if (!session || !session.user) return res.status(401).json({ error: "not authenticated" });

    const supabaseAdmin = getSupabaseClient({ server: true });
    const userId = session.user.id;
    const { data: profile } = await supabaseAdmin.from("profiles").select("role").eq("id", userId).maybeSingle();
    const role = (profile?.role || "user").toLowerCase();
    if (role !== "admin") return res.status(403).json({ error: "forbidden" });

    const limit = Number(req.query.limit) || 100;
    let { data, error } = await supabaseAdmin
      .from("bot_logs")
      .select("*")
      .order("created_at", { ascending: false })
      .limit(limit);

    if (error) {
      const msg = String(error?.message || "").toLowerCase();
      if (msg.includes("created_at")) {
        const fallback = await supabaseAdmin.from("bot_logs").select("*").limit(limit);
        data = fallback.data;
        error = fallback.error;
      }
    }

    if (error) {
      const msg = String(error?.message || "").toLowerCase();
      if (msg.includes("event")) {
        const fallback = await supabaseAdmin.from("bot_logs").select("id,payload").limit(limit);
        data = fallback.data?.map((item) => ({
          ...item,
          event: item.payload?.message || "bot_log",
        }));
        error = fallback.error;
      }
    }

    if (error) {
      return res.status(500).json({ error: "failed to fetch logs" });
    }

    const signalLimit = Number(req.query.signalLimit) || 50;
    const { data: signals, error: signalsError } = await supabaseAdmin
      .from("bot_signals")
      .select("id,user_id,symbol,direction,entry_price,stop_loss,take_profit,signal_quality,confidence,status,created_at")
      .order("created_at", { ascending: false })
      .limit(signalLimit);

    const { data: deliveries, error: deliveriesError } = await supabaseAdmin
      .from("signal_deliveries")
      .select("id,signal_id,user_id,email,plan,status,delivered_at,bot_signals:signal_id(id,symbol,direction,status,created_at)")
      .order("delivered_at", { ascending: false })
      .limit(5000);

    return res.status(200).json({
      logs: data || [],
      signals: signalsError ? [] : signals || [],
      signalsError: signalsError?.message || null,
      signalStats: deliveriesError ? null : buildSignalStats(deliveries || []),
      signalStatsError: deliveriesError?.message || null,
    });
  } catch (e) {
    console.error(e);
    return res.status(500).json({ error: e.message || String(e) });
  }
}
