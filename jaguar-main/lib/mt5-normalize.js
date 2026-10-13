/**
 * Provider-agnostic MT5 deal normalisation.
 *
 * Cloud bridges describe the same MT5 deal with slightly different keys:
 *   MetaApi : { id, positionId, type: "DEAL_TYPE_BUY", entryType: "DEAL_ENTRY_IN",
 *               time: "2026-10-01T10:00:00.000Z", symbol, magic, volume, price,
 *               commission, swap, profit, comment, brokerComment, reason }
 *   WebAPI  : { Deal, PositionID, Action: 0, Entry: 1, Time: 1759312800, Symbol,
 *               Volume, Price, Commission, Storage, Profit, ExpertID, Comment }
 *
 * Instead of pinning a single shape we read a superset of aliases, so switching
 * bridges (MetaApi <-> MT5 WebAPI <-> relay) never requires touching the
 * aggregation code. Every reader returns null when the bridge omits the field -
 * values are never invented.
 */
import { classifyExitReason, readComment, readMagic, readReasonCode } from "./mt5-exit-reason.js";
import { buildPeriod, computeNetPnl, computePips, digitsForSymbol, round, toNumber } from "./mt5-metrics.js";

function firstPresent(source, keys) {
  for (const key of keys) {
    const value = source?.[key];
    if (value !== undefined && value !== null && String(value).trim() !== "") return value;
  }
  return null;
}

function toIso(value) {
  if (value === null || value === undefined || value === "") return null;
  if (value instanceof Date) return Number.isNaN(value.getTime()) ? null : value.toISOString();
  const numeric = typeof value === "number" ? value : /^\d+$/.test(String(value).trim()) ? Number(value) : null;
  if (numeric !== null) {
    // MT5 WebAPI emits unix seconds; MetaApi/JS emit milliseconds.
    const ms = numeric < 1e12 ? numeric * 1000 : numeric;
    const date = new Date(ms);
    return Number.isNaN(date.getTime()) ? null : date.toISOString();
  }
  const date = new Date(String(value));
  return Number.isNaN(date.getTime()) ? null : date.toISOString();
}

export function readDealTicket(deal = {}) {
  const raw = firstPresent(deal, ["ticket", "id", "Deal", "dealTicket"]);
  return raw === null ? null : String(raw);
}

export function readPositionId(deal = {}) {
  const raw = firstPresent(deal, ["positionId", "PositionID", "position_id", "position", "Position"]);
  return raw === null ? null : String(raw);
}

export function readSymbol(deal = {}) {
  const raw = firstPresent(deal, ["symbol", "Symbol", "instrument"]);
  return raw === null ? null : String(raw).toUpperCase();
}

/** 0 = buy, 1 = sell (MT5 ENUM_DEAL_TYPE) or null when unknown. */
export function readDealTypeNumber(deal = {}) {
  const raw = firstPresent(deal, ["type", "Type", "action", "Action", "dealType", "DealType"]);
  if (raw === null) return null;
  if (typeof raw === "string" && /[a-z]/i.test(raw)) {
    const text = raw.toUpperCase();
    if (text.includes("SELL")) return 1;
    if (text.includes("BUY")) return 0;
    return null;
  }
  const numeric = Number(raw);
  return numeric === 0 || numeric === 1 ? numeric : null;
}

export function readSide(deal = {}) {
  const type = readDealTypeNumber(deal);
  if (type === null) return null;
  return type === 0 ? "buy" : "sell";
}

/** MT5 ENUM_DEAL_ENTRY. Note INOUT must be tested before IN. */
export function readEntryType(deal = {}) {
  const raw = firstPresent(deal, ["entryType", "EntryType", "entry", "Entry"]);
  if (raw === null) return null;
  if (typeof raw === "string" && /[a-z]/i.test(raw)) {
    const text = raw.toUpperCase();
    if (text.includes("INOUT")) return "inout";
    if (text.includes("OUT_BY") || text.includes("OUTBY")) return "out_by";
    if (text.includes("OUT")) return "out";
    if (text.includes("STATE")) return "state";
    if (text.includes("IN")) return "in";
    return null;
  }
  const numeric = Number(raw);
  if (numeric === 0) return "in";
  if (numeric === 1) return "out";
  if (numeric === 2) return "inout";
  if (numeric === 3) return "out_by";
  if (numeric === 4) return "state";
  return null;
}

export function readDealTime(deal = {}) {
  return toIso(firstPresent(deal, ["time", "Time", "brokerTime", "BrokerTime"]));
}

export function readDigits(deal = {}) {
  const raw = firstPresent(deal, ["digits", "Digits"]);
  const numeric = Number(raw);
  return Number.isFinite(numeric) && numeric >= 0 ? numeric : null;
}

function readNumericField(deal, keys) {
  const raw = firstPresent(deal, keys);
  if (raw === null) return null;
  const numeric = Number(raw);
  return Number.isFinite(numeric) ? numeric : null;
}

export function readVolume(deal = {}) {
  return readNumericField(deal, ["volume", "Volume", "volumeClosed", "VolumeClosed"]);
}

export function readPrice(deal = {}) {
  return readNumericField(deal, ["price", "Price"]);
}

export function readProfit(deal = {}) {
  return readNumericField(deal, ["profit", "Profit", "profitRaw"]);
}

export function readCommission(deal = {}) {
  return readNumericField(deal, ["commission", "Commission"]);
}

export function readSwap(deal = {}) {
  return readNumericField(deal, ["swap", "Swap", "storage", "Storage"]);
}

export function readStorage(deal = {}) {
  return readNumericField(deal, ["storage", "Storage"]);
}

/** Prose comment only - MT5 WebAPI returns a numeric comment enum that we ignore. */
export function readPlainComment(deal = {}) {
  const raw = firstPresent(deal, ["comment", "Comment"]);
  if (raw === null || typeof raw === "number") return null;
  const text = String(raw).trim();
  return text || null;
}

export function readBrokerComment(deal = {}) {
  const raw = firstPresent(deal, ["brokerComment", "BrokerComment"]);
  if (raw === null || typeof raw === "number") return null;
  const text = String(raw).trim();
  return text || null;
}

/** Flatten any bridge deal payload into the canonical deal shape. */
export function normalizeDeal(deal = {}, { source = "metaapi" } = {}) {
  return {
    ticket: readDealTicket(deal),
    positionId: readPositionId(deal),
    symbol: readSymbol(deal),
    side: readSide(deal),
    typeNumber: readDealTypeNumber(deal),
    entryType: readEntryType(deal),
    time: readDealTime(deal),
    digits: readDigits(deal),
    volume: readVolume(deal),
    price: readPrice(deal),
    profit: readProfit(deal),
    commission: readCommission(deal),
    swap: readSwap(deal),
    storage: readStorage(deal),
    magic: readMagic(deal),
    comment: readPlainComment(deal),
    brokerComment: readBrokerComment(deal),
    reasonCode: readReasonCode(deal),
    reasonText: readComment(deal),
    source,
    raw: deal,
  };
}

const CLOSE_ENTRY_TYPES = ["out", "out_by"];
const OPEN_ENTRY_TYPES = ["in", "inout"];

function invertSide(side) {
  if (side === "buy") return "sell";
  if (side === "sell") return "buy";
  return null;
}

function timeValue(deal) {
  return deal?.time ? new Date(deal.time).getTime() : Number.MAX_SAFE_INTEGER;
}

function toMillis(value) {
  const ms = value ? new Date(value).getTime() : NaN;
  return Number.isFinite(ms) ? ms : null;
}

/** Ascending broker time (deals without a timestamp sink to the end). */
export function sortDealsByTime(deals = []) {
  return [...deals].sort((left, right) => timeValue(left) - timeValue(right));
}

/** Stable de-dupe key for a position: broker position id, else the deal ticket. */
export function positionKeyFor(deal) {
  if (deal?.positionId) return `position:${deal.positionId}`;
  if (deal?.ticket) return `deal:${deal.ticket}`;
  return null;
}

/** True when the payload already passed through normalizeDeal(). */
function isNormalizedDeal(deal) {
  return Boolean(deal) && deal.raw !== undefined && deal.entryType !== undefined && deal.ticket !== undefined;
}

/**
 * Normalise + group raw bridge deals by position.
 * @returns {Array<{ key: string, positionId: string|null, deals: Array<object> }>}
 */
export function groupDealsByPosition(deals = [], { source = "metaapi" } = {}) {
  const groups = new Map();
  for (const raw of deals || []) {
    const deal = isNormalizedDeal(raw) ? raw : normalizeDeal(raw, { source });
    if (!deal?.ticket || !deal.symbol) continue;
    const key = positionKeyFor(deal);
    if (!key) continue;
    if (!groups.has(key)) groups.set(key, { key, positionId: deal.positionId || null, deals: [] });
    const group = groups.get(key);
    if (!group.positionId && deal.positionId) group.positionId = deal.positionId;
    if (!group.deals.some((existing) => existing.ticket === deal.ticket)) group.deals.push(deal);
  }
  return Array.from(groups.values()).map((group) => ({ ...group, deals: sortDealsByTime(group.deals) }));
}

/**
 * MT5 emits separate IN and OUT deals for the same position; trade_history stores
 * one row per CLOSED POSITION. Positions that are still open (no OUT deal in the
 * fetched window) are intentionally skipped - the live floating panel covers them.
 *
 * @returns {Array<object>} closed positions, newest close first
 */
export function pairDealsIntoPositions(deals = [], { source = "metaapi" } = {}) {
  const positions = [];
  for (const group of groupDealsByPosition(deals, { source })) {
    const position = buildPositionFromGroup(group, { source });
    if (position) positions.push(position);
  }
  return positions.sort((left, right) => (toMillis(right.closeTime) || 0) - (toMillis(left.closeTime) || 0));
}

/**
 * Collapse one position group into a closed-position record.
 * @returns {object|null} null when the position is still open or cannot be placed on a timeline
 */
export function buildPositionFromGroup(group, { source = "metaapi" } = {}) {
  const deals = sortDealsByTime(group?.deals || []);
  if (!deals.length) return null;

  const openDeals = deals.filter((deal) => OPEN_ENTRY_TYPES.includes(deal.entryType));
  const closeEntries = deals.filter((deal) => CLOSE_ENTRY_TYPES.includes(deal.entryType));
  const openDeal = openDeals.length ? openDeals[0] : null;
  // An INOUT deal closes the previous position and opens this one; its money
  // belongs to the PREVIOUS position, so it must not be counted twice.
  const reversalOpen = openDeal && openDeal.entryType === "inout" ? openDeal : null;
  const closingDeals = closeEntries.length ? closeEntries : openDeals.filter((deal) => deal !== openDeal);
  if (!closingDeals.length) return null; // still open

  const lastClose = closingDeals[closingDeals.length - 1];
  const moneyDeals = deals.filter((deal) => deal !== reversalOpen);

  const closeVolumes = closingDeals.map((deal) => toNumber(deal.volume, 0)).filter((value) => value > 0);
  const closeVolume = closeVolumes.reduce((sum, value) => sum + value, 0);
  const openVolume = toNumber(openDeal?.volume, 0);
  const volume = closeVolume > 0 ? closeVolume : openVolume;

  const pricedCloses = closingDeals.filter((deal) => Number.isFinite(Number(deal.price)));
  let closePrice = null;
  if (pricedCloses.length) {
    const weighted = pricedCloses.reduce((sum, deal) => sum + Number(deal.price) * Math.max(toNumber(deal.volume, 0), 0), 0);
    const weightSum = pricedCloses.reduce((sum, deal) => sum + Math.max(toNumber(deal.volume, 0), 0), 0);
    closePrice = weightSum > 0 ? round(weighted / weightSum, 8) : round(Number(pricedCloses[pricedCloses.length - 1].price), 8);
  }
  const openPrice = Number.isFinite(Number(openDeal?.price)) ? round(Number(openDeal.price), 8) : null;

  const profit = round(moneyDeals.reduce((sum, deal) => sum + toNumber(deal.profit, 0), 0));
  const commission = round(moneyDeals.reduce((sum, deal) => sum + toNumber(deal.commission, 0), 0));
  const swap = round(moneyDeals.reduce((sum, deal) => sum + toNumber(deal.swap, 0), 0));
  const storage = round(moneyDeals.reduce((sum, deal) => sum + toNumber(deal.storage, 0), 0));

  const digits = lastClose.digits ?? openDeal?.digits ?? null;
  const symbol = lastClose.symbol || openDeal?.symbol || null;
  if (!symbol) return null;

  const openTime = openDeal?.time || deals[0]?.time || null;
  const closeTime = lastClose.time || openTime;
  if (!closeTime) return null;

  const openMs = toMillis(openTime);
  const closeMs = toMillis(closeTime);
  const durationSeconds = openMs !== null && closeMs !== null && closeMs >= openMs ? Math.round((closeMs - openMs) / 1000) : null;

  // The open deal carries the position direction; a position closed with a SELL
  // deal was long, so the closing deal's type is inverted when the open is missing.
  const side = openDeal?.side || invertSide(lastClose.side);
  if (!side) return null;

  const magic = openDeal?.magic ?? lastClose.magic ?? null;
  const exit = classifyExitReason(lastClose.raw || lastClose, { magic });

  return {
    dedupeKey: group.positionId ? `position:${group.positionId}` : String(lastClose.ticket),
    positionId: group.positionId || null,
    openTicket: openDeal?.ticket || null,
    closeTicket: lastClose.ticket || null,
    symbol,
    side,
    volume: round(volume, 4),
    openPrice,
    closePrice,
    openTime,
    closeTime,
    durationSeconds,
    digits,
    pips: computePips({ side, openPrice, closePrice, digits: digits ?? digitsForSymbol(symbol), symbol }),
    profit,
    commission,
    swap,
    storage,
    netPnl: computeNetPnl({ profit, commission, swap, storage }),
    exitReason: exit.reason,
    exitSource: exit.source,
    magic: Number.isFinite(Number(magic)) ? Math.trunc(Number(magic)) : null,
    comment: lastClose.comment || openDeal?.comment || null,
    brokerComment: lastClose.brokerComment || openDeal?.brokerComment || null,
    source,
    raw: {
      open: openDeal?.raw ?? null,
      close: closingDeals.map((deal) => deal.raw ?? null),
    },
  };
}

/** Map a paired position onto the public.trade_history row shape. */
export function positionToTradeRow(position, { link = {}, source = "metaapi" } = {}) {
  if (!position) return null;
  return {
    link_id: link.id || link.linkId || null,
    user_id: link.user_id || link.userId || null,
    account_login: String(link.login || link.account_login || link.accountLogin || ""),
    server: link.server || null,
    position_id: position.positionId,
    deal_ticket: position.dedupeKey,
    open_ticket: position.openTicket,
    symbol: position.symbol,
    side: position.side,
    volume: position.volume,
    open_price: position.openPrice,
    close_price: position.closePrice,
    open_time: position.openTime,
    close_time: position.closeTime,
    duration_seconds: position.durationSeconds,
    pips: position.pips,
    profit: position.profit,
    commission: position.commission,
    swap: position.swap,
    storage: position.storage,
    net_pnl: position.netPnl,
    exit_reason: position.exitReason,
    exit_source: position.exitSource,
    magic: position.magic,
    comment: position.comment,
    broker_comment: position.brokerComment,
    source: position.source || source,
    period: buildPeriod(new Date(position.closeTime)),
    raw: position.raw,
    updated_at: new Date().toISOString(),
  };
}

/** Pair raw bridge deals and map them straight to trade_history rows. */
export function toTradeRows(deals = [], { link = {}, source = "metaapi" } = {}) {
  return pairDealsIntoPositions(deals, { source })
    .map((position) => positionToTradeRow(position, { link, source }))
    .filter(Boolean);
}

/** De-dupe rows by (link, deal_ticket), keeping the latest close for each key. */
export function dedupeTradeRows(rows = []) {
  const byKey = new Map();
  for (const row of rows || []) {
    if (!row?.deal_ticket) continue;
    const key = `${row.link_id || ""}:${row.deal_ticket}`;
    const existing = byKey.get(key);
    if (!existing || (toMillis(row.close_time) || 0) >= (toMillis(existing.close_time) || 0)) {
      byKey.set(key, row);
    }
  }
  return Array.from(byKey.values());
}




