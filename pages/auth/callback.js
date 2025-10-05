import React from "react";
import { createPagesServerClient } from "@supabase/auth-helpers-nextjs";
import { createClient } from "@supabase/supabase-js";

function safeNextParam(rawNext) {
  if (!rawNext) return null;
  try {
    const decoded = decodeURIComponent(String(rawNext));
    if (decoded.startsWith("/") && !decoded.startsWith("//")) {
      return decoded;
    }
    return null;
  } catch (e) {
    return null;
  }
}

export const getServerSideProps = async (ctx) => {
  const supabase = createPagesServerClient(ctx);

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

  const rawNext = ctx.query?.next ?? null;
  const validatedNext = safeNextParam(rawNext);

  const { data: profile, error: profileError } = await supabase
    .from("profiles")
    .select("role")
    .eq("id", user.id)
    .maybeSingle();

  if (profileError) {
    console.error("Supabase profile fetch error:", profileError);
    return { redirect: { destination: "/dashboard", permanent: false } };
  }

  const role = profile?.role ?? null;
  const email = (user.email || "").toLowerCase();
  const SUPER_ADMIN_EMAIL = (process.env.SUPER_ADMIN_EMAIL || "").toLowerCase();

  // Debug logs to verify environment variable
  console.log("DEBUG => Logged-in:", email);
  console.log("DEBUG => SUPER_ADMIN_EMAIL:", process.env.SUPER_ADMIN_EMAIL);

  if (role === "admin" || email === SUPER_ADMIN_EMAIL) {
    const computedDestination = "/admin";
    const finalDestination = validatedNext || computedDestination;
    return { redirect: { destination: finalDestination, permanent: false } };
  }

  async function hasSuccessfulPaymentForPlan(plan) {
    try {
      const supabaseAdmin = createClient(
        process.env.NEXT_PUBLIC_SUPABASE_URL,
        process.env.SUPABASE_SERVICE_ROLE_KEY
      );

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

  if (role === "vip") {
    const paid = await hasSuccessfulPaymentForPlan("vip");
    const computedDestination = paid
      ? "/dashboard/vip"
      : `/checkout?plan=vip&next=${encodeURIComponent("/auth/callback")}`;
    const finalDestination = validatedNext || computedDestination;
    return { redirect: { destination: finalDestination, permanent: false } };
  }

  if (role === "premium") {
    const paid = await hasSuccessfulPaymentForPlan("premium");
    const computedDestination = paid
      ? "/dashboard/premium"
      : `/checkout?plan=premium&next=${encodeURIComponent("/auth/callback")}`;
    const finalDestination = validatedNext || computedDestination;
    return { redirect: { destination: finalDestination, permanent: false } };
  }

  const computedDestination = "/dashboard";
  const finalDestination = validatedNext || computedDestination;
  return { redirect: { destination: finalDestination, permanent: false } };
};

export default function Callback() {
  return <div className="p-6 text-center">Redirecting…</div>;
}
