import { createPagesServerClient } from "@supabase/auth-helpers-nextjs";
import { getSupabaseClient } from "./supabaseClient.js";

/**
 * Shared API-route authentication used by the MT5 sync endpoints.
 * Mirrors the pattern already used in pages/api/bot/account-float.js and
 * pages/api/admin/mt5-credentials.js: session -> profile role -> admin email allow-list.
 */

/** Admin emails configured through any of the supported env vars. */
export function adminEmailAllowList() {
  return [process.env.SUPER_ADMIN_EMAIL, process.env.NEXT_PUBLIC_ADMIN_EMAIL, process.env.ADMIN_EMAIL]
    .map((value) => String(value || "").trim().toLowerCase())
    .filter(Boolean);
}

export function isAdminEmail(email) {
  const normalized = String(email || "").trim().toLowerCase();
  return Boolean(normalized) && adminEmailAllowList().includes(normalized);
}

/**
 * Resolve the caller of an API route.
 *
 * @returns {Promise<{ok:true, session:object, supabaseAdmin:object, role:string, isAdmin:boolean, email:string}
 *   | {ok:false, status:number, error:string}>}
 */
export async function authenticateRequest(req, res) {
  const supabase = createPagesServerClient({ req, res });
  const {
    data: { session },
  } = await supabase.auth.getSession();
  if (!session?.user) return { ok: false, status: 401, error: "not authenticated" };

  const supabaseAdmin = getSupabaseClient({ server: true });
  if (!supabaseAdmin) return { ok: false, status: 500, error: "Supabase admin client not configured" };

  const { data: profile } = await supabaseAdmin
    .from("profiles")
    .select("role")
    .eq("id", session.user.id)
    .maybeSingle();

  const storedRole = String(profile?.role || "user").toLowerCase();
  const adminByEmail = isAdminEmail(session.user.email);

  if (adminByEmail && storedRole !== "admin") {
    try {
      await supabaseAdmin.from("profiles").update({ role: "admin" }).eq("id", session.user.id);
    } catch {
      // email allow-list still grants admin access even if the profile update fails
    }
  }

  return {
    ok: true,
    session,
    supabaseAdmin,
    role: adminByEmail ? "admin" : storedRole,
    isAdmin: adminByEmail || storedRole === "admin",
    email: String(session.user.email || ""),
  };
}

/** Convenience guard for handlers that require an authenticated administrator. */
export async function requireAdmin(req, res) {
  const auth = await authenticateRequest(req, res);
  if (!auth.ok) return auth;
  if (!auth.isAdmin) return { ok: false, status: 403, error: "forbidden" };
  return auth;
}


/** Small helper to normalise query params into a positive integer. */
export function toPositiveInt(value, fallback, { min = 1, max = Number.MAX_SAFE_INTEGER } = {}) {
  const numeric = Number.parseInt(String(value ?? ""), 10);
  if (!Number.isFinite(numeric)) return fallback;
  return Math.min(Math.max(numeric, min), max);
}
