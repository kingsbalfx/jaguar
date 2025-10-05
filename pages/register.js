// pages/register.js
import React, { useState } from "react";
import { useRouter } from "next/router";
import { supabase } from "../lib/supabaseClient";
import { FcGoogle } from "react-icons/fc";

export default function Register() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [errorMsg, setErrorMsg] = useState("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  const getBaseUrl = () => {
    const envUrl = process.env.NEXT_PUBLIC_SITE_URL;
    if (envUrl) return envUrl.replace(/\/$/, "");
    if (typeof window !== "undefined" && window.location?.origin) return window.location.origin;
    return "http://localhost:3000";
  };

  const handleEmailSignUp = async (e) => {
    e.preventDefault();
    setLoading(true);
    setErrorMsg("");
    try {
      const { error } = await supabase.auth.signUp({
        email,
        password,
      });
      if (error) throw error;
      const base = getBaseUrl();
      router.push(`${base}/auth/callback`);
    } catch (err) {
      setErrorMsg(err?.message || "Sign up failed");
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleSignIn = async () => {
    setLoading(true);
    setErrorMsg("");
    try {
      const base = getBaseUrl();
      const { error } = await supabase.auth.signInWithOAuth({
        provider: "google",
        options: { redirectTo: `${base}/auth/callback` },
      });
      if (error) throw error;
    } catch (err) {
      setErrorMsg(err?.message || "Google sign-in failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-gray-900 via-indigo-900 to-black p-4">
      <div className="w-full max-w-md bg-black/70 backdrop-blur-lg ring-1 ring-white/20 rounded-2xl p-8 text-white shadow-lg space-y-6">
        <h1 className="text-3xl font-bold text-center">Register</h1>
        <p className="text-sm text-gray-400 text-center">Create your account below.</p>

        {errorMsg && (
          <div className="bg-red-600 bg-opacity-50 text-red-200 px-4 py-2 rounded">
            {errorMsg}
          </div>
        )}

        <form onSubmit={handleEmailSignUp} className="space-y-4">
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
            className="w-full py-3 bg-indigo-600 rounded-lg font-semibold hover:bg-indigo-700 disabled:opacity-60 transition"
          >
            {loading ? "Signing up…" : "Sign Up"}
          </button>
        </form>

        <div className="flex items-center gap-3 text-gray-500">
          <hr className="flex-1 border-gray-600" />
          <span className="text-xs">OR</span>
          <hr className="flex-1 border-gray-600" />
        </div>

        <button
          onClick={handleGoogleSignIn}
          disabled={loading}
          className="w-full flex items-center justify-center gap-3 py-3 border border-gray-500 rounded-lg hover:bg-white/10 transition"
        >
          <FcGoogle size={24} />
          Sign in with Google
        </button>

        <div className="text-center text-sm text-gray-400">
          Already have an account?{" "}
          <a href="/login" className="underline text-indigo-400">
            Sign in
          </a>
        </div>
      </div>
    </div>
  );
}
