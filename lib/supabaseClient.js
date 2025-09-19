// lib/supabaseClient.js
import { createClient } from "@supabase/supabase-js";

/**
 * Client-side supabase instance (uses NEXT_PUBLIC_* envs).
 * This will be null if the public envs are not set (so client code can check).
 */
const publicUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || process.env.SUPABASE_URL;
const publicAnon = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || process.env.SUPABASE_ANON_KEY;

export const supabase = (publicUrl && publicAnon)
  ? createClient(publicUrl, publicAnon)
  : null;

/**
 * Factory for server-side usage. Use getSupabaseClient({ server: true })
 * in getServerSideProps, API routes, or other server-only code.
 *
 * It returns `null` if required envs are not present (so builds don't crash).
 */
export function getSupabaseClient({ server = false } = {}) {
  const url = process.env.SUPABASE_URL || process.env.NEXT_PUBLIC_SUPABASE_URL;
  const serverKey = process.env.SUPABASE_SERVICE_ROLE_KEY;
  const anonKey = process.env.SUPABASE_ANON_KEY || process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

  if (!url) {
    console.warn("getSupabaseClient: SUPABASE_URL not set.");
    return null;
  }

  const key = server ? (serverKey || anonKey) : anonKey;
  if (!key) {
    console.warn("getSupabaseClient: Supabase key not set (server or anon).");
    return null;
  }

  return createClient(url, key);
}
