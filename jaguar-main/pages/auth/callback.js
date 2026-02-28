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

function normalizeBool(value) {
  if (value === true) return true;
  if (value === "true") return true;
  if (value === 1) return true;
  if (value === "1") return true;
  return false;
}

export const getServerSideProps = async (ctx) => {
  const oauthError =
    (typeof ctx.query?.error === "string" && ctx.query.error) ||
    (typeof ctx.query?.error_description === "string" && ctx.query.error_description) ||
    (ctx.query?.status === "failed" ? "OAuth status failed" : null);

  if (oauthError) {
    return {
      redirect: {
        destination: `/login?error=${encodeURIComponent(oauthError)}`,
        permanent: false,
      },
    };
  }

  const supabase = createPagesServerClient(ctx);
  const code = typeof ctx.query?.code === "string" ? ctx.query.code : null;
  if (code) {
    try {
      await supabase.auth.exchangeCodeForSession(code);
    } catch (err) {
      console.error("OAuth code exchange failed:", err);
    }
  }
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

  const supabaseAdmin = getSupabaseClient({ server: true });
  let profile = null;
  let profileColumnsMissing = false;

  async function fetchProfile(client) {
    if (!client) return { data: null, missingColumns: false };
    let data = null;
    let missingColumns = false;
    const { data: fullData, error: fullErr } = await client
      .from("profiles")
      .select("id, role, email, name, phone, address, country, age_confirmed")
      .eq("id", user.id)
      .maybeSingle();
    if (fullErr && fullErr.code === "42703") {
      missingColumns = true;
      const { data: fallbackData, error: fallbackErr } = await client
        .from("profiles")
        .select("id, role, email, name, phone")
        .eq("id", user.id)
        .maybeSingle();
      if (fallbackErr && fallbackErr.code !== "42501") {
        console.error("Profile fetch error:", fallbackErr);
      }
      data = fallbackData || null;
    } else {
      if (fullErr && fullErr.code !== "42501") {
        console.error("Profile fetch error:", fullErr);
      }
      data = fullData || null;
    }
    return { data, missingColumns };
  }

  if (supabaseAdmin) {
    const result = await fetchProfile(supabaseAdmin);
    profile = result.data;
    profileColumnsMissing = result.missingColumns;
  }

  if (!profile) {
    const result = await fetchProfile(supabase);
    profile = result.data;
    profileColumnsMissing = profileColumnsMissing || result.missingColumns;
  }

  const SUPER_ADMIN_EMAIL = (process.env.SUPER_ADMIN_EMAIL || "").toLowerCase();
  const FALLBACK_ADMIN_EMAIL = (process.env.NEXT_PUBLIC_ADMIN_EMAIL || process.env.ADMIN_EMAIL || "").toLowerCase();
  const isAdminEmail = email && (email === SUPER_ADMIN_EMAIL || email === FALLBACK_ADMIN_EMAIL);
  const isCheckoutNext = typeof validatedNext === "string" && validatedNext.startsWith("/checkout");
  const skipProfileCompletion = Boolean(isAdminEmail || isCheckoutNext);
  const skipDestination = isAdminEmail
    ? "/admin"
    : isCheckoutNext
    ? validatedNext
    : "/dashboard";
  const metadata = user.user_metadata || {};
  const metaName = metadata.full_name || metadata.name || null;
  const metaPhone = metadata.phone || null;
  const metaAddress = metadata.address || null;
  const metaCountry = metadata.country || null;
  const metaAgeConfirmed = normalizeBool(metadata.age_confirmed);
  const hasMetaProfile = Boolean(metaName && metaPhone && metaAddress && metaCountry && metaAgeConfirmed);

  if (!profile) {
    if (supabaseAdmin && (hasMetaProfile || isAdminEmail)) {
      const role = isAdminEmail ? "admin" : "user";
      const payload = {
        id: user.id,
        email: user.email,
        role,
        name: isAdminEmail ? metaName || null : metaName,
        phone: isAdminEmail ? metaPhone || null : metaPhone,
        address: isAdminEmail ? metaAddress || null : metaAddress,
        country: isAdminEmail ? metaCountry || null : metaCountry,
        age_confirmed: isAdminEmail ? Boolean(metaAgeConfirmed) : true,
        updated_at: new Date().toISOString(),
      };

      let insertErr = null;
      try {
        const { error } = await supabaseAdmin.from("profiles").insert([payload]);
        insertErr = error || null;
      } catch (e) {
        insertErr = e;
      }

      if (insertErr && insertErr.code === "42703") {
        // Fallback to minimal columns if profile schema is missing new fields.
        const { error } = await supabaseAdmin.from("profiles").insert([
          { id: user.id, email: user.email, role },
        ]);
        insertErr = error || null;
      }

      if (insertErr) {
        console.error("Profile insert error:", insertErr);
        if (skipProfileCompletion) {
          return { redirect: { destination: validatedNext || skipDestination, permanent: false } };
        }
        return { redirect: { destination: "/complete-profile", permanent: false } };
      }
      profile = { id: user.id, email: user.email, role };
    } else {
      // If profile missing or metadata incomplete, send user to complete-profile
      if (skipProfileCompletion) {
        return { redirect: { destination: validatedNext || skipDestination, permanent: false } };
      }
      return { redirect: { destination: "/complete-profile", permanent: false } };
    }
  }

  const role = profile.role || "user";
  const effectiveRole = role === "admin" && isAdminEmail ? "admin" : role;

  const needsProfileCompletion =
    !profileColumnsMissing &&
    (!profile.name || !profile.phone || !profile.address || !profile.country || profile.age_confirmed !== true);

  if (needsProfileCompletion && !skipProfileCompletion) {
    return { redirect: { destination: "/complete-profile", permanent: false } };
  }

  if (role === "admin" && !isAdminEmail && supabaseAdmin) {
    try {
      await supabaseAdmin.from("profiles").update({ role: "user" }).eq("id", user.id);
    } catch (e) {
      console.warn("Failed to downgrade non-admin email:", e?.message || e);
    }
  }

  // Admin or super admin email override
  if (effectiveRole === "admin" || isAdminEmail) {
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

  if (effectiveRole === "vip") {
    const paid = await hasPaid("vip");
    const dest = validatedNext || (paid ? "/dashboard/vip" : `/checkout?plan=vip&next=/auth/callback`);
    return { redirect: { destination: dest, permanent: false } };
  }

  if (effectiveRole === "premium") {
    const paid = await hasPaid("premium");
    const dest = validatedNext || (paid ? "/dashboard/premium" : `/checkout?plan=premium&next=/auth/callback`);
    return { redirect: { destination: dest, permanent: false } };
  }

  if (effectiveRole === "pro") {
    const paid = await hasPaid("pro");
    const dest = validatedNext || (paid ? "/dashboard/pro" : `/checkout?plan=pro&next=/auth/callback`);
    return { redirect: { destination: dest, permanent: false } };
  }

  if (effectiveRole === "lifetime") {
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
