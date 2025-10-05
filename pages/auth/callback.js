// pages/auth/callback.js
import React from "react";
import { createPagesServerClient } from "@supabase/auth-helpers-nextjs";
import { getSupabaseClient } from "../../lib/supabaseClient";

/**
 * After OAuth login, this page:
 * - Validates Supabase session.
 * - Gets user role from `profiles`.
 * - Redirects to admin, vip, premium, or dashboard accordingly.
 * - Uses SUPER_ADMIN_EMAIL from .env for emergency admin override.
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
  // ✅ Authenticated Supabase client (server-side, reads cookies)
  const supabase = createPagesServerClient(ctx);

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

  // ✅ Fetch user role
  const { data: profile, error: profileError } = await supabase
    .from("profiles")
    .select("role")
    .eq("id", user.id)
    .maybeSingle();

  if (profileError) {
    console.error("Supabase profile fetch error:", profileError);
    return { redirect: { destination: "/dashboard", permanent: false } };
  }

  const role = profile?.role || null;
  const SUPER_ADMIN_EMAIL = (process.env.SUPER_ADMIN_EMAIL || "").toLowerCase();

  // ✅ Debug output (visible in Vercel build logs)
  console.log("DEBUG => Logged-in user:", email);
  console.log("DEBUG => SUPER_ADMIN_EMAIL:", SUPER_ADMIN_EMAIL);

  // ✅ Admin or Super Admin redirect
  if (role === "admin" || email === SUPER_ADMIN_EMAIL) {
    const destination = validatedNext || "/admin";
    return { redirect: { destination, permanent: false } };
  }

  // ✅ Server-side client for payment validation
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

  // ✅ Role-based routing
  if (role === "vip") {
    const paid = await hasSuccessfulPaymentForPlan("vip");
    const destination = validatedNext || (paid ? "/dashboard/vip" : `/checkout?plan=vip&next=/auth/callback`);
    return { redirect: { destination, permanent: false } };
  }

  if (role === "premium") {
    const paid = await hasSuccessfulPaymentForPlan("premium");
    const destination = validatedNext || (paid ? "/dashboard/premium" : `/checkout?plan=premium&next=/auth/callback`);
    return { redirect: { destination, permanent: false } };
  }

  // ✅ Default user
  const destination = validatedNext || "/dashboard";
  return { redirect: { destination, permanent: false } };
};

export default function Callback() {
  return <div className="p-6 text-center text-gray-700">Redirecting…</div>;
}
