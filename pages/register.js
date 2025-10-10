// pages/register.js
import React, { useState } from "react";
import { useRouter } from "next/router";
import { supabase } from "../lib/supabaseClient";

export default function Register() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [errorMsg, setErrorMsg] = useState("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  // Resolve base URL like in login
  const getBaseUrl = () => {
    const envUrl = process.env.NEXT_PUBLIC_SITE_URL;
    if (envUrl) return envUrl.replace(/\/$/, "");
    if (typeof window !== "undefined" && window.location?.origin) return window.location.origin;
    return "http://localhost:3000";
  };

  // Email/password sign-up
  const handleEmailSignUp = async (e) => {
    e.preventDefault();
    setLoading(true);
    setErrorMsg("");
    try {
      const base = getBaseUrl();
      const { error } = await supabase.auth.signUp({
        email,
        password,
        options: { redirectTo: `${base}/auth/callback` }
      });
      if (error) throw error;
      // After sign-up, Supabase will send email for verification then redirect to callback.
      router.push("/auth/callback");
    } catch (err) {
      setErrorMsg(err?.message || "Sign up failed");
      setLoading(false);
    }
  };

  // Google OAuth sign-in (as part of sign-up)
  const handleGoogleSignIn = async () => {
    setLoading(true);
    setErrorMsg("");
    try {
      const base = getBaseUrl();
      const { error } = await supabase.auth.signInWithOAuth({
        provider: "google",
        options: { redirectTo: `${base}/auth/callback` }
      });
      if (error) throw error;
      // Browser will handle redirect
    } catch (err) {
      setErrorMsg(err?.message || "Google sign-in failed");
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-900 via-indigo-900 to-black p-4">
      <div className="w-full max-w-md bg-black/70 backdrop-blur-lg border border-white/10 rounded-2xl shadow-2xl p-8 text-white space-y-6">
        <h1 className="text-4xl font-bold text-center">Create an Account</h1>
        <p className="text-sm text-gray-400 text-center">
          Sign up with your email or continue with Google.
        </p>
        {errorMsg && (
          <div className="bg-red-600/40 text-red-200 text-sm p-3 rounded-md text-center">
            {errorMsg}
          </div>
        )}

        <form onSubmit={handleEmailSignUp} className="space-y-5">
          <div>
            <label className="block mb-1 text-sm text-gray-300">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              placeholder="you@example.com"
              className="w-full px-4 py-3 rounded-lg bg-white/10 placeholder-gray-500 focus:bg-white/20 focus:ring-2 focus:ring-indigo-500 outline-none transition"
            />
          </div>
          <div>
            <label className="block mb-1 text-sm text-gray-300">Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              placeholder="••••••••"
              className="w-full px-4 py-3 rounded-lg bg-white/10 placeholder-gray-500 focus:bg-white/20 focus:ring-2 focus:ring-indigo-500 outline-none transition"
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="w-full py-3 bg-indigo-600 rounded-lg font-semibold text-white hover:bg-indigo-700 disabled:opacity-60 transition"
          >
            {loading ? "Creating account…" : "Sign Up"}
          </button>
        </form>

        <div className="flex items-center gap-3 text-gray-500">
          <hr className="flex-1 border-gray-600" />
          <span className="text-xs uppercase">or</span>
          <hr className="flex-1 border-gray-600" />
        </div>

        <button
          onClick={handleGoogleSignIn}
          disabled={loading}
          className="w-full flex items-center justify-center gap-3 py-3 border border-gray-600 rounded-lg hover:bg-white/5 transition"
        >
          {/* Google icon (use react-icons or similar) */}
          <span className="text-xl"><FcGoogle /></span>
          <span>Continue with Google</span>
        </button>

        <div className="mt-4 text-center text-sm text-gray-400">
          Already have an account?{" "}
          <a href="/login" className="text-indigo-300 hover:text-indigo-200 underline">
            Sign in
          </a>
        </div>
      </div>
    </div>
  );
}