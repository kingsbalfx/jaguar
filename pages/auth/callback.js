import React from "react";
import { createPagesServerClient } from "@supabase/auth-helpers-nextjs";
import { getSupabaseClient } from "../../lib/supabaseClient";

/**
 * Supabase Auth Callback
 * -----------------------
 * - Validates user session and profile.
 * - Auto-redirects based on user role.
 * - Uses SUPER_ADMIN_EMAIL override.
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
  const {
    data: { session },
    error: sessionError,
  } = await supabase.auth.getSession();

  if (sessionError || !session?.user) {
    console.error("Session error:", sessionError);
    return { redirect: { destination: "/login", permanent: false } };
  }

  const user = session.user;
  const email = user.email?.toLowerCase() || "";
  const rawNext = ctx.query?.next ?? ctx.query?.redirectTo ?? null;
  const validatedNext = safeNextParam(rawNext);

  const { data: profile, error: profileError } = await supabase
    .from("profiles")
    .select("*")
    .eq("id", user.id)
    .maybeSingle();

  if (profileError) console.error("Profile fetch error:", profileError);

  const SUPER_ADMIN_EMAIL = (process.env.SUPER_ADMIN_EMAIL || "").toLowerCase();
  const role = profile?.role || "user";

  if (!profile) {
    return { redirect: { destination: "/complete-profile", permanent: false } };
  }

  if (role === "admin" || email === SUPER_ADMIN_EMAIL) {
    return { redirect: { destination: validatedNext || "/admin", permanent: false } };
  }

  const supabaseAdmin = getSupabaseClient({ server: true });

  async function hasPaid(plan) {
    try {
      const { data, error } = await supabaseAdmin
        .from("payments")
        .select("id")
        .eq("user_id", user.id)
        .eq("plan", plan)
        .eq("status", "success")
        .limit(1);
      if (error) return false;
      return Array.isArray(data) && data.length > 0;
    } catch {
      return false;
    }
  }

  if (role === "vip") {
    const paid = await hasPaid("vip");
    return {
      redirect: {
        destination: validatedNext || (paid ? "/dashboard/vip" : `/checkout?plan=vip&next=/auth/callback`),
        permanent: false,
      },
    };
  }

  if (role === "premium") {
    const paid = await hasPaid("premium");
    return {
      redirect: {
        destination: validatedNext || (paid ? "/dashboard/premium" : `/checkout?plan=premium&next=/auth/callback`),
        permanent: false,
      },
    };
  }

  return { redirect: { destination: validatedNext || "/dashboard", permanent: false } };
};

export default function Callback() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-black text-gray-300 text-lg">
      Redirecting…
    </div>
  );
}
