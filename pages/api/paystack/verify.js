// pages/api/paystack/verify.js
import fetch from "node-fetch";
import { createClient } from "@supabase/supabase-js";

const supabaseAdmin = createClient(process.env.NEXT_PUBLIC_SUPABASE_URL, process.env.SUPABASE_SERVICE_ROLE_KEY);

export default async function handler(req, res) {
  const reference = req.query.reference || req.body?.reference;
  if (!reference) return res.status(400).send("Missing reference");

  try {
    // Verify transaction with Paystack
    const vRes = await fetch(`https://api.paystack.co/transaction/verify/${encodeURIComponent(reference)}`, {
      method: "GET",
      headers: { Authorization: `Bearer ${process.env.PAYSTACK_SECRET_KEY}` },
    });
    const vJson = await vRes.json();
    if (!vRes.ok || vJson.status !== true) {
      console.error("Paystack verify failed", vJson);
      return res.status(400).send("Payment verification failed");
    }

    const trx = vJson.data;
    if (trx.status !== "success") {
      return res.status(400).send("Payment not successful");
    }

    // metadata contains userId and plan we attached earlier
    const userId = trx.metadata?.userId;
    const plan = trx.metadata?.plan;

    if (!userId || !plan) {
      console.warn("Missing metadata", trx.metadata);
      // fallback: may try to find user by email
    }

    // Update user's profile table (or auth app_metadata) to reflect new role
    // Recommended: maintain a profiles table linked to auth.users for roles
    // Example: update profiles table (server-side using service role)
    if (userId) {
      const { error: upErr } = await supabaseAdmin
        .from("profiles")
        .update({ role: plan })
        .eq("id", userId);

      if (upErr) {
        console.error("Failed to update profile role:", upErr);
        // Do not block user — but log and alert
      }
      // Optionally also update auth.user's app_metadata (if that is your source of truth)
      // await supabaseAdmin.auth.admin.updateUserById(userId, { app_metadata: { role: plan } })
    }

    // After update, redirect user to the appropriate dashboard
    let destination = "/dashboard";
    if (plan === "vip") destination = "/dashboard/vip";
    else if (plan === "premium") destination = "/dashboard/premium";

    // If this route is called as a redirect (browser), redirect to destination
    return res.redirect(302, destination);
  } catch (err) {
    console.error("paystack/verify error", err);
    return res.status(500).send("Server error");
  }
}
