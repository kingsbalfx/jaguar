// pages/auth/callback.js
import React from "react";
import { createPagesServerClient } from "@supabase/auth-helpers-nextjs";
import { getSupabaseClient } from "../../lib/supabaseClient";

/**
 * Validate `next` param (avoid open redirect)
 */
function safeNextParam(rawNext) {
  if (!rawNext) return null;
  try {
    const decoded = decodeURIComponent(String(rawNext));
    if (decoded.startsWith("/") && !decoded.startsWith("//")) return decoded;
  } catch {}
  return null;
}

export const getServerSideProps = async (ctx) => {
  const supabase = createPagesServerClient(ctx);
  // try to get session (server-side)
  const { data: { session }, error: sessionError } = await supabase.auth.getSession();

  if (sessionError || !session?.user) {
    // Not signed in: redirect to login (preserve next)
    const rawNext = ctx.query.next ?? null;
    const next = safeNextParam(rawNext);
    const dest = next ? `/login?next=${encodeURIComponent(next)}` : "/login";
    return { redirect: { destination: dest, permanent: false } };
  }

  const user = session.user;
  const email = (user.email || "").toLowerCase();
  const rawNext = ctx.query.next ?? ctx.query.redirectTo ?? null;
  const validatedNext = safeNextParam(rawNext);

  // fetch profile
  const { data: profile, error: profileError } = await supabase
    .from("profiles")
    .select("id, role, email")
    .eq("id", user.id)
    .maybeSingle();

  if (profileError) {
    console.error("Profile fetch error:", profileError);
  }

  if (!profile) {
    // If profile missing, send user to complete-profile (you can create that page)
    return { redirect: { destination: "/complete-profile", permanent: false } };
  }

  const SUPER_ADMIN_EMAIL = (process.env.SUPER_ADMIN_EMAIL || "").toLowerCase();
  const role = profile.role || "user";

  // Admin or super admin email override
  if (role === "admin" || email === SUPER_ADMIN_EMAIL) {
    return { redirect: { destination: validatedNext || "/admin", permanent: false } };
  }

  // Use server admin client for secure payments table checks
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
      if (error) {
        console.error("hasPaid error:", error);
        return false;
      }
      return Array.isArray(data) && data.length > 0;
    } catch (e) {
      console.error("hasPaid exception:", e);
      return false;
    }
  }

  if (role === "vip") {
    const paid = await hasPaid("vip");
    const dest = validatedNext || (paid ? "/dashboard/vip" : `/checkout?plan=vip&next=/auth/callback`);
    return { redirect: { destination: dest, permanent: false } };
  }

  if (role === "premium") {
    const paid = await hasPaid("premium");
    const dest = validatedNext || (paid ? "/dashboard/premium" : `/checkout?plan=premium&next=/auth/callback`);
    return { redirect: { destination: dest, permanent: false } };
  }

  // default
  return { redirect: { destination: validatedNext || "/dashboard", permanent: false } };
};

export default function Callback() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-black text-gray-300">
      Redirecting…
    </div>
  );
}