// pages/auth/register.js
import { useRouter } from "next/router";
import { useEffect } from "react";
import { createClient } from "@supabase/supabase-js";

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY,
);

export default function Register() {
  const router = useRouter();
  const { next } = router.query; // example: /register?next=/checkout?plan=vip

  const buildRedirectTo = () => {
    // prefer configured site URL (set it in Vercel envs)
    const site = process.env.NEXT_PUBLIC_SITE_URL || (typeof window !== "undefined" && window.location.origin) || "";
    // ensure site is defined
    if (!site) return "/auth/callback";
    // include next param if present
    const encodedNext = next ? `?next=${encodeURIComponent(String(next))}` : "";
    return `${site.replace(/\/$/, "")}/auth/callback${encodedNext}`;
  };

  const handleGoogle = async () => {
    try {
      const redirectTo = buildRedirectTo();
      // Supabase will redirect the browser to the provider and then back to redirectTo
      const { data, error } = await supabase.auth.signInWithOAuth({
        provider: "google",
        options: { redirectTo },
      });
      if (error) {
        console.error("OAuth error:", error);
        alert("Sign-in failed: " + (error.message || "check console"));
      }
      // note: in the redirect flow, the browser will be redirected — nothing further to do here
    } catch (err) {
      console.error("handleGoogle exception:", err);
      alert("Unexpected error; check console.");
    }
  };

  useEffect(() => {
    // If you want to auto-redirect already-authenticated users, you can check session here.
    // For now we keep simple: user clicks Sign-in and redirect flow begins.
  }, []);

  return (
    <div className="min-h-screen p-6">
      <h2 className="text-2xl font-bold">Register with Google</h2>
      <p className="mt-2">Click the button below to sign in with Google (Supabase OAuth).</p>

      <div className="mt-4">
        <button onClick={handleGoogle} className="card px-4 py-3">
          Sign in with Google
        </button>
      </div>
    </div>
  );
}
