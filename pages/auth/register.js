import { useEffect } from "react";
import { createClient } from "@supabase/supabase-js";
const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY,
);
export default function Register() {
  const handleGoogle = async () => {
    const { data, error } = await supabase.auth.signInWithOAuth({
      provider: "google",
      options: { redirectTo: window.location.origin + "/auth/callback" },
    });
    if (error) console.error("OAuth error", error);
    // Supabase will redirect to callback
  };
  return (
    <div className="min-h-screen p-6">
      <h2 className="text-2xl font-bold">Register with Google</h2>
      <p className="mt-2">
        Click the button below to sign in with Google (Supabase OAuth).
      </p>
      <div className="mt-4">
        <button onClick={handleGoogle} className="card px-4 py-3">
          Sign in with Google
        </button>
      </div>
    </div>
  );
}
