import { createClient } from "@supabase/supabase-js";

/**
 * ✅ Public (client-side) Supabase instance
 * Used in browser components (auth pages, dashboard, etc.)
 */
export const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
);

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
    throw new Error("❌ Missing Supabase URL (NEXT_PUBLIC_SUPABASE_URL). Check your environment variables.");
  }

  if (server) {
    if (!service) {
      console.warn("⚠️ Missing SUPABASE_SERVICE_ROLE_KEY — falling back to anon key (not recommended).");
      return createClient(url, anon);
    }
    return createClient(url, service);
  }

  if (!anon) {
    throw new Error("❌ Missing NEXT_PUBLIC_SUPABASE_ANON_KEY. Check your environment variables.");
  }

  return createClient(url, anon);
}