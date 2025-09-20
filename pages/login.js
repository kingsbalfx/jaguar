// pages/login.js
import React, { useState } from "react";
import { useRouter } from "next/router";
import { createClient } from "@supabase/supabase-js";

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
);

export default function Login() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [errMsg, setErrMsg] = useState("");

  const getBaseUrl = () => {
    // Use explicit env (production), otherwise runtime origin (preview/dev), fallback to localhost for dev
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
      const { data, error } = await supabase.auth.signInWithPassword({
        email,
        password,
      });
      if (error) throw error;
      // success — go to callback page where the server/client will route by role
      const base = getBaseUrl();
      router.push(`/auth/callback?redirectTo=${encodeURIComponent(base + "/auth/callback")}`);
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
      await supabase.auth.signInWithOAuth({
        provider: "google",
        options: { redirectTo: `${base}/auth/callback` },
      });
      // Supabase will redirect the browser to the provider and back to /auth/callback
    } catch (err) {
      setErrMsg(err?.message || "OAuth failed");
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-b from-slate-900 to-black p-6">
      <div className="w-full max-w-md bg-black/60 ring-1 ring-white/10 rounded-xl p-8 text-white">
        <h1 className="text-2xl font-bold mb-2 text-center">Welcome back</h1>
        <p className="text-sm text-gray-300 mb-6 text-center">Login to access your dashboard</p>

        {errMsg && <div className="text-red-400 mb-4 text-sm">{errMsg}</div>}

        <form onSubmit={handleEmailLogin} className="space-y-4">
          <label className="block">
            <span className="text-sm text-gray-300">Email</span>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="mt-1 w-full p-3 rounded bg-white/5 outline-none focus:ring-2 focus:ring-indigo-500"
              placeholder="you@example.com"
            />
          </label>

          <label className="block">
            <span className="text-sm text-gray-300">Password</span>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className="mt-1 w-full p-3 rounded bg-white/5 outline-none focus:ring-2 focus:ring-indigo-500"
              placeholder="Your password"
            />
          </label>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-3 bg-indigo-600 rounded text-white font-semibold hover:bg-indigo-700 disabled:opacity-60"
          >
            {loading ? "Signing in…" : "Sign in"}
          </button>
        </form>

        <div className="my-4 flex items-center gap-3">
          <hr className="flex-1 border-white/10" />
          <span className="text-xs text-gray-400">or</span>
          <hr className="flex-1 border-white/10" />
        </div>

        <button
          onClick={handleGoogle}
          className="w-full flex items-center justify-center gap-3 py-3 border border-white/10 rounded hover:bg-white/5"
        >
          <img src="/images/google.svg" alt="Google" className="w-5 h-5" />
          <span>Continue with Google</span>
        </button>

        <div className="mt-4 text-center text-sm text-gray-400">
          New here?{" "}
          <a href="/register" className="text-white underline">
            Create account
          </a>
        </div>
      </div>
    </div>
  );
}
