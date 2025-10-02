// pages/auth/callback.js
import React from "react";
import { createPagesServerClient } from "@supabase/auth-helpers-nextjs";
import { createClient } from "@supabase/supabase-js";

/**
 * Callback page after Supabase OAuth.
 * - ensures server session is present
 * - checks profiles.role
 * - if vip/premium => verifies there's a success payment for that user & plan
 *   (payments table must be populated by your Paystack verify/webhook handler)
 *
 * Behavior:
 *  - admin => /admin
 *  - vip (and has successful payment) => /dashboard/vip
 *  - vip (and no payment) => /checkout?plan=vip&next=/auth/callback
 *  - premium (and has successful payment) => /dashboard/premium
 *  - premium (and no payment) => /checkout?plan=premium&next=/auth/callback
 *  - default => /dashboard
 */

export const getServerSideProps = async (ctx) => {
  // server-side Supabase client (reads cookies)
  const supabase = createPagesServerClient(ctx);

  // get session
  const {
    data: { session },
    error: sessionError,
  } = await supabase.auth.getSession();

  if (sessionError) {
    console.error("Supabase getSession error:", sessionError);
    return { redirect: { destination: "/login", permanent: false } };
  }

  const user = session?.user;
  if (!user || !user.email) {
    return { redirect: { destination: "/login", permanent: false } };
  }

  // Get role from profiles table
  const { data: profile, error: profileError } = await supabase
    .from("profiles")
    .select("role")
    .eq("id", user.id)
    .maybeSingle();

  if (profileError) {
    console.error("Supabase profile fetch error:", profileError);
    // If profile query fails, safe fallback: send to dashboard (or login)
    return { redirect: { destination: "/dashboard", permanent: false } };
  }

  const role = profile?.role ?? null;
  const email = (user.email || "").toLowerCase();

  // allow special super admin env override (optional)
  const SUPER_ADMIN_EMAIL = (process.env.SUPER_ADMIN_EMAIL || "").toLowerCase();
  if (role === "admin" || email === SUPER_ADMIN_EMAIL) {
    return { redirect: { destination: "/admin", permanent: false } };
  }

  // Helper: check payments table for success record
  async function hasSuccessfulPaymentForPlan(plan) {
    try {
      // Use service role key to query payments table server-side
      const supabaseAdmin = createClient(
        process.env.NEXT_PUBLIC_SUPABASE_URL,
        process.env.SUPABASE_SERVICE_ROLE_KEY
      );

      // look for a successful payment record for this user & plan
      const { data: rows, error } = await supabaseAdmin
        .from("payments")
        .select("id, status, paid_at, reference")
        .eq("user_id", user.id)
        .eq("plan", plan)
        .eq("status", "success")
        .order("paid_at", { ascending: false })
        .limit(1);

      if (error) {
        console.warn("payments lookup error:", error);
        return false;
      }
      return Array.isArray(rows) && rows.length > 0;
    } catch (e) {
      console.error("hasSuccessfulPaymentForPlan error:", e);
      return false;
    }
  }

  // Role-based redirection with payment check for paid roles
  if (role === "vip") {
    const paid = await hasSuccessfulPaymentForPlan("vip");
    if (paid) {
      return { redirect: { destination: "/dashboard/vip", permanent: false } };
    } else {
      // Not paid yet — send to checkout (preserving intent)
      const checkoutUrl = `/checkout?plan=vip&next=${encodeURIComponent("/auth/callback")}`;
      return { redirect: { destination: checkoutUrl, permanent: false } };
    }
  }

  if (role === "premium") {
    const paid = await hasSuccessfulPaymentForPlan("premium");
    if (paid) {
      return { redirect: { destination: "/dashboard/premium", permanent: false } };
    } else {
      const checkoutUrl = `/checkout?plan=premium&next=${encodeURIComponent("/auth/callback")}`;
      return { redirect: { destination: checkoutUrl, permanent: false } };
    }
  }

  // default /trial users
  return { redirect: { destination: "/dashboard", permanent: false } };
};

export default function Callback() {
  return <div className="p-6 text-center">Redirecting…</div>;
}
