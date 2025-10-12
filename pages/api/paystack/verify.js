// pages/api/paystack/verify.js
import fetch from "node-fetch";
import { getSupabaseClient } from "../../lib/supabaseClient";

const supabaseAdmin = getSupabaseClient({ server: true });

export default async function handler(req, res) {
  // paystack will hit callback_url with ?reference=...
  const reference = req.query.reference || req.body?.reference;
  if (!reference) return res.status(400).send("Missing reference");

  try {
    const verifyRes = await fetch(`https://api.paystack.co/transaction/verify/${encodeURIComponent(reference)}`, {
      method: "GET",
      headers: { Authorization: `Bearer ${process.env.PAYSTACK_SECRET_KEY}` },
    });
    const json = await verifyRes.json();

    if (!verifyRes.ok || json.status !== true) {
      console.error("Paystack verify failed:", json);
      // show simple page explaining failure
      return res.status(400).send("Payment verification failed");
    }

    const trx = json.data;
    if (trx.status !== "success") {
      return res.status(400).send("Payment not successful");
    }

    // metadata should include userId and plan
    const { userId, plan, email } = trx.metadata || {};
    let profileId = userId || null;

    // update payments table
    try {
      await supabaseAdmin.from("payments").insert([{
        user_id: profileId || null,
        plan: plan || null,
        reference: trx.reference,
        amount: trx.amount,
        status: "success",
        raw: JSON.stringify(trx)
      }]);
    } catch (insertErr) {
      console.error("failed to insert payment record:", insertErr);
    }

    // If we have userId set the profile role, else attempt to find by email
    if (profileId) {
      await supabaseAdmin.from("profiles").update({ role: plan }).eq("id", profileId);
    } else if (email) {
      // try to find user by email in profiles
      const { data } = await supabaseAdmin.from("profiles").select("id").eq("email", email).maybeSingle();
      if (data?.id) {
        profileId = data.id;
        await supabaseAdmin.from("profiles").update({ role: plan }).eq("id", data.id);
      }
    }

    // Redirect to best landing
    let destination = "/dashboard";
    if (plan === "vip") destination = "/dashboard/vip";
    else if (plan === "premium") destination = "/dashboard/premium";

    // If you want to include a query with reference or success flag:
    const url = `${destination}?payment=success&reference=${encodeURIComponent(trx.reference)}`;
    return res.redirect(302, url);
  } catch (err) {
    console.error("paystack verify error:", err);
    return res.status(500).send("Server verification error");
  }
}