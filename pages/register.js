// pages/register.js
import { useState } from "react";
import { useRouter } from "next/router";
import { createClient } from "@supabase/supabase-js";
import { FcGoogle } from "react-icons/fc";

// Initialize Supabase client
const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
);

export default function Register() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [errorMsg, setErrorMsg] = useState("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  // Get base URL: use production env first, fallback to window or localhost
  const getBaseUrl = () => {
    const envUrl = process.env.NEXT_PUBLIC_SITE_URL;
    if (envUrl) return envUrl.replace(/\/$/, "");
    if (typeof window !== "undefined" && window.location?.origin)
      return window.location.origin;
    return "http://localhost:3000";
  };

  // Handle email/password signup
  const handleEmailSignUp = async (e) => {
    e.preventDefault();
    setLoading(true);
    setErrorMsg("");
    try {
      const { data, error } = await supabase.auth.signUp({
        email,
        password,
      });
      if (error) throw error;
      // After signup, redirect via callback
      const base = getBaseUrl();
      router.push(`${base}/auth/callback`);
    } catch (err) {
      setErrorMsg(err.message || "Sign up failed");
    } finally {
      setLoading(false);
    }
  };

  // Handle Google OAuth sign-in
  const handleGoogleSignIn = async () => {
    setLoading(true);
    setErrorMsg("");
    try {
      const base = getBaseUrl();
      const { error } = await supabase.auth.signInWithOAuth({
        provider: "google",
        options: {
          redirectTo: `${base}/auth/callback`,
        },
      });
      if (error) throw error;
      // The OAuth flow will lead back to callback
    } catch (err) {
      setErrorMsg(err.message || "Google sign-in failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-b from-slate-800 to-black p-6">
      <div className="w-full max-w-md bg-black/70 ring-1 ring-white/20 rounded-2xl p-8 text-white space-y-6">
        <h1 className="text-3xl font-bold text-center">Create an Account</h1>

        {errorMsg && (
          <div className="text-red-400 text-sm text-center">{errorMsg}</div>
        )}

        <form onSubmit={handleEmailSignUp} className="space-y-4">
          <div>
            <label className="block text-sm text-gray-300">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              required
              className="mt-1 w-full p-3 rounded-lg bg-white/10 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>

          <div>
            <label className="block text-sm text-gray-300">Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              required
              className="mt-1 w-full p-3 rounded-lg bg-white/10 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-3 bg-indigo-600 rounded-lg font-semibold hover:bg-indigo-700 disabled:opacity-60"
          >
            {loading ? "Signing up…" : "Sign Up"}
          </button>
        </form>

        <div className="flex items-center gap-3">
          <hr className="flex-1 border-gray-600" />
          <span className="text-sm text-gray-400">or</span>
          <hr className="flex-1 border-gray-600" />
        </div>

        <button
          onClick={handleGoogleSignIn}
          disabled={loading}
          className="w-full flex items-center justify-center gap-3 py-3 border-2 border-white/30 rounded-lg hover:bg-white/10"
        >
          <FcGoogle size={24} />
          <span>Continue with Google</span>
        </button>

        <div className="text-center text-sm text-gray-400">
          Already have an account?{" "}
          <a href="/login" className="underline text-white">
            Sign in
          </a>
        </div>

        {/* Price section */}
        <div className="mt-6 border-t border-gray-600 pt-4 space-y-4">
          <div className="text-center text-gray-300">Choose your plan:</div>
          <div className="flex justify-around">
            <div className="p-4 bg-gray-800 rounded-lg">
              <div className="text-lg font-semibold text-yellow-300">VIP</div>
              <div className="mt-1 text-lg text-white">₦150,000</div>
            </div>
            <div className="p-4 bg-gray-800 rounded-lg">
              <div className="text-lg font-semibold text-yellow-300">Premium</div>
              <div className="mt-1 text-lg text-white">₦90,000</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
