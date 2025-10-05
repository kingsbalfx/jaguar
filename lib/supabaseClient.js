// lib/supabaseClient.js
import { createClient } from "@supabase/supabase-js";

/**
 * ✅ Public client (for browser-side code)
 * Uses NEXT_PUBLIC_* env vars only.
 */
const PUBLIC_SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL;
const PUBLIC_SUPABASE_ANON_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

export const supabase =
  PUBLIC_SUPABASE_URL && PUBLIC_SUPABASE_ANON_KEY
    ? createClient(PUBLIC_SUPABASE_URL, PUBLIC_SUPABASE_ANON_KEY)
    : null;

/**
 * ✅ Server-side factory (for getServerSideProps or API routes)
 * Uses service role key when available.
 */
export function getSupabaseClient({ server = false } = {}) {
  const url =
    process.env.SUPABASE_URL || process.env.NEXT_PUBLIC_SUPABASE_URL;
  const serviceKey = process.env.SUPABASE_SERVICE_ROLE_KEY;
  const anonKey =
    process.env.SUPABASE_ANON_KEY || process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

  if (!url) {
    console.warn("⚠️ getSupabaseClient: Missing SUPABASE_URL.");
    return null;
  }

  const key = server ? serviceKey || anonKey : anonKey;
  if (!key) {
    console.warn("⚠️ getSupabaseClient: Missing Supabase key.");
    return null;
  }

  return createClient(url, key);
}

