import crypto from "crypto";
import { getPricingTier, formatPrice } from "./pricing-config.js";
import { getURL } from "./getURL.js";

function escapeHtml(value) {
  return String(value || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function compact(value) {
  return String(value || "")
    .trim()
    .replace(/[^a-z0-9_-]+/gi, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 80);
}

function signingSecret() {
  return String(
    process.env.RECEIPT_SIGNING_SECRET ||
      process.env.SUPABASE_SERVICE_ROLE_KEY ||
      process.env.NEXT_PUBLIC_SUPABASE_URL ||
      "kingsbalfx-receipt-signing"
  );
}

export function createReceiptSignature(payload) {
  return crypto
    .createHmac("sha256", signingSecret())
    .update(JSON.stringify(payload))
    .digest("hex")
    .toUpperCase();
}

export function buildSubscriptionReceipt({ email, plan, amount, currency = "NGN", reference, startedAt, endedAt }) {
  const tier = getPricingTier(plan);
  const issuedAt = new Date().toISOString();
  const receiptId = `KBS-RCPT-${Date.now()}-${crypto.randomBytes(4).toString("hex").toUpperCase()}`;
  const receiptPayload = {
    receiptId,
    email: String(email || "").trim().toLowerCase(),
    plan: String(plan || "").trim().toLowerCase(),
    amount: Number(amount || 0),
    currency,
    reference: reference || null,
    startedAt: startedAt || null,
    endedAt: endedAt || null,
    issuedAt,
  };
  const signature = createReceiptSignature(receiptPayload);
  const planName = tier?.displayName || plan || "Subscription";
  const expiryLabel = endedAt ? new Date(endedAt).toLocaleString("en-NG") : "No expiry";
  const startLabel = startedAt ? new Date(startedAt).toLocaleString("en-NG") : new Date(issuedAt).toLocaleString("en-NG");
  const verifyUrl = `${getURL().replace(/\/$/, "")}/api/receipts/verify?receipt=${encodeURIComponent(receiptId)}`;
  const filename = `${compact(receiptId)}-${compact(planName)}.html`;

  const html = `<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <title>KINGSBALFX Original Receipt ${escapeHtml(receiptId)}</title>
  </head>
  <body style="margin:0;background:#07111f;color:#172033;font-family:Arial,sans-serif">
    <main style="max-width:760px;margin:0 auto;padding:28px">
      <section style="background:#ffffff;border-radius:24px;padding:28px;border:1px solid #dbe4ef;position:relative;overflow:hidden">
        <div style="position:absolute;inset:80px 0 auto 0;text-align:center;font-size:72px;font-weight:900;letter-spacing:8px;color:rgba(15,23,42,0.06);transform:rotate(-18deg)">KINGSBALFX ORIGINAL</div>
        <div style="position:relative">
          <div style="display:flex;justify-content:space-between;gap:16px;align-items:flex-start">
            <div>
              <div style="font-size:13px;letter-spacing:3px;color:#64748b;font-weight:700">OFFICIAL RECEIPT</div>
              <h1 style="margin:8px 0 0;font-size:30px;color:#0f172a">KINGSBALFX Academy</h1>
              <p style="margin:6px 0 0;color:#64748b">Original subscription payment receipt</p>
            </div>
            <div style="border:3px solid #16a34a;color:#16a34a;border-radius:999px;padding:16px 18px;font-weight:900;transform:rotate(-8deg);text-align:center">
              ORIGINAL<br />STAMP
            </div>
          </div>

          <div style="margin-top:28px;border-radius:18px;background:#f8fafc;border:1px solid #e2e8f0;padding:20px">
            <p style="margin:0 0 8px;color:#64748b;font-size:13px">Receipt ID</p>
            <p style="margin:0;font-size:20px;font-weight:800;color:#0f172a">${escapeHtml(receiptId)}</p>
            <p style="margin:16px 0 8px;color:#64748b;font-size:13px">Tamper-evident signature</p>
            <p style="margin:0;word-break:break-all;font-family:Consolas,monospace;font-size:12px;color:#334155">${signature}</p>
          </div>

          <table style="width:100%;border-collapse:collapse;margin-top:24px;font-size:15px">
            <tr><td style="padding:12px;border-bottom:1px solid #e2e8f0;color:#64748b">Subscriber</td><td style="padding:12px;border-bottom:1px solid #e2e8f0;font-weight:700">${escapeHtml(receiptPayload.email)}</td></tr>
            <tr><td style="padding:12px;border-bottom:1px solid #e2e8f0;color:#64748b">Plan</td><td style="padding:12px;border-bottom:1px solid #e2e8f0;font-weight:700">${escapeHtml(planName)}</td></tr>
            <tr><td style="padding:12px;border-bottom:1px solid #e2e8f0;color:#64748b">Amount</td><td style="padding:12px;border-bottom:1px solid #e2e8f0;font-weight:700">${escapeHtml(formatPrice(receiptPayload.amount))}</td></tr>
            <tr><td style="padding:12px;border-bottom:1px solid #e2e8f0;color:#64748b">Payment reference</td><td style="padding:12px;border-bottom:1px solid #e2e8f0;font-weight:700">${escapeHtml(reference || "Manual activation")}</td></tr>
            <tr><td style="padding:12px;border-bottom:1px solid #e2e8f0;color:#64748b">Access starts</td><td style="padding:12px;border-bottom:1px solid #e2e8f0">${escapeHtml(startLabel)}</td></tr>
            <tr><td style="padding:12px;border-bottom:1px solid #e2e8f0;color:#64748b">Access expires</td><td style="padding:12px;border-bottom:1px solid #e2e8f0">${escapeHtml(expiryLabel)}</td></tr>
            <tr><td style="padding:12px;color:#64748b">Issued</td><td style="padding:12px">${escapeHtml(new Date(issuedAt).toLocaleString("en-NG"))}</td></tr>
          </table>

          <p style="margin-top:24px;color:#475569;line-height:1.6">
            This receipt is marked original by KINGSBALFX. Any edit to the receipt details will not match the server-generated signature above.
          </p>
          <p style="margin-top:12px;color:#64748b;font-size:12px">Verification endpoint: ${escapeHtml(verifyUrl)}</p>
        </div>
      </section>
    </main>
  </body>
</html>`;

  return {
    receiptId,
    signature,
    payload: receiptPayload,
    filename,
    html,
    attachment: {
      filename,
      content: html,
      contentType: "text/html",
    },
  };
}
