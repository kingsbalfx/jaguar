import React from "react";
import { createPagesServerClient } from "@supabase/auth-helpers-nextjs";
import { getSupabaseClient } from "../../lib/supabaseClient";

/**
 * Supabase Auth Callback
 * -----------------------
 * - Verifies session after login or signup.
 * - If no profile record exists, redirect to /complete-profile.
 * - Routes by role (admin, vip, premium, user).
 * - Supports SUPER_ADMIN_EMAIL from .env for master admin access.
 * - Uses payments table to verify paid subscriptions.
 */

function safeNextParam(rawNext) {
  if (!rawNext) return null;
  try {
    const decoded = decodeURIComponent(String(rawNext));
    if (decoded.startsWith("/") && !decoded.startsWith("//")) return decoded;
    return null;
  } catch {
    return null;
  }
}

export const getServerSideProps = async (ctx) => {
  const supabase = createPagesServerClient(ctx);

  // ✅ Step 1: Verify user session
  const {
    data: { session },
    error: sessionError,
  } = await supabase.auth.getSession();

  if (sessionError || !session?.user) {
    console.error("Supabase session error:", sessionError);
    return { redirect: { destination: "/login", permanent: false } };
  }

  const user = session.user;
  const email = user.email?.toLowerCase() || "";
  const rawNext = ctx.query?.next ?? null;
  const validatedNext = safeNextParam(rawNext);

  // ✅ Step 2: Fetch user profile
  const { data: profile, error: profileError } = await supabase
    .from("profiles")
    .select("*")
    .eq("id", user.id)
    .maybeSingle();

  if (profileError) {
    console.error("Supabase profile fetch error:", profileError);
  }

  // ✅ Step 3: Super Admin Logic
  const SUPER_ADMIN_EMAIL = (process.env.SUPER_ADMIN_EMAIL || "").toLowerCase();
  const role = profile?.role || null;

  console.log("DEBUG => Logged-in user:", email);
  console.log("DEBUG => SUPER_ADMIN_EMAIL:", SUPER_ADMIN_EMAIL);

  // ✅ Step 4: New user profile redirect
  if (!profile) {
    console.log("⚠️ No profile found for user. Redirecting to /complete-profile");
    return { redirect: { destination: "/complete-profile", permanent: false } };
  }

  // ✅ Step 5: Admin or Super Admin redirect
  if (role === "admin" || email === SUPER_ADMIN_EMAIL) {
    const destination = validatedNext || "/admin";
    return { redirect: { destination, permanent: false } };
  }

  // ✅ Step 6: Create a server client to check payments
  const supabaseAdmin = getSupabaseClient({ server: true });

  async function hasSuccessfulPaymentForPlan(plan) {
    try {
      const { data, error } = await supabaseAdmin
        .from("payments")
        .select("id")
        .eq("user_id", user.id)
        .eq("plan", plan)
        .eq("status", "success")
        .limit(1);

      if (error) {
        console.warn("Payment lookup error:", error);
        return false;
      }

      return Array.isArray(data) && data.length > 0;
    } catch (e) {
      console.error("Payment check error:", e);
      return false;
    }
  }

  // ✅ Step 7: Role-based redirects
  if (role === "vip") {
    const paid = await hasSuccessfulPaymentForPlan("vip");
    const destination =
      validatedNext ||
      (paid
        ? "/dashboard/vip"
        : `/checkout?plan=vip&next=/auth/callback`);
    return { redirect: { destination, permanent: false } };
  }

  if (role === "premium") {
    const paid = await hasSuccessfulPaymentForPlan("premium");
    const destination =
      validatedNext ||
      (paid
        ? "/dashboard/premium"
        : `/checkout?plan=premium&next=/auth/callback`);
    return { redirect: { destination, permanent: false } };
  }

  // ✅ Step 8: Default users → normal dashboard
  const destination = validatedNext || "/dashboard";
  return { redirect: { destination, permanent: false } };
};

// ✅ Step 9: Fallback UI while redirecting
export default function Callback() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-black text-gray-300 text-lg">
      Redirecting…
    </div>
  );
}
