// pages/login.js
import React, { useState } from "react";
import { useRouter } from "next/router";
import { supabase } from "../lib/supabaseClient"; // use your shared client import

export default function Login() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [errMsg, setErrMsg] = useState("");

  const getBaseUrl = () => {
    const envUrl = process.env.NEXT_PUBLIC_SITE_URL;
    if (envUrl) return envUrl.replace(/\/$/, "");
    if (typeof window !== "undefined" && window.location?.origin) return window.location.origin;
    return "http://localhost:3000";
  };

  const handleEmailLogin = async (e) => {
    e.preventDefault();
    setLoading(true);
    setErrMsg("");
    try {
      const { error } = await supabase.auth.signInWithPassword({
        email,
        password,
      });
      if (error) throw error;
      const base = getBaseUrl();
      router.push(`/auth/callback?next=${encodeURIComponent(base + "/dashboard")}`);
    } catch (err) {
      setErrMsg(err?.message || "Login failed");
    } finally {
      setLoading(false);
    }
  };

  const handleGoogle = async () => {
    setLoading(true);
    setErrMsg("");
    try {
      const base = getBaseUrl();
      const { error } = await supabase.auth.signInWithOAuth({
        provider: "google",
        options: { redirectTo: `${base}/auth/callback` },
      });
      if (error) throw error;
    } catch (err) {
      setErrMsg(err?.message || "OAuth failed");
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-indigo-900 via-black to-gray-900 p-4">
      <div className="w-full max-w-md bg-black/70 backdrop-blur-lg ring-1 ring-white/20 rounded-2xl p-8 text-white shadow-lg">
        <h1 className="text-3xl font-bold mb-4 text-center">Sign In</h1>
        <p className="text-sm text-gray-400 mb-6 text-center">
          Welcome back — login to your account
        </p>

        {errMsg && (
          <div className="bg-red-600 bg-opacity-50 text-red-200 px-4 py-2 rounded mb-4">
            {errMsg}
          </div>
        )}

        <form onSubmit={handleEmailLogin} className="space-y-4">
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
            {loading ? "Signing in…" : "Sign In"}
          </button>
        </form>

        <div className="my-6 flex items-center gap-3 text-gray-500">
          <hr className="flex-1 border-gray-600" />
          <span className="text-xs">OR</span>
          <hr className="flex-1 border-gray-600" />
        </div>

        <button
          onClick={handleGoogle}
          disabled={loading}
          className="w-full flex items-center justify-center gap-3 py-3 border border-gray-500 rounded-lg hover:bg-white/10 transition"
        >
          <img src="/images/google.svg" alt="Google" className="w-5 h-5" />
          Continue with Google
        </button>

        <div className="mt-6 text-center text-sm text-gray-400">
          Don’t have an account?{" "}
          <a href="/register" className="text-indigo-400 hover:underline">
            Register
          </a>
        </div>
      </div>
    </div>
  );
}
