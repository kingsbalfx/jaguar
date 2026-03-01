// pages/checkout/success.js
import React from "react";
import Link from "next/link";
import { verifyKorapayCharge } from "../../lib/korapay";
import { PRICING_TIERS } from "../../lib/pricing-config";

export default function CheckoutSuccess({ success, message, reference, plan }) {
  const dashboardUrl =
    plan === "vip"
      ? "/dashboard/vip"
      : plan === "premium"
      ? "/dashboard/premium"
      : plan === "pro"
      ? "/dashboard/pro"
      : plan === "lifetime"
      ? "/dashboard/lifetime"
      : "/dashboard";

  return (
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
  );
}

function normalizeReference(value) {
  if (!value) return null;
  const ref = Array.isArray(value) ? value[0] : String(value);
  if (!ref) return null;
  const trimmed = ref.trim();
  if (!trimmed) return null;
  if (trimmed.includes(",")) {
    return trimmed.split(",")[0];
  }
  const firstKbs = trimmed.indexOf("KBS_");
  const secondKbs = trimmed.indexOf("KBS_", firstKbs + 1);
  if (firstKbs === 0 && secondKbs > 0) {
    return trimmed.slice(0, secondKbs);
  }
  const match = trimmed.match(/KBS_[A-Za-z0-9_]+/);
  return match ? match[0] : trimmed;
}

export async function getServerSideProps(context) {
  const reference =
    normalizeReference(context.query.reference) ||
    normalizeReference(context.query.ref) ||
    normalizeReference(context.query.transaction_reference) ||
    null;

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
    const result = await verifyKorapayCharge(reference);
    if (!result.ok) {
      return {
        props: {
          success: false,
          message: result.error || "Unable to verify transaction with Korapay.",
          reference,
        },
      };
    }

    const metadata = result.metadata || {};
    const plan =
      metadata.plan ||
      metadata.product ||
      metadata.tier ||
      (typeof context.query.plan === "string" ? context.query.plan : null);
    const userId = metadata.userId || metadata.user_id || null;
    const buyerEmail = result.email || metadata.email || null;
    const tier = PRICING_TIERS[String(plan || "").toUpperCase()];
    const endedAt =
      tier?.billingCycle === "monthly"
        ? new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString()
        : null;

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
      if (buyerEmail) {
        await supabaseAdmin.from("subscriptions").upsert(
          {
            email: buyerEmail,
            plan,
            status: "active",
            amount: result.amount || 0,
            started_at: new Date().toISOString(),
            ended_at: endedAt,
          },
          { onConflict: "email,plan" }
        );
      }
    } catch (upErr) {
      console.error("Failed updating role after payment:", upErr);
    }

    // Redirect logic
    const SUPER = (process.env.SUPER_ADMIN_EMAIL || "").toLowerCase();
    const FALLBACK_ADMIN =
      (process.env.NEXT_PUBLIC_ADMIN_EMAIL || process.env.ADMIN_EMAIL || "").toLowerCase();
    const buyerLower = (buyerEmail || "").toLowerCase();
    if (buyerLower && (buyerLower === SUPER || buyerLower === FALLBACK_ADMIN)) {
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
    else if (plan === "pro") destination = "/dashboard/pro";
    else if (plan === "lifetime") destination = "/dashboard/lifetime";

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
