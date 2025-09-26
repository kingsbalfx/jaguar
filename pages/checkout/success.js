// pages/checkout/success.js
import React from "react";
import Header from "../../components/Header";
import Footer from "../../components/Footer";

/**
 * Server-side Paystack verification + profile update.
 * - Requires PAYSTACK_SECRET_KEY and SUPABASE_SERVICE_ROLE_KEY (server envs).
 * - Expects Paystack redirect to this page with ?reference=...
 */

export default function CheckoutSuccess({ success, message, reference }) {
  return (
    <>
      <Header />
      <main className="container mx-auto px-6 py-8">
        <h1 className="text-2xl font-bold mb-4">
          {success ? "Payment Successful" : "Payment Verification Failed"}
        </h1>
        <p className="mb-2">{message}</p>
        {reference && (
          <div className="mt-2">
            Reference: <strong>{reference}</strong>
          </div>
        )}
      </main>
      <Footer />
    </>
  );
}

export async function getServerSideProps(context) {
  const reference = context.query.reference || context.query.ref || null;

  if (!reference) {
    return {
      props: {
        success: false,
        message: "No payment reference provided.",
        reference: null,
      },
    };
  }

  try {
    // 1) Verify transaction with Paystack
    const vRes = await fetch(
      `https://api.paystack.co/transaction/verify/${encodeURIComponent(reference)}`,
      {
        method: "GET",
        headers: { Authorization: `Bearer ${process.env.PAYSTACK_SECRET_KEY}` },
      }
    );
    const vJson = await vRes.json();

    if (!vRes.ok || vJson.status !== true) {
      return {
        props: {
          success: false,
          message: vJson.message || "Unable to verify transaction with Paystack.",
          reference,
        },
      };
    }

    const trx = vJson.data;
    if (trx.status !== "success") {
      return {
        props: {
          success: false,
          message: `Payment not successful (status: ${trx.status}).`,
          reference,
        },
      };
    }

    // 2) Extract metadata
    const metadata = trx.metadata || {};
    const plan = metadata.plan || metadata.product || null; // 'vip'|'premium'
    const userId = metadata.userId || null;
    const buyerEmail = trx.customer?.email || metadata.email || null;

    // 3) Update Supabase server-side using service role key
    const { createClient } = await import("@supabase/supabase-js");
    const supabaseAdmin = createClient(
      process.env.NEXT_PUBLIC_SUPABASE_URL,
      process.env.SUPABASE_SERVICE_ROLE_KEY
    );

    try {
      if (userId) {
        // update profiles table if exists
        await supabaseAdmin.from("profiles").update({ role: plan }).eq("id", userId);
        // attempt to also set auth app_metadata (best-effort)
        try {
          await supabaseAdmin.auth.admin.updateUserById(userId, {
            app_metadata: { role: plan },
          });
        } catch (e) {
          // non-fatal
          console.warn("auth.admin.updateUserById failed:", e?.message || e);
        }
      } else if (buyerEmail) {
        const { data: profileRow } = await supabaseAdmin
          .from("profiles")
          .select("id")
          .eq("email", buyerEmail)
          .maybeSingle();

        if (profileRow?.id) {
          await supabaseAdmin.from("profiles").update({ role: plan }).eq("id", profileRow.id);
        } else {
          // create profile if none exists (optional)
          await supabaseAdmin.from("profiles").insert([{ email: buyerEmail, role: plan }]);
        }
      }
    } catch (upErr) {
      console.error("Failed updating role after payment:", upErr);
      // continue — don't block the user
    }

    // 4) Optional Mailchimp subscribe (best-effort)
    try {
      const listId = process.env.MAILCHIMP_LIST_ID;
      const apiKey = process.env.MAILCHIMP_API_KEY;
      const emailToSubscribe = buyerEmail;
      if (emailToSubscribe && listId && apiKey) {
        const dc = apiKey.split("-").pop();
        await fetch(`https://${dc}.api.mailchimp.com/3.0/lists/${listId}/members`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Basic ${Buffer.from(`apikey:${apiKey}`).toString("base64")}`,
          },
          body: JSON.stringify({ email_address: emailToSubscribe, status: "subscribed" }),
        });
      }
    } catch (mcErr) {
      console.warn("Mailchimp subscribe failed:", mcErr);
    }

    // 5) Redirect to proper dashboard
    let destination = "/dashboard";
    if (plan === "vip") destination = "/dashboard/vip";
    else if (plan === "premium") destination = "/dashboard/premium";
    if ((trx.customer?.email || "").toLowerCase() === "shafiuabdullahi.sa3@gmail.com") {
      destination = "/admin";
    }

    return {
      redirect: {
        destination,
        permanent: false,
      },
    };
  } catch (err) {
    console.error("checkout success verification error:", err);
    return {
      props: {
        success: false,
        message: "Server error while verifying payment. Try again or contact support.",
        reference: null,
      },
    };
  }
}
