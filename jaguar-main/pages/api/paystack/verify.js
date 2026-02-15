// pages/api/paystack/verify.js
import { getSupabaseClient } from "../../lib/supabaseClient";
import { getURL } from "../../lib/getURL";

// ✅ Helper to safely extract reference (GET or POST)
function getReference(req) {
  return req.query?.reference || req.body?.reference || req.query?.ref || null;
}

export default async function handler(req, res) {
  const reference = getReference(req);

  if (!reference) {
    console.error("❌ Missing Paystack reference in callback:", req.query, req.body);
    return res.status(400).json({ error: "Missing reference parameter" });
  }

  try {
    // ✅ Verify transaction with Paystack
    const verifyRes = await fetch(
      `https://api.paystack.co/transaction/verify/${encodeURIComponent(reference)}`,
      {
        method: "GET",
        headers: {
          Authorization: `Bearer ${process.env.PAYSTACK_SECRET_KEY}`,
          "Content-Type": "application/json",
        },
      }
    );

    const json = await verifyRes.json();

    if (!verifyRes.ok || !json.status) {
      console.error("❌ Paystack verification failed:", json);
      return res
        .status(400)
        .json({ error: json.message || "Paystack verification failed" });
    }

    const trx = json.data;
    if (!trx || trx.status !== "success") {
      console.error("⚠️ Transaction not successful:", trx?.status);
      return res
        .status(400)
        .json({ error: `Payment not successful: ${trx?.status}` });
    }

    const metadata = trx.metadata || {};
    const plan = metadata.plan || metadata.product || "user";
    const userId = metadata.userId || metadata.user_id || null;
    const buyerEmail = trx.customer?.email || metadata.email || null;

    // ✅ Connect Supabase (service role)
    const supabaseAdmin = getSupabaseClient({ server: true });

    // ✅ Record successful payment
    const { error: payErr } = await supabaseAdmin.from("payments").insert([
      {
        user_id: userId,
        plan,
        reference: trx.reference,
        amount: trx.amount / 100, // Paystack sends kobo
        status: "success",
        raw: trx,
      },
    ]);
    if (payErr) console.warn("⚠️ Payment insert failed:", payErr);

    // ✅ Update user profile role
    if (userId) {
      await supabaseAdmin.from("profiles").update({ role: plan }).eq("id", userId);
    } else if (buyerEmail) {
      const { data: profile } = await supabaseAdmin
        .from("profiles")
        .select("id")
        .eq("email", buyerEmail)
        .maybeSingle();
      if (profile?.id) {
        await supabaseAdmin.from("profiles").update({ role: plan }).eq("id", profile.id);
      }
    }

    // ✅ Redirect user to correct dashboard
    let dest = "/dashboard";
    if (plan === "vip") dest = "/dashboard/vip";
    else if (plan === "premium") dest = "/dashboard/premium";

    // Include reference in redirect for confirmation page if needed
    const baseUrl = getURL().replace(/\/$/, "");
    return res.redirect(302, `${baseUrl}${dest}?reference=${encodeURIComponent(reference)}`);
  } catch (err) {
    console.error("💥 Paystack verify exception:", err);
    return res
      .status(500)
      .json({ error: "Server error while verifying payment", detail: err.message });
  }
}
