import crypto from "crypto";
import fetch from "node-fetch";
import { getSupabaseClient } from "./supabaseClient.js";

export function verifySignature(rawBody, signature, secret) {
  if (!secret || !signature) return false;
  const expected = crypto.createHmac("sha512", secret).update(rawBody).digest("hex");
  try {
    const a = Buffer.from(expected, "utf8");
    const b = Buffer.from(signature, "utf8");
    if (a.length !== b.length) return false;
    return crypto.timingSafeEqual(a, b);
  } catch (e) {
    return false;
  }
}

export async function handlePaystackEvent(rawBody, eventJson) {
  // minimal processing: persist into Supabase 'payments' table
  try {
    const supabase = getSupabaseClient({ server: true });
    const data = {
      event: eventJson.event,
      data: eventJson.data || {},
      received_at: new Date().toISOString()
    };
    await supabase.from("payments").insert([data]);

    // On successful charge, grant lifetime access to the purchaser if possible
    try {
      const ev = (eventJson || {}).event || "";
      if (ev === "charge.success" || ev === "transaction.success") {
        const customerEmail = (eventJson.data && (eventJson.data.customer?.email || eventJson.data.customer_email)) || eventJson.data?.customer?.email || null;
        const amount = eventJson.data?.amount || eventJson.data?.paid_at || null;

        if (customerEmail) {
          // Mark profile with lifetime flag (if column exists) and upsert subscriptions table
          try {
            await supabase.from("profiles").update({ lifetime: true }).eq("email", customerEmail);
          } catch (e) {
            // ignore if column doesn't exist
            console.warn("Could not update profiles.lifetime (column may not exist):", e.message || e);
          }

          try {
            await supabase.from("subscriptions").insert([{ email: customerEmail, plan: "lifetime", amount: amount || 0, status: "active", started_at: new Date().toISOString() }]);
          } catch (e) {
            // ignore if subscriptions table doesn't exist
            console.warn("Could not insert to subscriptions table:", e.message || e);
          }
        }
      }
    } catch (e) {
      console.warn("Error processing charge.success actions:", e.message || e);
    }
  } catch (e) {
    console.warn("Failed saving paystack event to supabase:", e.message || e);
  }
}
