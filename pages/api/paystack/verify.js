import fetch from "node-fetch";
import { createClient } from "@supabase/supabase-js";

const supabaseAdmin = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL,
  process.env.SUPABASE_SERVICE_ROLE_KEY
);

export default async function handler(req, res) {
  const reference = req.query.reference || req.body?.reference;
  if (!reference) return res.status(400).send("Missing reference");

  try {
    const verify = await fetch(
      `https://api.paystack.co/transaction/verify/${encodeURIComponent(reference)}`,
      {
        method: "GET",
        headers: { Authorization: `Bearer ${process.env.PAYSTACK_SECRET_KEY}` },
      }
    );
    const json = await verify.json();
    if (!verify.ok || json.status !== true) {
      console.error("Paystack verify failed:", json);
      return res.status(400).send("Payment verification failed");
    }

    const trx = json.data;
    if (trx.status !== "success") {
      return res.status(400).send("Payment not successful");
    }

    const { userId, plan, email } = trx.metadata || {};

    if (userId) {
      await supabaseAdmin.from("profiles").update({ role: plan }).eq("id", userId);
    } else if (email) {
      const { data } = await supabaseAdmin
        .from("profiles")
        .select("id")
        .eq("email", email)
        .maybeSingle();

      if (data?.id)
        await supabaseAdmin.from("profiles").update({ role: plan }).eq("id", data.id);
    }

    let destination = "/dashboard";
    if (plan === "vip") destination = "/dashboard/vip";
    else if (plan === "premium") destination = "/dashboard/premium";

    return res.redirect(302, destination);
  } catch (err) {
    console.error("paystack/verify error:", err);
    return res.status(500).send("Server error");
  }
}
