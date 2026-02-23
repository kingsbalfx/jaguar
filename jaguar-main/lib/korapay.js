import crypto from "crypto";
import fetch from "node-fetch";
import { getSupabaseClient } from "./supabaseClient.js";

const DEFAULT_API_BASE = "https://api.korapay.com/merchant/api/v1";

function getConfig() {
  const secret = process.env.KORAPAY_SECRET_KEY || process.env.KORAPAY_SECRET;
  const apiBase = process.env.KORAPAY_API_URL || DEFAULT_API_BASE;
  return { secret, apiBase };
}

export function verifyKorapaySignature(rawBody, signature, secret) {
  if (!secret || !signature) return false;
  const sha256 = crypto.createHmac("sha256", secret).update(rawBody).digest("hex");
  const sha512 = crypto.createHmac("sha512", secret).update(rawBody).digest("hex");
  try {
    const sig = Buffer.from(signature, "utf8");
    return (
      (sig.length === Buffer.from(sha256, "utf8").length &&
        crypto.timingSafeEqual(Buffer.from(sha256, "utf8"), sig)) ||
      (sig.length === Buffer.from(sha512, "utf8").length &&
        crypto.timingSafeEqual(Buffer.from(sha512, "utf8"), sig))
    );
  } catch (e) {
    return false;
  }
}

function normalizeKorapayResponse(json, reference) {
  const payload = json?.data || json || {};
  const rawStatus =
    payload.status ||
    payload.charge_status ||
    payload.transaction_status ||
    payload.state ||
    json?.status;
  const status = typeof rawStatus === "string" ? rawStatus.toLowerCase() : rawStatus;
  const ok =
    status === true ||
    ["success", "successful", "completed", "paid", "approved"].includes(status);

  const metadata = payload.metadata || payload.meta || {};
  const customer = payload.customer || {};

  return {
    ok,
    status: status || "unknown",
    reference: payload.reference || reference,
    amount: payload.amount || payload.amount_paid || payload.amount_in_kobo || payload.amount_in_base || null,
    currency: payload.currency || "NGN",
    email: customer.email || payload.customer_email || metadata.email || null,
    metadata,
    raw: json,
  };
}

export async function initKorapayCharge({ amount, currency = "NGN", email, reference, metadata, redirectUrl }) {
  const { secret, apiBase } = getConfig();
  if (!secret) {
    return { ok: false, error: "Missing KORAPAY_SECRET_KEY on server" };
  }

  const initEndpoint =
    process.env.KORAPAY_INIT_ENDPOINT || `${apiBase}/charges/initialize`;

  const payload = {
    amount,
    currency,
    reference,
    redirect_url: redirectUrl,
    customer: { email },
    metadata: metadata || {},
  };

  const resp = await fetch(initEndpoint, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${secret}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  const json = await resp.json().catch(() => null);
  if (!resp.ok) {
    return { ok: false, error: json?.message || "Korapay init failed", raw: json };
  }

  const data = json?.data || {};
  const checkoutUrl =
    data.checkout_url ||
    data.checkoutUrl ||
    data.authorization_url ||
    data.authorizationUrl ||
    json?.authorization_url;

  if (!checkoutUrl) {
    return { ok: false, error: "No checkout URL returned by Korapay", raw: json };
  }

  return {
    ok: true,
    checkoutUrl,
    reference: data.reference || reference,
    raw: json,
  };
}

export async function verifyKorapayCharge(reference) {
  const { secret, apiBase } = getConfig();
  if (!secret) {
    return { ok: false, error: "Missing KORAPAY_SECRET_KEY on server" };
  }

  const headers = {
    Authorization: `Bearer ${secret}`,
    "Content-Type": "application/json",
  };

  const endpoints = [];
  const customVerify = process.env.KORAPAY_VERIFY_ENDPOINT;
  if (customVerify) {
    endpoints.push({
      url: customVerify.replace("{reference}", encodeURIComponent(reference)),
      method: "GET",
    });
  }

  endpoints.push({ url: `${apiBase}/charges/${encodeURIComponent(reference)}`, method: "GET" });
  endpoints.push({ url: `${apiBase}/charges/verify/${encodeURIComponent(reference)}`, method: "GET" });
  endpoints.push({
    url: `${apiBase}/charges/verify`,
    method: "POST",
    body: JSON.stringify({ reference }),
  });

  let lastJson = null;
  for (const endpoint of endpoints) {
    try {
      const resp = await fetch(endpoint.url, {
        method: endpoint.method,
        headers,
        body: endpoint.body,
      });
      const json = await resp.json().catch(() => null);
      lastJson = json;
      if (resp.ok) {
        return normalizeKorapayResponse(json, reference);
      }
    } catch (e) {
      // try next endpoint
    }
  }

  return { ok: false, error: lastJson?.message || "Korapay verification failed", raw: lastJson };
}

export async function handleKorapayEvent(rawBody, eventJson) {
  try {
    const supabase = getSupabaseClient({ server: true });
    if (!supabase) throw new Error("Supabase admin client not configured");

    const payload = eventJson?.data || eventJson || {};
    const customer = payload.customer || {};
    const customerEmail = customer.email || payload.customer_email || payload.email || null;
    const amount = payload.amount || payload.amount_paid || null;
    const status = payload.status || eventJson?.status || "received";
    const eventName = eventJson?.event || eventJson?.type || "korapay.event";
    const metadata = payload.metadata || payload.meta || {};
    const plan = metadata.plan || metadata.product || metadata.tier || null;
    const userId = metadata.userId || metadata.user_id || null;

    await supabase.from("payments").insert([
      {
        event: eventName,
        data: eventJson,
        customer_email: customerEmail,
        amount,
        status: typeof status === "string" ? status : JSON.stringify(status),
        received_at: new Date().toISOString(),
      },
    ]);

    const isSuccess =
      typeof status === "string"
        ? ["success", "successful", "completed", "paid", "approved"].includes(status.toLowerCase())
        : Boolean(status);

    if (isSuccess && plan) {
      try {
        if (userId) {
          await supabase.from("profiles").update({ role: plan }).eq("id", userId);
          try {
            await supabase.auth.admin.updateUserById(userId, {
              app_metadata: { role: plan },
            });
          } catch (e) {
            console.warn("auth.admin.updateUserById failed:", e?.message || e);
          }
        } else if (customerEmail) {
          const { data: profile } = await supabase
            .from("profiles")
            .select("id")
            .eq("email", customerEmail)
            .maybeSingle();
          if (profile?.id) {
            await supabase.from("profiles").update({ role: plan }).eq("id", profile.id);
          }
        }
      } catch (e) {
        console.warn("Failed updating profile role from webhook:", e?.message || e);
      }
    }
  } catch (e) {
    console.warn("Failed saving Korapay event to supabase:", e.message || e);
  }
}
