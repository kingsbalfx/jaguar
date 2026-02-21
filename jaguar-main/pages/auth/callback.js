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

  // fetch profile (try anon first, fallback to service role)
  let profile = null;
  const { data: profileData, error: profileError } = await supabase
    .from("profiles")
    .select("id, role, email")
    .eq("id", user.id)
    .maybeSingle();

  if (profileError) {
    console.error("Profile fetch error:", profileError);
  }
  profile = profileData || null;

  const supabaseAdmin = getSupabaseClient({ server: true });
  if (!profile && supabaseAdmin) {
    const { data: adminProfile, error: adminErr } = await supabaseAdmin
      .from("profiles")
      .select("id, role, email")
      .eq("id", user.id)
      .maybeSingle();
    if (adminErr) console.error("Admin profile fetch error:", adminErr);
    profile = adminProfile || null;
  }

  const SUPER_ADMIN_EMAIL = (process.env.SUPER_ADMIN_EMAIL || "").toLowerCase();
  const FALLBACK_ADMIN_EMAIL = (process.env.NEXT_PUBLIC_ADMIN_EMAIL || process.env.ADMIN_EMAIL || "").toLowerCase();
  const isAdminEmail = email && (email === SUPER_ADMIN_EMAIL || email === FALLBACK_ADMIN_EMAIL);

  if (!profile) {
    if (supabaseAdmin) {
      const role = isAdminEmail ? "admin" : "user";
      const { error: insertErr } = await supabaseAdmin.from("profiles").insert([
        { id: user.id, email: user.email, role }
      ]);
      if (insertErr) {
        console.error("Profile insert error:", insertErr);
        return { redirect: { destination: "/complete-profile", permanent: false } };
      }
      profile = { id: user.id, email: user.email, role };
    } else {
      // If profile missing and no admin client, send user to complete-profile
      return { redirect: { destination: "/complete-profile", permanent: false } };
    }
  }

  const role = profile.role || "user";

  // Admin or super admin email override
  if (role === "admin" || isAdminEmail) {
    return { redirect: { destination: validatedNext || "/admin", permanent: false } };
  }

  // Use server admin client for secure payments table checks

  async function hasPaid(plan) {
    try {
      if (!supabaseAdmin) return false;
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

  if (role === "pro") {
    const paid = await hasPaid("pro");
    const dest = validatedNext || (paid ? "/dashboard/pro" : `/checkout?plan=pro&next=/auth/callback`);
    return { redirect: { destination: dest, permanent: false } };
  }

  if (role === "lifetime") {
    const paid = await hasPaid("lifetime");
    const dest = validatedNext || (paid ? "/dashboard/lifetime" : `/checkout?plan=lifetime&next=/auth/callback`);
    return { redirect: { destination: dest, permanent: false } };
  }

  // default
  return { redirect: { destination: validatedNext || "/dashboard", permanent: false } };
};

export default function Callback() {
  return (
    <div className="min-h-[calc(100vh-160px)] flex items-center justify-center bg-black text-gray-300">
      Redirecting…
    </div>
  );
}
