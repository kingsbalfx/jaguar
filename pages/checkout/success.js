// pages/checkout/success.js
import React from "react";
import Header from "../../components/Header";
import Footer from "../../components/Footer";

/**
 * This page verifies a Paystack transaction server-side (getServerSideProps).
 * On success it updates the user's role in Supabase (profiles table) using
 * the SUPABASE_SERVICE_ROLE_KEY (server-only), then redirects the user to
 * the appropriate dashboard.
 *
 * IMPORTANT:
 * - SUPABASE_SERVICE_ROLE_KEY and PAYSTACK_SECRET_KEY must be set in Vercel
 *   as server-side environment variables (do NOT expose service key to client).
 * - This page expects Paystack to call /redirect?reference=... which lands here
 *   as /checkout/success?reference=...
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

  // 1) Verify transaction with Paystack
  try {
    const paystackRes = await fetch(
      `https://api.paystack.co/transaction/verify/${encodeURIComponent(reference)}`,
      {
        method: "GET",
        headers: {
          Authorization: `Bearer ${process.env.PAYSTACK_SECRET_KEY}`,
        },
      }
    );
    const paystackJson = await paystackRes.json();

    // Paystack returns status: true/false at top-level; data contains details
    if (!paystackRes.ok || paystackJson.status !== true) {
      return {
        props: {
          success: false,
          message:
            paystackJson.message || "Unable to verify transaction with Paystack.",
          reference,
        },
      };
    }

    const trx = paystackJson.data;
    if (trx.status !== "success") {
      return {
        props: {
          success: false,
          message: `Payment not successful (status: ${trx.status}).`,
          reference,
        },
      };
    }

    // 2) Extract metadata we sent during initialization (we recommended: { userId, plan })
    const metadata = trx.metadata || {};
    const plan = metadata.plan || metadata?.product || null; // expected 'vip' or 'premium'
    const userId = metadata.userId || null;
    const buyerEmail = trx.customer?.email || metadata.email || null;

    // 3) Update Supabase to set role = plan (server-side using service role)
    // Use supabase-js admin client with SUPABASE_SERVICE_ROLE_KEY
    const { createClient } = await import("@supabase/supabase-js");
    const supabaseAdmin = createClient(
      process.env.NEXT_PUBLIC_SUPABASE_URL,
      process.env.SUPABASE_SERVICE_ROLE_KEY
    );

    let updated = false;
    let updateError = null;

    try {
      if (userId) {
        // Preferred: update profiles table if you maintain one
        const { error: upErr } = await supabaseAdmin
          .from("profiles")
          .update({ role: plan })
          .eq("id", userId);
        if (upErr) {
          // fallback: try updating auth user app_metadata
          updateError = upErr;
        } else {
          updated = true;
        }

        // Also optionally update auth user's app_metadata (if you use it)
        try {
          const { error: authErr } = await supabaseAdmin.auth.admin.updateUserById(userId, {
            app_metadata: { role: plan },
          });
          if (authErr) {
            // not fatal — log
            console.warn("auth.admin.updateUserById error:", authErr);
          }
        } catch (e) {
          // ignore
        }
      } else if (buyerEmail) {
        // No userId in metadata — attempt to find profile by email and update
        const { data: profileRow, error: selErr } = await supabaseAdmin
          .from("profiles")
          .select("id")
          .eq("email", buyerEmail)
          .maybeSingle();
        if (selErr) {
          updateError = selErr;
        } else if (profileRow?.id) {
          const { error: upErr2 } = await supabaseAdmin
            .from("profiles")
            .update({ role: plan })
            .eq("id", profileRow.id);
          if (upErr2) updateError = upErr2;
          else updated = true;
        } else {
          // no profile found — you might want to create one
          const { error: insErr } = await supabaseAdmin.from("profiles").insert([
            { id: null, email: buyerEmail, role: plan },
          ]);
          if (insErr) {
            updateError = insErr;
          } else {
            updated = true;
          }
        }
      }
    } catch (err) {
      updateError = err;
    }

    if (!updated && updateError) {
      console.error("Failed updating user role after payment:", updateError);
      // We won't block the user; continue to redirect to success but note the issue
    }

    // 4) Optional: subscribe to Mailchimp (if MAILCHIMP vars set)
    try {
      const emailToSubscribe = buyerEmail;
      const listId = process.env.MAILCHIMP_LIST_ID;
      const apiKey = process.env.MAILCHIMP_API_KEY;
      if (emailToSubscribe && listId && apiKey) {
        const dc = apiKey.split("-").pop();
        const mcRes = await fetch(`https://${dc}.api.mailchimp.com/3.0/lists/${listId}/members`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Basic ${Buffer.from(`apikey:${apiKey}`).toString("base64")}`,
          },
          body: JSON.stringify({ email_address: emailToSubscribe, status: "subscribed" }),
        });
        // ignore result if already subscribed
        if (mcRes.status !== 200 && mcRes.status !== 201) {
          // log but don't fail
          const mcJson = await mcRes.json().catch(() => ({}));
          console.warn("Mailchimp subscribe issue:", mcRes.status, mcJson);
        }
      }
    } catch (err) {
      console.warn("Mailchimp subscribe failed:", err);
    }

    // 5) Final: redirect user to appropriate page based on plan (role)
    let destination = "/dashboard";
    if (plan === "vip") destination = "/dashboard/vip";
    else if (plan === "premium") destination = "/dashboard/premium";

    // If the buyer's email is the special admin, route to /admin
    if ((trx.customer?.email || "").toLowerCase() === "shafiuabdullahi.sa3@gmail.com") {
      destination = "/admin";
    }

    // Prefer to redirect server-side to the destination (user lands directly)
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
        refere:contentReference[oaicite:0]{index=0}:contentReference[oaicite:1]{index=1}
