// pages/checkout/success.js
import React from "react";
import Header from "../../components/Header";
import Footer from "../../components/Footer";
import Link from "next/link";

export default function CheckoutSuccess({ success, message, reference, plan }) {
  const dashboardUrl = plan === 'vip' ? '/dashboard/vip' : plan === 'premium' ? '/dashboard/premium' : '/dashboard';

  return (
    <>
      <Header />
      <main className="container mx-auto px-6 py-12 text-center">
        <div className="max-w-lg mx-auto bg-gray-800/50 rounded-lg shadow-lg p-8">
          {success ? (
            <svg className="h-16 w-16 text-green-500 mx-auto mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          ) : (
            <svg className="h-16 w-16 text-red-500 mx-auto mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          )}
          <h1 className="text-3xl font-bold mb-4">
            {success ? "Payment Successful" : "Payment Verification Failed"}
          </h1>
          <p className="text-gray-300 mb-6">{message}</p>
          {reference && (
            <div className="mt-4 text-gray-400">
              Reference: <strong>{reference}</strong>
            </div>
          )}
          {success && (
            <div className="mt-8">
              <Link href={dashboardUrl} className="bg-green-600 text-white font-bold py-3 px-6 rounded-lg hover:bg-green-700 transition duration-300">
                Go to Your Dashboard
              </Link>
            </div>
          )}
        </div>
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

    const metadata = trx.metadata || {};
    const plan = metadata.plan || metadata.product || null;
    const userId = metadata.userId || null;
    const buyerEmail = trx.customer?.email || metadata.email || null;

    const { createClient } = await import("@supabase/supabase-js");
    const supabaseAdmin = createClient(
      process.env.NEXT_PUBLIC_SUPABASE_URL,
      process.env.SUPABASE_SERVICE_ROLE_KEY
    );

    try {
      if (userId) {
        await supabaseAdmin.from("profiles").update({ role: plan }).eq("id", userId);
        try {
          await supabaseAdmin.auth.admin.updateUserById(userId, {
            app_metadata: { role: plan },
          });
        } catch (e) {
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
          await supabaseAdmin.from("profiles").insert([{ email: buyerEmail, role: plan }]);
        }
      }
    } catch (upErr) {
      console.error("Failed updating role after payment:", upErr);
    }

    // Redirect logic
    if ((trx.customer?.email || "").toLowerCase() === "shafiuabdullahi.sa3@gmail.com") {
      return {
        redirect: {
          destination: "/admin",
          permanent: false,
        },
      };
    }

    let destination = "/dashboard";
    if (plan === "vip") destination = "/dashboard/vip";
    else if (plan === "premium") destination = "/dashboard/premium";

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
        plan: null,
      },
    };
  }
}