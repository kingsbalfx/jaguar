import { createClient } from "@supabase/supabase-js";

/**
 * ✅ Public (client-side) Supabase instance
 * Used in browser components (auth pages, dashboard, etc.)
 */
const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL;
const SUPABASE_ANON = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
export const isSupabaseConfigured = Boolean(SUPABASE_URL && SUPABASE_ANON);

export const supabase = isSupabaseConfigured
  ? createClient(SUPABASE_URL, SUPABASE_ANON)
  : null;

/**
 * ✅ Server/Admin Supabase instance factory
 * Use { server: true } when calling from getServerSideProps or API routes.
 * Automatically uses the secure SERVICE_ROLE_KEY for admin actions.
 */
export function getSupabaseClient({ server = false } = {}) {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const anon = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  const service = process.env.SUPABASE_SERVICE_ROLE_KEY;

  if (!url) {
    console.warn("Missing Supabase URL (NEXT_PUBLIC_SUPABASE_URL).");
    return null;
  }

  if (server) {
    if (!service) {
      if (!anon) {
        console.warn("Missing SUPABASE_SERVICE_ROLE_KEY and NEXT_PUBLIC_SUPABASE_ANON_KEY.");
        return null;
      }
      console.warn("Missing SUPABASE_SERVICE_ROLE_KEY — falling back to anon key (not recommended).");
      return createClient(url, anon);
    }
    return createClient(url, service);
  }

  if (!anon) {
    console.warn("Missing NEXT_PUBLIC_SUPABASE_ANON_KEY.");
    return null;
  }

  return createClient(url, anon);
}
