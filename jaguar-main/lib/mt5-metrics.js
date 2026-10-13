/**
 * MT5 trade metrics (pure functions, no network / no DB).
 *
 * Everything the trade-history table, the pair dashboard and the admin macro
 * overview need: pip maths, net PnL, per-symbol aggregation, platform roll-ups,
 * sorting, pagination and period helpers. Kept dependency-free so the same code
 * runs in API routes, the sync service and scripts/verify-mt5-sync.js.
 */

export function toNumber(value, fallback = 0) {
  if (value === null || value === undefined || value === "") return fallback;
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : fallback;
}

export function round(value, digits = 2) {
  const numeric = toNumber(value, 0);
  const factor = 10 ** digits;
  return Math.round((numeric + Number.EPSILON) * factor) / factor;
}

/** Typical digit counts per instrument family (used when the bridge omits digits). */
const DIGITS_BY_KEYWORD = [
  ["XAU", 2],
  ["GOLD", 2],
  ["XAG", 3],
  ["SILVER", 3],
  ["XPT", 2],
  ["XPD", 2],
  ["BTC", 2],
  ["ETH", 2],
  ["US30", 1],
  ["US500", 1],
  ["SPX", 1],
  ["NAS", 1],
  ["GER", 1],
  ["UK100", 1],
  ["WTI", 2],
  ["BRENT", 2],
];

/** Infer the number of decimal digits for a symbol when the broker doesn't tell us. */
export function digitsForSymbol(symbol) {
  const upper = String(symbol || "").toUpperCase();
  if (!upper) return 2;
  if (/^[A-Z]{3}\/?JPY/.test(upper) || upper.endsWith("JPY")) return 3;
  for (const [keyword, digits] of DIGITS_BY_KEYWORD) {
    if (upper.includes(keyword)) return digits;
  }
  if (/^[A-Z]{6}$/.test(upper)) return 5;
  return 2;
}

/**
 * Price value of one pip for a symbol. One pip = 10 * point, so for a 5-digit
 * FX quote a pip is 0.0001 and for a 3-digit JPY quote it is 0.01.
 */
export function pipSizeForSymbol(symbol, digits) {
  const resolved = Number.isFinite(Number(digits)) && Number(digits) > 0 ? Number(digits) : digitsForSymbol(symbol);
  return Number((10 ** (1 - resolved)).toFixed(10));
}

/**
 * Signed pip result of a closed position.
 * @returns {number|null} null when prices are unusable (never a fabricated 0).
 */
export function computePips({ side, openPrice, closePrice, digits, symbol } = {}) {
  const open = toNumber(openPrice, NaN);
  const close = toNumber(closePrice, NaN);
  if (!Number.isFinite(open) || !Number.isFinite(close) || open <= 0 || close <= 0) return null;
  const pipSize = pipSizeForSymbol(symbol, digits);
  if (!pipSize) return null;
  const direction = String(side || "").toLowerCase() === "sell" ? -1 : 1;
  return round(((close - open) * direction) / pipSize, 2);
}

/**
 * Net PnL of a closed position: broker profit + commission + swap.
 * Some bridges report swap under `Storage`; it is only used when swap is absent
 * so the same money is never counted twice.
 */
export function computeNetPnl({ profit, commission, swap, storage } = {}) {
  const profitValue = toNumber(profit, 0);
  const commissionValue = toNumber(commission, 0);
  const hasSwap = swap !== undefined && swap !== null && swap !== "";
  const swapValue = hasSwap ? toNumber(swap, 0) : toNumber(storage, 0);
  return round(profitValue + commissionValue + swapValue, 2);
}

/** "2026-10" bucket key for a date. */
export function buildPeriod(date = new Date()) {
  const value = date instanceof Date ? date : new Date(date);
  if (Number.isNaN(value.getTime())) return buildPeriod(new Date());
  return `${value.getUTCFullYear()}-${String(value.getUTCMonth() + 1).padStart(2, "0")}`;
}

const MONTH_LABELS = [
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "May",
  "Jun",
  "Jul",
  "Aug",
  "Sep",
  "Oct",
  "Nov",
  "Dec",
];

/** "all" -> "All time", "2026-10" -> "Oct 2026". */
export function periodLabel(period) {
  const value = String(period || "all");
  if (value.toLowerCase() === "all") return "All time";
  const match = /^(\d{4})-(\d{2})$/.exec(value);
  if (!match) return value;
  const monthIndex = Number(match[2]) - 1;
  const month = MONTH_LABELS[monthIndex] || match[2];
  return `${month} ${match[1]}`;
}

/** ISO bounds for a period bucket ("all" has no bounds). */
export function periodBounds(period) {
  const value = String(period || "all");
  const match = /^(\d{4})-(\d{2})$/.exec(value);
  if (!match) return { start: null, end: null };
  const year = Number(match[1]);
  const monthIndex = Number(match[2]) - 1;
  const start = new Date(Date.UTC(year, monthIndex, 1, 0, 0, 0, 0));
  const end = new Date(Date.UTC(year, monthIndex + 1, 1, 0, 0, 0, 0));
  return { start: start.toISOString(), end: end.toISOString() };
}

/** Most recent period keys, newest first, including the current month. */
export function listRecentPeriods(count = 12, from = new Date()) {
  const base = from instanceof Date ? from : new Date(from);
  const periods = [];
  for (let index = 0; index < count; index += 1) {
    periods.push(buildPeriod(new Date(Date.UTC(base.getUTCFullYear(), base.getUTCMonth() - index, 1))));
  }
  return periods;
}

/** Normalise an incoming period filter ("all", "2026-10", "" -> "all"). */
export function normalizePeriodFilter(period) {
  const value = String(period || "all").trim();
  if (!value || value.toLowerCase() === "all") return "all";
  return /^\d{4}-\d{2}$/.test(value) ? value : "all";
}

/** Aggregate a list of closed trades into the headline performance block. */
export function aggregateTrades(trades = []) {
  const list = (trades || []).filter(Boolean);
  let wins = 0;
  let losses = 0;
  let breakeven = 0;
  let volume = 0;
  let grossProfit = 0;
  let grossLoss = 0;
  let netPnl = 0;
  let commission = 0;
  let swap = 0;
  let pips = 0;
  let pipsTrades = 0;
  let bestTrade = 0;
  let worstTrade = 0;
  let firstTradeAt = null;
  let lastTradeAt = null;

  for (const trade of list) {
    const net = toNumber(trade.net_pnl ?? trade.netPnl, 0);
    netPnl += net;
    if (net > 0) {
      wins += 1;
      grossProfit += net;
    } else if (net < 0) {
      losses += 1;
      grossLoss += Math.abs(net);
    } else {
      breakeven += 1;
    }
    volume += toNumber(trade.volume, 0);
    commission += toNumber(trade.commission, 0);
    const hasSwap = trade.swap !== undefined && trade.swap !== null && trade.swap !== "";
    swap += hasSwap ? toNumber(trade.swap, 0) : toNumber(trade.storage, 0);

    const pipsValue = trade.pips;
    if (pipsValue !== null && pipsValue !== undefined && Number.isFinite(Number(pipsValue))) {
      pips += Number(pipsValue);
      pipsTrades += 1;
    }
    if (net > bestTrade) bestTrade = net;
    if (net < worstTrade) worstTrade = net;

    const closeTime = trade.close_time || trade.closeTime;
    if (closeTime) {
      const closeMs = new Date(closeTime).getTime();
      if (Number.isFinite(closeMs)) {
        if (!firstTradeAt || closeMs < new Date(firstTradeAt).getTime()) firstTradeAt = closeTime;
        if (!lastTradeAt || closeMs > new Date(lastTradeAt).getTime()) lastTradeAt = closeTime;
      }
    }
  }

  const decided = wins + losses;
  return {
    trades: list.length,
    wins,
    losses,
    breakeven,
    volume: round(volume, 4),
    grossProfit: round(grossProfit),
    grossLoss: round(grossLoss),
    netPnl: round(netPnl),
    commission: round(commission),
    swap: round(swap),
    profitFactor: grossLoss > 0 ? round(grossProfit / grossLoss, 4) : grossProfit > 0 ? null : 0,
    winRate: list.length ? round((wins / list.length) * 100) : 0,
    winRateOfDecided: decided ? round((wins / decided) * 100) : 0,
    avgWin: wins ? round(grossProfit / wins) : 0,
    avgLoss: losses ? round(grossLoss / losses) : 0,
    avgTrade: list.length ? round(netPnl / list.length) : 0,
    bestTrade: round(bestTrade),
    worstTrade: round(worstTrade),
    pips: round(pips),
    pipsTrades,
    firstTradeAt,
    lastTradeAt,
  };
}

/**
 * Per-symbol performance breakdown.
 * @returns {Array<object>} newest-first by net PnL, each row carrying sharePct.
 */
export function computePairMetrics(trades = []) {
  const list = (trades || []).filter(Boolean);
  const groups = new Map();
  for (const trade of list) {
    const symbol = String(trade.symbol || "UNKNOWN").toUpperCase();
    if (!groups.has(symbol)) groups.set(symbol, []);
    groups.get(symbol).push(trade);
  }

  const totalTrades = list.length;
  const totalNet = list.reduce((sum, trade) => sum + toNumber(trade.net_pnl ?? trade.netPnl, 0), 0);

  return Array.from(groups.entries())
    .map(([symbol, symbolTrades]) => {
      const stats = aggregateTrades(symbolTrades);
      return {
        symbol,
        ...stats,
        sharePct: totalTrades ? round((stats.trades / totalTrades) * 100) : 0,
        netContributionPct: totalNet !== 0 ? round((stats.netPnl / Math.abs(totalNet)) * 100) : 0,
      };
    })
    .sort((left, right) => {
      if (right.netPnl !== left.netPnl) return right.netPnl - left.netPnl;
      return right.trades - left.trades;
    });
}

/** Stored row shape for public.pair_analytics. */
export function buildPairAnalyticsRows({ trades = [], link = {}, period = "all" } = {}) {
  const rows = computePairMetrics(trades);
  const breakouts = new Map();
  for (const trade of trades || []) {
    const symbol = String(trade.symbol || "UNKNOWN").toUpperCase();
    if (!breakouts.has(symbol)) breakouts.set(symbol, { TP: 0, SL: 0, MANUAL: 0, EA: 0, STOP_OUT: 0, OTHER: 0 });
    const bucket = breakouts.get(symbol);
    const reason = String(trade.exit_reason || "OTHER").toUpperCase();
    if (bucket[reason] === undefined) bucket.OTHER += 1;
    else bucket[reason] += 1;
  }

  return rows.map((row) => {
    const breakout = breakouts.get(row.symbol) || { TP: 0, SL: 0, MANUAL: 0, EA: 0, STOP_OUT: 0, OTHER: 0 };
    return {
      link_id: link.id || link.linkId || null,
      user_id: link.user_id || link.userId || null,
      account_login: String(link.login || link.account_login || link.accountLogin || "") || null,
      period: String(period || "all"),
      symbol: row.symbol,
      trades: row.trades,
      wins: row.wins,
      losses: row.losses,
      breakeven: row.breakeven,
      win_rate: row.winRate,
      volume: row.volume,
      gross_profit: row.grossProfit,
      gross_loss: row.grossLoss,
      net_pnl: row.netPnl,
      profit_factor: row.profitFactor,
      pips: row.pips,
      avg_win: row.avgWin,
      avg_loss: row.avgLoss,
      best_trade: row.bestTrade,
      worst_trade: row.worstTrade,
      tp_trades: breakout.TP,
      sl_trades: breakout.SL,
      manual_trades: breakout.MANUAL,
      ea_trades: breakout.EA,
      stop_out_trades: breakout.STOP_OUT,
      other_trades: breakout.OTHER,
      first_trade_at: row.firstTradeAt,
      last_trade_at: row.lastTradeAt,
      updated_at: new Date().toISOString(),
    };
  });
}

/**
 * Platform-wide roll-up for the admin macro overview.
 * @param {{trades?:Array<object>, links?:Array<object>}} payload
 */
export function aggregateMacroPerformance({ trades = [], links = [] } = {}) {
  const list = (trades || []).filter(Boolean);
  const totals = aggregateTrades(list);
  const pairMetrics = computePairMetrics(list);

  const byUser = new Map();
  for (const trade of list) {
    const key = String(trade.user_id || trade.userId || trade.account_login || "unknown");
    if (!byUser.has(key)) {
      byUser.set(key, {
        userId: key,
        accountLogin: trade.account_login || null,
        email: trade.email || null,
        trades: [],
      });
    }
    byUser.get(key).trades.push(trade);
  }

  const accounts = Array.from(byUser.values())
    .map((entry) => ({
      userId: entry.userId,
      accountLogin: entry.accountLogin,
      email: entry.email,
      ...aggregateTrades(entry.trades),
    }))
    .sort((left, right) => right.netPnl - left.netPnl);

  return {
    totals,
    accounts,
    pairs: pairMetrics,
    activeAccounts: accounts.filter((account) => account.trades > 0).length,
    linkedAccounts: (links || []).length,
    topPair: pairMetrics[0] || null,
    worstPair: pairMetrics.length ? pairMetrics[pairMetrics.length - 1] : null,
  };
}

const SORT_FIELDS = {
  close_time: "close_time",
  closeTime: "close_time",
  symbol: "symbol",
  volume: "volume",
  pips: "pips",
  net_pnl: "net_pnl",
  netPnl: "net_pnl",
  profit: "profit",
  open_time: "open_time",
  openTime: "open_time",
  exit_reason: "exit_reason",
  exitReason: "exit_reason",
};

/** Whitelisted sorting so query params can never inject raw SQL-ish column names. */
export function sortTrades(trades = [], { sortBy = "close_time", direction = "desc" } = {}) {
  const field = SORT_FIELDS[sortBy] || SORT_FIELDS.close_time;
  const sign = String(direction || "desc").toLowerCase() === "asc" ? 1 : -1;
  return [...(trades || [])].sort((left, right) => {
    const leftValue = left?.[field];
    const rightValue = right?.[field];
    if (field === "close_time" || field === "open_time") {
      const leftMs = new Date(leftValue || 0).getTime() || 0;
      const rightMs = new Date(rightValue || 0).getTime() || 0;
      return (leftMs - rightMs) * sign;
    }
    if (field === "symbol" || field === "exit_reason") {
      return String(leftValue || "").localeCompare(String(rightValue || "")) * sign;
    }
    return (toNumber(leftValue, 0) - toNumber(rightValue, 0)) * sign;
  });
}

/** Page a list with 1-based page numbers. */
export function paginate(items = [], { page = 1, pageSize = 25 } = {}) {
  const safeSize = Math.max(1, Math.min(Number(pageSize) || 25, 200));
  const total = (items || []).length;
  const totalPages = total ? Math.ceil(total / safeSize) : 0;
  const safePage = totalPages ? Math.min(Math.max(Number(page) || 1, 1), totalPages) : 1;
  const start = (safePage - 1) * safeSize;
  return {
    items: (items || []).slice(start, start + safeSize),
    page: safePage,
    pageSize: safeSize,
    total,
    totalPages,
    hasMore: safePage < totalPages,
  };
}


