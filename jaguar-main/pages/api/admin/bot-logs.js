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

function topSignalPairs(rows, since = null) {
  const counts = new Map();
  for (const row of rows || []) {
    const createdAt = row.created_at ? new Date(row.created_at) : null;
    if (since && (!createdAt || createdAt < since)) continue;
    const symbol = row.symbol || "UNKNOWN";
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

function buildGeneratedSignalStats(signals = []) {
  const today = startOfToday();
  const week = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000);
  const todayRows = signals.filter((row) => row.created_at && new Date(row.created_at) >= today);
  const weekRows = signals.filter((row) => row.created_at && new Date(row.created_at) >= week);
  return {
    generatedToday: todayRows.length,
    generatedWeek: weekRows.length,
    generatedTotal: signals.length,
    topGeneratedPairsToday: topSignalPairs(signals, today),
    topGeneratedPairsWeek: topSignalPairs(signals, week),
    topGeneratedPairsTotal: topSignalPairs(signals),
  };
}

function normalizeStrategyName(value) {
  const raw = String(value || "").trim();
  if (!raw) return "Unknown";
  const labels = {
    ict_state_machine: "ICT 12-gate",
    kingsbalfx: "Kingsbalfx",
    fallback3: "Fallback 3",
    fallback4: "Fallback 4",
    fallback5: "Fallback 5",
    mirror_trade: "Mirror Trade",
  };
  const key = raw.toLowerCase();
  return labels[key] || raw.replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

function pickStrategy(payload = {}) {
  return normalizeStrategyName(
    payload.strategy ||
    payload.source_strategy ||
    payload.execution_route ||
    payload.state_machine?.strategy ||
    payload.setup?.strategy ||
    payload.raw?.strategy
  );
}

function classifyOutcome(log = {}) {
  const event = String(log.event || "").toLowerCase();
  const payload = log.payload || {};
  const reason = String(payload.outcome || payload.close_reason || payload.reason || payload.status || event).toLowerCase();
  const profit = Number(payload.profit ?? payload.pnl ?? payload.realized_profit ?? payload.net_profit);

  if (event === "trade_opened" || reason === "open") return "opened";
  if (/take[_\s-]?profit|\btp\b|target/.test(reason)) return "takeProfit";
  if (/stop[_\s-]?loss|\bsl\b|loss|stopped/.test(reason)) return "loss";
  if (/closed|close|exit|settled/.test(event) || /closed|close|exit|settled/.test(reason)) {
    if (Number.isFinite(profit)) return profit >= 0 ? "takeProfit" : "loss";
    return "closed";
  }
  return null;
}

function buildStrategyOutcomeStats(logs = []) {
  const byStrategy = new Map();
  const recent = [];

  for (const log of logs || []) {
    const outcome = classifyOutcome(log);
    if (!outcome) continue;
    const payload = log.payload || {};
    const strategy = pickStrategy(payload);
    const current = byStrategy.get(strategy) || {
      strategy,
      opened: 0,
      takeProfit: 0,
      loss: 0,
      closed: 0,
      totalClosed: 0,
      netPnl: 0,
    };

    current[outcome] = (current[outcome] || 0) + 1;
    if (outcome !== "opened") current.totalClosed += 1;
    const pnl = Number(payload.profit ?? payload.pnl ?? payload.realized_profit ?? payload.net_profit);
    if (Number.isFinite(pnl)) current.netPnl += pnl;
    byStrategy.set(strategy, current);

    recent.push({
      id: log.id || `${strategy}-${recent.length}`,
      strategy,
      outcome,
      symbol: payload.symbol || payload.raw?.symbol || "UNKNOWN",
      direction: payload.direction || payload.raw?.direction || "",
      pnl: Number.isFinite(pnl) ? pnl : null,
      created_at: log.created_at || null,
    });
  }

  const strategies = Array.from(byStrategy.values())
    .map((item) => ({
      ...item,
      winRate: item.totalClosed > 0 ? item.takeProfit / item.totalClosed : 0,
      netPnl: Number(item.netPnl.toFixed(2)),
    }))
    .sort((a, b) => (b.opened + b.totalClosed) - (a.opened + a.totalClosed) || a.strategy.localeCompare(b.strategy));

  return {
    strategies,
    totals: strategies.reduce((acc, item) => ({
      opened: acc.opened + item.opened,
      takeProfit: acc.takeProfit + item.takeProfit,
      loss: acc.loss + item.loss,
      closed: acc.closed + item.closed,
      totalClosed: acc.totalClosed + item.totalClosed,
      netPnl: Number((acc.netPnl + item.netPnl).toFixed(2)),
    }), { opened: 0, takeProfit: 0, loss: 0, closed: 0, totalClosed: 0, netPnl: 0 }),
    recent: recent.slice(-20).reverse(),
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
      .limit(Math.max(signalLimit, 1000));

    const { data: deliveries, error: deliveriesError } = await supabaseAdmin
      .from("signal_deliveries")
      .select("id,signal_id,user_id,email,plan,status,delivered_at,bot_signals:signal_id(id,symbol,direction,status,created_at)")
      .order("delivered_at", { ascending: false })
      .limit(5000);

    return res.status(200).json({
      logs: data || [],
      signals: signalsError ? [] : (signals || []).slice(0, signalLimit),
      signalsError: signalsError?.message || null,
      signalStats: deliveriesError ? null : buildSignalStats(deliveries || []),
      signalStatsError: deliveriesError?.message || null,
      generatedSignalStats: signalsError ? null : buildGeneratedSignalStats(signals || []),
      strategyOutcomeStats: buildStrategyOutcomeStats(data || []),
    });
  } catch (e) {
    console.error(e);
    return res.status(500).json({ error: e.message || String(e) });
  }
}
