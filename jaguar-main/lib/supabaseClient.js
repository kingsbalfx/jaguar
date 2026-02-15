import { createClient } from "@supabase/supabase-js";

/**
 * ✅ Public (client-side) Supabase instance
 * Used in browser components (auth pages, dashboard, etc.)
 * Lazily initialized when needed
 */
let supabaseInstance = null;

export function getSupabase() {
  if (!supabaseInstance) {
    const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
    const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
    
    if (!url || !key) {
      console.warn("⚠️ Supabase credentials not available yet");
      return null;
    }
    
    supabaseInstance = createClient(url, key);
  }
  return supabaseInstance;
}

// Export for backward compatibility
export const supabase = new Proxy(
  {},
  {
    get(target, prop) {
      const instance = getSupabase();
      if (!instance) {
        throw new Error("❌ Supabase not initialized. Check your environment variables.");
      }
      return instance[prop];
    },
  }
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