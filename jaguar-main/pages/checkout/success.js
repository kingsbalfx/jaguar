// pages/checkout/success.js
import React from "react";
import Link from "next/link";
import { verifyKorapayCharge } from "../../lib/korapay";
import { getPricingTier } from "../../lib/pricing-config";
import { validatePlanPayment } from "../../lib/payment-amount";
import { activateSubscription } from "../../lib/subscription-lifecycle";
import { createPagesServerClient } from "@supabase/auth-helpers-nextjs";
import { getSupabaseClient } from "../../lib/supabaseClient";
import FeedbackMessage from "../../components/FeedbackMessage";

export default function CheckoutSuccess({ success, message, reference, plan, diagnostic }) {
  const planLabel = getPricingTier(plan)?.displayName || plan || "selected";
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
          <p className="text-gray-200 mb-6">{message}</p>
          {plan && <div className="mt-2 text-gray-300">Plan: <strong>{planLabel}</strong></div>}
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
          <FeedbackMessage message={diagnostic} type="error" className="mt-5 text-left" />
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
  if (process.env.NODE_ENV === "production" && reference.startsWith("SIMULATED_")) {
    return { props: { success: false, message: "Simulated payments are not accepted in production.", reference, plan: null } };
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
      null;
    const supabaseSession = createPagesServerClient(context);
    const { data: { session } } = await supabaseSession.auth.getSession();
    const userId = metadata.userId || metadata.user_id || session?.user?.id || null;
    const buyerEmail = result.email || metadata.email || session?.user?.email || null;
    const paymentValidation = validatePlanPayment({ amount: result.amount, currency: result.currency, plan });
    if (!paymentValidation.valid) {
      return { props: { success: false, message: paymentValidation.error, reference, plan: null } };
    }

    const supabaseAdmin = getSupabaseClient({ server: true });
    if (!supabaseAdmin) {
      return { props: { success: false, message: "Payment verified, but subscription activation service is unavailable.", reference, plan } };
    }

    let activation = null;
    try {
      if (!buyerEmail || !plan) throw new Error("Verified payment is missing account email or plan metadata");
      activation = await activateSubscription({ supabaseAdmin, email: buyerEmail, plan, amount: paymentValidation.normalizedAmount, userId, reference: result.reference || reference });
    } catch (upErr) {
      console.error("Failed updating role after payment:", upErr);
      return {
        props: {
          success: false,
          message: "Payment verified, but subscription activation failed. Reload this page to retry; no new payment is required.",
          reference,
          plan,
          diagnostic: upErr?.message || "Unknown subscription database error",
        },
      };
    }
    if (!activation?.active) {
      return { props: { success: false, message: "Payment verified, but subscription is not active yet. Reload to retry.", reference, plan } };
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
