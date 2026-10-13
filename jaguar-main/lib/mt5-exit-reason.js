/**
 * MT5 exit-reason classification (pure functions, no network / no DB).
 *
 * MT5 tags every deal with ENUM_DEAL_REASON (deal.reason). Cloud bridges forward
 * it under different keys depending on the bridge:
 *   - MetaApi            -> `reason` (numeric) on the deal object
 *   - MT5 WebAPI relay   -> `Reason`
 *   - generic REST relay -> `reason` / `reasonCode` / `closeReason`
 * Some bridges only forward the raw comment, so we classify in order of trust:
 *   1. numeric reason code (authoritative, MT5 ENUM_DEAL_REASON)
 *   2. textual reason label ("DEAL_REASON_SL", "expert", "SL")
 *   3. comment heuristics ("[sl 1.23456]", "tp 1.23", "so: 1.23", "closed by user")
 *   4. attribute heuristic (magic != 0 => expert advisor / bot)
 *
 * Nothing is invented: when a bridge returns only a numeric MT5 comment code
 * (which is a comment enum, not an exit reason) the result stays OTHER unless
 * the magic-number heuristic can attribute the trade to an EA.
 */

export const EXIT_REASON = {
  SL: "SL",
  TP: "TP",
  MANUAL: "MANUAL",
  EA: "EA",
  STOP_OUT: "STOP_OUT",
  ROLLOVER: "ROLLOVER",
  OTHER: "OTHER",
};

export const EXIT_REASON_LABELS = {
  SL: "Stop Loss",
  TP: "Take Profit",
  MANUAL: "Manual / User",
  EA: "Expert Advisor (EA)",
  STOP_OUT: "Stop Out / Margin Call",
  ROLLOVER: "Rollover",
  OTHER: "Other / Unknown",
};

export const EXIT_REASON_ORDER = ["TP", "SL", "MANUAL", "EA", "STOP_OUT", "ROLLOVER", "OTHER"];

/** MT5 ENUM_DEAL_REASON -> canonical reason. */
const NUMERIC_REASON_MAP = {
  0: EXIT_REASON.MANUAL, // DEAL_REASON_CLIENT
  1: EXIT_REASON.MANUAL, // DEAL_REASON_MOBILE
  2: EXIT_REASON.MANUAL, // DEAL_REASON_WEB
  3: EXIT_REASON.EA, // DEAL_REASON_EXPERT
  4: EXIT_REASON.SL, // DEAL_REASON_SL
  5: EXIT_REASON.TP, // DEAL_REASON_TP
  6: EXIT_REASON.STOP_OUT, // DEAL_REASON_SO
  7: EXIT_REASON.ROLLOVER, // DEAL_REASON_ROLLOVER
  8: EXIT_REASON.STOP_OUT, // DEAL_REASON_VMARGIN (variation margin / margin call)
  9: EXIT_REASON.OTHER, // DEAL_REASON_SPLIT
};

/** Reason keys seen across bridges (checked in order, first match wins). */
const REASON_KEYS = ["reason", "Reason", "reasonCode", "closeReason", "dealReason", "exitReason"];

/** Textual reason labels ("DEAL_REASON_SL", "expert", "stop loss", ...). */
const TEXT_REASON_PATTERNS = [
  [/deal_reason_sl|^s\/?l$|stop[\s_-]?loss/i, EXIT_REASON.SL],
  [/deal_reason_tp|^t\/?p$|take[\s_-]?profit/i, EXIT_REASON.TP],
  [/deal_reason_so|^so$|stop[\s_-]?out|margin[\s_-]?call|vmargin/i, EXIT_REASON.STOP_OUT],
  [/deal_reason_rollover|rollover/i, EXIT_REASON.ROLLOVER],
  [/deal_reason_expert|^expert$|^ea$|expert[\s_-]?advisor|^bot$/i, EXIT_REASON.EA],
  [
    /deal_reason_client|deal_reason_mobile|deal_reason_web|^client$|^manual$|^user$|^web$|^mobile$/i,
    EXIT_REASON.MANUAL,
  ],
  [/deal_reason_split|^split$/i, EXIT_REASON.OTHER],
];

/** Comment heuristics - MT5/broker close comments such as "[sl 1.23456]". */
const COMMENT_PATTERNS = [
  [/stop\s*out|margin\s*call|\bso\s*[:>]|\bso\b\s*\d/i, EXIT_REASON.STOP_OUT],
  [/\[sl\b|\bsl\s*[:>]\s*\d|\bsl\s+\d/i, EXIT_REASON.SL],
  [/\[tp\b|\btp\s*[:>]\s*\d|\btp\s+\d/i, EXIT_REASON.TP],
  [/\bs\/l\b|\bt\/p\b/i, EXIT_REASON.SL],
  [/rollover|swap\s*charge/i, EXIT_REASON.ROLLOVER],
  [/\bea\b|expert|automated|algorithm/i, EXIT_REASON.EA],
  [/manual|closed?\s+by\s+(user|client)|\buser\b|\btrader\b|\bmobile\b|\bweb\b/i, EXIT_REASON.MANUAL],
];

function readFirstPresent(source, keys) {
  for (const key of keys) {
    const value = source?.[key];
    if (value !== undefined && value !== null && String(value).trim() !== "") return value;
  }
  return null;
}

/**
 * Extract the raw numeric MT5 reason code from a deal/bridge payload.
 * @returns {number|null}
 */
export function readReasonCode(deal = {}) {
  const raw = readFirstPresent(deal, REASON_KEYS);
  if (raw === null) return null;
  const numeric = Number(raw);
  if (Number.isInteger(numeric) && numeric >= 0 && numeric <= 255) return numeric;
  return null;
}

/**
 * Extract the raw reason text when the bridge sends a label instead of a code.
 * @returns {string|null}
 */
export function readReasonText(deal = {}) {
  const raw = readFirstPresent(deal, REASON_KEYS);
  if (raw === null) return null;
  if (typeof raw === "number") return null;
  if (readReasonCode(deal) !== null) return null;
  const text = String(raw).trim();
  return text || null;
}

/** Read a human comment from either the MetaApi-style or MT5-WebAPI-style payload. */
export function readComment(deal = {}) {
  const raw = readFirstPresent(deal, ["comment", "Comment", "brokerComment", "BrokerComment"]);
  if (raw === null) return "";
  // MT5 WebAPI returns the comment as a numeric comment-enum, not prose.
  if (typeof raw === "number") return "";
  return String(raw).trim();
}

/** Read the deal magic number (EA id) from any bridge payload. */
export function readMagic(deal = {}) {
  const raw = readFirstPresent(deal, ["magic", "Magic", "expertId", "ExpertID", "ExpertId"]);
  if (raw === null) return null;
  const numeric = Number(raw);
  return Number.isFinite(numeric) ? Math.trunc(numeric) : null;
}

function buildResult(reason, source, reasonCode, detail) {
  return {
    reason,
    label: EXIT_REASON_LABELS[reason] || EXIT_REASON_LABELS.OTHER,
    source,
    reasonCode: reasonCode === undefined ? null : reasonCode,
    detail: detail || null,
  };
}

/**
 * Classify why a position was closed.
 *
 * @param {object} deal closing deal (or a flattened position row)
 * @param {object} [options]
 * @param {number} [options.magic] override the magic number used for the EA heuristic
 * @returns {{ reason: string, label: string, source: string, reasonCode: number|null, detail: string|null }}
 */
export function classifyExitReason(deal = {}, { magic } = {}) {
  const reasonCode = readReasonCode(deal);
  if (reasonCode !== null && NUMERIC_REASON_MAP[reasonCode]) {
    return buildResult(NUMERIC_REASON_MAP[reasonCode], "trade_reason", reasonCode, `ENUM_DEAL_REASON ${reasonCode}`);
  }

  const reasonText = readReasonText(deal);
  if (reasonText) {
    for (const [pattern, reason] of TEXT_REASON_PATTERNS) {
      if (pattern.test(reasonText)) return buildResult(reason, "label", reasonCode, reasonText);
    }
  }

  const comment = readComment(deal);
  if (comment) {
    for (const [pattern, reason] of COMMENT_PATTERNS) {
      if (pattern.test(comment)) return buildResult(reason, "comment", reasonCode, comment);
    }
  }

  const resolvedMagic = magic === undefined ? readMagic(deal) : magic;
  if (Number.isFinite(Number(resolvedMagic)) && Number(resolvedMagic) !== 0) {
    return buildResult(EXIT_REASON.EA, "heuristic", reasonCode, `magic ${resolvedMagic}`);
  }

  return buildResult(EXIT_REASON.OTHER, "unknown", reasonCode, comment || reasonText || null);
}

/** Turn raw fields into the canonical exit reason string only. */
export function exitReasonFor(deal = {}, options) {
  return classifyExitReason(deal, options).reason;
}

/** Human label for a stored exit reason value. */
export function exitReasonLabel(reason) {
  const key = String(reason || "").toUpperCase();
  return EXIT_REASON_LABELS[key] || EXIT_REASON_LABELS.OTHER;
}

/** Count trades per exit reason, preserving a stable display order. */
export function exitReasonBreakdown(trades = []) {
  const buckets = new Map(
    EXIT_REASON_ORDER.map((reason) => [
      reason,
      { reason, label: exitReasonLabel(reason), trades: 0, wins: 0, losses: 0, netPnl: 0, winRate: 0 },
    ]),
  );
  for (const trade of trades || []) {
    const key = String(trade.exit_reason || trade.exitReason || EXIT_REASON.OTHER).toUpperCase();
    const bucket = buckets.get(key) || buckets.get(EXIT_REASON.OTHER);
    const netPnl = Number(trade.net_pnl ?? trade.netPnl ?? 0) || 0;
    bucket.trades += 1;
    bucket.netPnl += netPnl;
    if (netPnl > 0) bucket.wins += 1;
    else if (netPnl < 0) bucket.losses += 1;
  }
  return Array.from(buckets.values())
    .filter((bucket) => bucket.trades > 0)
    .map((bucket) => ({
      ...bucket,
      netPnl: Number(bucket.netPnl.toFixed(2)),
      winRate: bucket.trades ? Number(((bucket.wins / bucket.trades) * 100).toFixed(2)) : 0,
    }));
}

