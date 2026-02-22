import { createClient } from "@supabase/supabase-js";
import { createPagesBrowserClient } from "@supabase/auth-helpers-nextjs";

/**
 * Public (client-side) Supabase instance
 * Used in browser components (auth pages, dashboard, etc.)
 */
const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL;
const SUPABASE_ANON = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
export const isSupabaseConfigured = Boolean(SUPABASE_URL && SUPABASE_ANON);

let browserClient = null;

/**
 * Browser client (uses auth-helpers to set cookies for SSR)
 */
export function getBrowserSupabaseClient() {
  if (!isSupabaseConfigured) return null;
  if (typeof window === "undefined") return null;
  if (!browserClient) {
    browserClient = createPagesBrowserClient({
      supabaseUrl: SUPABASE_URL,
      supabaseKey: SUPABASE_ANON,
    });
  }
  return browserClient;
}

// Keep legacy export for components that import { supabase }
export const supabase = typeof window !== "undefined" ? getBrowserSupabaseClient() : null;

/**
 * Server/Admin Supabase instance factory
 * Use { server: true } when calling from getServerSideProps or API routes.
 * Requires SUPABASE_SERVICE_ROLE_KEY set as a server-only environment variable.
 */
export function getSupabaseClient({ server = false } = {}) {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const anon = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  const service = process.env.SUPABASE_SERVICE_ROLE_KEY || process.env.SUPABASE_SERVICE_KEY;

  if (!url) {
    console.warn("Missing Supabase URL (NEXT_PUBLIC_SUPABASE_URL).");
    return null;
  }

  if (server) {
    if (!service) {
      console.warn("Missing SUPABASE_SERVICE_ROLE_KEY. Set it as a server-only env var.");
      return null;
    }
    return createClient(url, service);
  }

  if (!anon) {
    console.warn("Missing NEXT_PUBLIC_SUPABASE_ANON_KEY.");
    return null;
  }

  return createClient(url, anon);
}
