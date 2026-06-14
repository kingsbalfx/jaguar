import nodemailer from "nodemailer";
import { getURL } from "./getURL.js";

function smtpConfig() {
  const service = String(process.env.SMTP_SERVICE || "").trim().toLowerCase();
  const user = String(process.env.GMAIL_USER || process.env.SMTP_USER || "").trim();
  const rawPass = String(
    process.env.GMAIL_APP_PASSWORD || process.env.SMTP_PASSWORD || process.env.SMTP_PASS || ""
  ).trim();
  const isGmail = service === "gmail" || Boolean(process.env.GMAIL_USER || process.env.GMAIL_APP_PASSWORD);
  const host = String(process.env.SMTP_HOST || (isGmail ? "smtp.gmail.com" : "")).trim();
  const pass = isGmail ? rawPass.replace(/\s+/g, "") : rawPass;
  if (!host || !user || !pass) return null;
  const port = Number(process.env.SMTP_PORT || 587);
  return {
    host,
    port,
    secure: process.env.SMTP_SECURE === "true" || port === 465,
    auth: { user, pass },
    requireTLS: port === 587,
    connectionTimeout: 15000,
    greetingTimeout: 15000,
    socketTimeout: 30000,
  };
}

function smtpCredentials() {
  const user = String(process.env.GMAIL_USER || process.env.SMTP_USER || "").trim();
  const rawPass = String(
    process.env.GMAIL_APP_PASSWORD || process.env.SMTP_PASSWORD || process.env.SMTP_PASS || ""
  ).trim();
  return { user, passwordLength: rawPass.replace(/\s+/g, "").length };
}

function safeMailerError(error) {
  return {
    code: error?.code || null,
    command: error?.command || null,
    responseCode: error?.responseCode || null,
    message: String(error?.message || "Unknown SMTP error").replace(
      /(?:password|pass|credentials?)\s*[:=]\s*\S+/gi,
      "credentials: [redacted]",
    ),
  };
}

export function isSmtpConfigured() {
  return Boolean(smtpConfig());
}

export function getSmtpStatus() {
  const config = smtpConfig();
  const { user, passwordLength } = smtpCredentials();
  return {
    configured: Boolean(config),
    provider: config?.host === "smtp.gmail.com" ? "Gmail SMTP" : config?.host || "Not configured",
    sender: user ? user.replace(/^(.{2}).*(@.*)$/, "$1***$2") : null,
    port: config?.port || null,
    appPasswordLength: passwordLength,
    appPasswordLengthValid: passwordLength === 16,
  };
}

function createTransporter() {
  const config = smtpConfig();
  return config ? nodemailer.createTransport(config) : null;
}

export async function sendEmail({ to, subject, text, html }) {
  const transporter = createTransporter();
  if (!transporter) {
    console.warn("SMTP email skipped because Gmail/SMTP credentials are not configured.");
    return { sent: false, reason: "smtp_not_configured" };
  }
  const from = process.env.SMTP_FROM || process.env.GMAIL_USER || process.env.SMTP_USER;
  const info = await transporter.sendMail({ from, to, subject, text, html });
  const accepted = (info.accepted || []).map(String);
  const rejected = (info.rejected || []).map(String);
  const sent = accepted.some((recipient) => recipient.toLowerCase() === String(to).toLowerCase());
  return {
    sent,
    reason: sent ? null : "recipient_not_accepted",
    messageId: info.messageId,
    accepted,
    rejected,
    response: info.response || null,
  };
}

export async function verifySmtpConnection() {
  const transporter = createTransporter();
  if (!transporter) return { ok: false, reason: "smtp_not_configured" };
  try {
    await transporter.verify();
    return { ok: true };
  } catch (error) {
    const details = safeMailerError(error);
    console.error("SMTP connection verification failed:", details);
    return { ok: false, reason: "connection_failed", details };
  }
}

export async function sendLifecycleEmail({ supabaseAdmin, email, type, subject, text, html, dedupeKey }) {
  if (!email) return { sent: false, reason: "missing_email" };
  if (dedupeKey && supabaseAdmin) {
    const { data } = await supabaseAdmin
      .from("email_notifications")
      .select("id")
      .eq("dedupe_key", dedupeKey)
      .maybeSingle();
    if (data?.id) return { sent: false, reason: "already_sent" };
  }

  let result;
  try {
    result = await sendEmail({ to: email, subject, text, html });
  } catch (error) {
    const details = safeMailerError(error);
    console.error(`SMTP ${type || "email"} delivery failed:`, details);
    return { sent: false, reason: "delivery_failed", details };
  }
  if (result.sent && dedupeKey && supabaseAdmin) {
    await supabaseAdmin.from("email_notifications").insert({
      email,
      notification_type: type,
      dedupe_key: dedupeKey,
      sent_at: new Date().toISOString(),
    });
  }
  return result;
}

export function emailLayout(title, body, actionLabel, actionPath) {
  const baseUrl = getURL().replace(/\/$/, "");
  const actionUrl = actionPath
    ? /^https?:\/\//i.test(actionPath) ? actionPath : `${baseUrl}${actionPath}`
    : null;
  return `
    <div style="font-family:Arial,sans-serif;max-width:620px;margin:auto;padding:24px;color:#172033">
      <h1 style="font-size:24px">${title}</h1>
      <div style="font-size:16px;line-height:1.6">${body}</div>
      ${actionUrl ? `<p style="margin-top:24px"><a href="${actionUrl}" style="background:#4f46e5;color:white;padding:12px 18px;border-radius:8px;text-decoration:none">${actionLabel}</a></p>` : ""}
      <p style="margin-top:28px;color:#64748b;font-size:13px">KINGSBALFX Academy</p>
    </div>`;
}
