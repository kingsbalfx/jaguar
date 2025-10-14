// pages/api/paystack/verify.js
import fetch from "node-fetch";
import { getSupabaseClient } from "../../lib/supabaseClient";

export default async function handler(req, res) {
  const reference = req.query.reference || req.body?.reference;
  if (!reference) {
    return res.status(400).send("Missing reference");
  }

  try {
    const verifyRes = await fetch(`https://api.paystack.co/transaction/verify/${encodeURIComponent(reference)}`, {
      method: "GET",
      headers: {
        Authorization: `Bearer ${process.env.PAYSTACK_SECRET_KEY}`,
      },
    });
    const json = await verifyRes.json();

    if (!verifyRes.ok || json.status !== true) {
      console.error("Paystack verify failed:", json);
      return res.status(400).send("Payment verification failed");
    }

    const trx = json.data;
    if (trx.status !== "success") {
      return res.status(400).send("Payment not successful");
    }

    const { plan, userId, email } = trx.metadata || {};

    // Use Supabase admin client to update the user role
    const supabaseAdmin = getSupabaseClient({ server: true });

    // record the payment
    await supabaseAdmin
      .from("payments")
      .insert([
        {
          user_id: userId || null,
          plan,
          reference: trx.reference,
          amount: trx.amount,
          status: "success",
          raw: JSON.stringify(trx),
        },
      ]);

    // update user profile
    if (userId) {
      await supabaseAdmin.from("profiles").update({ role: plan }).eq("id", userId);
    } else if (email) {
      // fallback: find by email
      const { data } = await supabaseAdmin.from("profiles").select("id").eq("email", email).maybeSingle();
      if (data?.id) {
        await supabaseAdmin.from("profiles").update({ role: plan }).eq("id", data.id);
      }
    }

    // redirect user to their dashboard
    let dest = "/dashboard";
    if (plan === "vip") dest = "/dashboard/vip";
    else if (plan === "premium") dest = "/dashboard/premium";

    // You may attach reference or success flag
    return res.redirect(302, `${dest}?reference=${encodeURIComponent(trx.reference)}`);
  } catch (err) {
    console.error("paystack/verify exception:", err);
    return res.status(500).send("Server verification error");
  }
}