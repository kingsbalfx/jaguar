import crypto from "crypto";

function getKey() {
  const secret = process.env.MT5_CREDENTIALS_SECRET;
  if (!secret && process.env.NODE_ENV === "production") {
    throw new Error("MT5 credential submissions are unavailable until encryption is configured.");
  }
  return crypto.createHash("sha256").update(secret || "development-only-mt5-secret").digest();
}

export function encryptMt5Password(password) {
  const iv = crypto.randomBytes(12);
  const cipher = crypto.createCipheriv("aes-256-gcm", getKey(), iv);
  const encrypted = Buffer.concat([cipher.update(String(password), "utf8"), cipher.final()]);
  return {
    password_encrypted: encrypted.toString("base64"),
    password_iv: iv.toString("base64"),
    password_tag: cipher.getAuthTag().toString("base64"),
    password_last4: String(password).slice(-4),
  };
}

export function maskPassword(last4) {
  return last4 ? `****${String(last4).slice(-4)}` : "****";
}
