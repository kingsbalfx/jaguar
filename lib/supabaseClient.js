// lib/supabaseClient.js
import { createClient } from "@supabase/supabase-js";

/**
 * Public (browser) client
 * Use NEXT_PUBLIC_... variables for client usage
 */
const PUBLIC_URL = process.env.NEXT_PUBLIC_SUPABASE_URL;
const PUBLIC_ANON = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

export const supabase = PUBLIC_URL && PUBLIC_ANON
  ? createClient(PUBLIC_URL, PUBLIC_ANON)
  : null;

/**
 * Server-side / admin client factory.
 * Pass { server: true } to get a client using the SERVICE_ROLE_KEY.
 * If SERVICE_ROLE_KEY is missing, falls back to anon key (not recommended).
 */
export function getSupabaseClient({ server = false } = {}) {
  const url = process.env.SUPABASE_URL || process.env.NEXT_PUBLIC_SUPABASE_URL;
  const serviceRole = process.env.SUPABASE_SERVICE_ROLE_KEY;
  const anon = process.env.SUPABASE_ANON_KEY || process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

  if (!url) {
    throw new Error("Supabase URL is not configured (SUPABASE_URL or NEXT_PUBLIC_SUPABASE_URL).");
  }

  if (server) {
    if (!serviceRole) {
      console.warn("SUPABASE_SERVICE_ROLE_KEY not found. Falling back to anon key (not secure).");
      if (!anon) throw new Error("No Supabase key available for server.");
      return createClient(url, anon);
    }
    return createClient(url, serviceRole);
  }

  if (!anon) {
    throw new Error("Client anon key missing (NEXT_PUBLIC_SUPABASE_ANON_KEY).");
  }
  return createClient(url, anon);
}