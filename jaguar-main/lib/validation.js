/**
 * Input Validation & Sanitization Middleware
 * Ensures all inputs are safe and correct format
 */

export function validateEmail(email) {
  const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  if (!email || typeof email !== "string" || email.length > 254) return false;
  return re.test(email);
}

export function validateAmount(amount) {
  const num = Number(amount);
  return !isNaN(num) && num > 0 && num < 100000000; // Max 100M
}

export function validateSymbol(symbol) {
  if (!symbol || typeof symbol !== "string") return false;
  const clean = symbol.toUpperCase().trim();
  return /^[A-Z]{2,8}$/.test(clean);
}

export function validateDirection(dir) {
  return ["buy", "sell", "BUY", "SELL"].includes(dir);
}

export function validatePrice(price) {
  const num = Number(price);
  return !isNaN(num) && num > 0;
}

export function validateRole(role) {
  return ["admin", "user", "vip", "premium"].includes((role || "").toLowerCase());
}

export function sanitizeString(str, maxLen = 500) {
  if (typeof str !== "string") return "";
  return str.trim().substring(0, maxLen).replace(/[<>\"']/g, "");
}

export function validateTrade(trade) {
  if (!trade || typeof trade !== "object") return { valid: false, error: "Invalid trade object" };
  if (!validateSymbol(trade.symbol)) return { valid: false, error: "Invalid symbol" };
  if (!validateDirection(trade.direction)) return { valid: false, error: "Invalid direction" };
  if (!validatePrice(trade.entry)) return { valid: false, error: "Invalid entry price" };
  if (!validatePrice(trade.sl)) return { valid: false, error: "Invalid SL price" };
  if (!validatePrice(trade.tp)) return { valid: false, error: "Invalid TP price" };
  if (trade.lot && (Number(trade.lot) <= 0 || Number(trade.lot) > 100)) return { valid: false, error: "Invalid lot size" };
  return { valid: true };
}

export function validatePaystackInit(data) {
  if (!data || typeof data !== "object") return { valid: false, error: "Invalid request" };
  if (!validateEmail(data.email)) return { valid: false, error: "Invalid email" };
  if (!validateAmount(data.amount)) return { valid: false, error: "Invalid amount" };
  return { valid: true };
}

/**
 * Middleware to inject validation into API handler
 */
export function withValidation(validator) {
  return (handler) => async (req, res) => {
    const validation = validators[validator](req.body);
    if (!validation.valid) return res.status(400).json({ error: validation.error });
    return handler(req, res);
  };
}

const validators = {
  paystack_init: validatePaystackInit,
  trade: validateTrade,
};
