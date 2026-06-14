import nodemailer from "nodemailer";
import { getURL } from "./getURL.js";

function smtpConfig() {
  const host = process.env.SMTP_HOST;
  const user = process.env.SMTP_USER;
  const pass = process.env.SMTP_PASSWORD || process.env.SMTP_PASS;
  if (!host || !user || !pass) return null;
  const port = Number(process.env.SMTP_PORT || 587);
  return {
    host,
    port,
    secure: process.env.SMTP_SECURE === "true" || port === 465,
    auth: { user, pass },
  };
}

export function isSmtpConfigured() {
  return Boolean(smtpConfig());
}

export async function sendEmail({ to, subject, text, html }) {
  const config = smtpConfig();
  if (!config) {
    console.warn("SMTP email skipped because SMTP_HOST, SMTP_USER, and SMTP_PASSWORD are not configured.");
    return { sent: false, reason: "smtp_not_configured" };
  }
  const transporter = nodemailer.createTransport(config);
  const from = process.env.SMTP_FROM || process.env.SMTP_USER;
  const info = await transporter.sendMail({ from, to, subject, text, html });
  return { sent: true, messageId: info.messageId };
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
    console.error(`SMTP ${type || "email"} delivery failed:`, error?.message || error);
    return { sent: false, reason: "delivery_failed" };
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
