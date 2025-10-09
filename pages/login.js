// pages/login.js
import React, { useState, useEffect } from "react";
import Image from "next/image";
import { useRouter } from "next/router";
import { supabase } from "../lib/supabaseClient";

/**
 * Stylish Login page for KingsbalFX
 * - Email/password sign-in
 * - Google OAuth sign-in (redirects to /auth/callback)
 * - Animated jaguar logo reveal
 */

export default function Login() {
  const router = useRouter();
  const { next } = router.query;

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [errMsg, setErrMsg] = useState("");

  // Resolve base URL (production env first, then runtime)
  const getBaseUrl = () => {
    const envUrl = process.env.NEXT_PUBLIC_SITE_URL;
    if (envUrl) return envUrl.replace(/\/$/, "");
    if (typeof window !== "undefined" && window.location?.origin) return window.location.origin;
    return "http://localhost:3000";
  };

  // When email login succeeds we redirect to /auth/callback which will route by role
  const handleEmailLogin = async (e) => {
    e.preventDefault();
    setErrMsg("");
    setLoading(true);

    try {
      const { error } = await supabase.auth.signInWithPassword({
        email,
        password,
      });

      if (error) throw error;

      // include next param if present (so callback can resume)
      const nextParam = next ? `?next=${encodeURIComponent(next)}` : "";
      router.push(`/auth/callback${nextParam}`);
    } catch (err) {
      setErrMsg(err?.message || "Login failed. Check credentials and try again.");
      setLoading(false);
    }
  };

  const handleGoogle = async () => {
    setErrMsg("");
    setLoading(true);
    try {
      const base = getBaseUrl();
      const redirectTo = next ? `${base}/auth/callback?next=${encodeURIComponent(next)}` : `${base}/auth/callback`;

      const { error } = await supabase.auth.signInWithOAuth({
        provider: "google",
        options: { redirectTo },
      });

      if (error) throw error;

      // Supabase will redirect the browser to Google and then back to /auth/callback
    } catch (err) {
      setErrMsg(err?.message || "Google sign-in failed");
      setLoading(false);
    }
  };

  // small sanity: if user already signed in, go to callback immediately
  useEffect(() => {
    (async () => {
      try {
        const { data } = await supabase.auth.getSession();
        if (data?.session?.user) {
          const nextParam = next ? `?next=${encodeURIComponent(next)}` : "";
          router.replace(`/auth/callback${nextParam}`);
        }
      } catch {
        // ignore
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-900 via-black to-indigo-900 p-6">
      <div className="max-w-md w-full bg-black/60 ring-1 ring-white/10 rounded-2xl p-8 text-white shadow-2xl backdrop-blur">
        {/* Logo + title */}
        <div className="flex items-center justify-center mb-6">
          <div className="relative w-20 h-20 mr-4">
            {/* Using next/image - ensure /public/jaguar.png exists */}
            <Image
              src="/jaguar.png"
              alt="KingsbalFX Jaguar"
              layout="fill"
              objectFit="contain"
              className="transform transition-transform duration-700 ease-out scale-90 opacity-0 animate-logo-reveal"
            />
          </div>
          <div>
            <h1 className="text-2xl md:text-3xl font-extrabold tracking-tight">KINGSBALFX</h1>
            <p className="text-xs text-gray-300">Trade smart • Live smart</p>
          </div>
        </div>

        {/* Animated keyframes for logo reveal (Tailwind won't have it built-in here so inline style class used) */}
        <style jsx>{`
          @keyframes logoReveal {
            0% { transform: scale(0.85); opacity: 0; filter: blur(6px); }
            60% { transform: scale(1.02); opacity: 1; filter: blur(0); }
            100% { transform: scale(1); opacity: 1; filter: blur(0); }
          }
          .animate-logo-reveal {
            animation: logoReveal 900ms cubic-bezier(.2,.9,.3,1) forwards;
          }
        `}</style>

        {/* Subtitle */}
        <p className="text-sm text-gray-400 mb-4 text-center">Sign in to access your dashboard</p>

        {errMsg && (
          <div className="mb-4 text-sm bg-red-700/30 text-red-200 px-4 py-2 rounded">
            {errMsg}
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleEmailLogin} className="space-y-4">
          <label className="block">
            <span className="text-xs text-gray-300">Email</span>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              placeholder="you@example.com"
              className="mt-1 w-full bg-white/5 px-4 py-3 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 transition"
            />
          </label>

          <label className="block">
            <span className="text-xs text-gray-300">Password</span>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              placeholder="Your password"
              className="mt-1 w-full bg-white/5 px-4 py-3 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 transition"
            />
          </label>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-3 rounded-lg bg-gradient-to-r from-emerald-500 to-lime-400 text-black font-semibold hover:from-emerald-600 hover:to-lime-300 disabled:opacity-60 transition transform hover:-translate-y-0.5"
          >
            {loading ? "Signing in…" : "Sign in"}
          </button>
        </form>

        {/* separator */}
        <div className="my-4 flex items-center gap-3">
          <hr className="flex-1 border-white/10" />
          <span className="text-xs text-gray-400">or</span>
          <hr className="flex-1 border-white/10" />
        </div>

        {/* Google */}
        <button
          onClick={handleGoogle}
          disabled={loading}
          className="w-full flex items-center justify-center gap-3 py-3 border border-white/10 rounded-lg hover:bg-white/5 transition"
        >
          <svg className="w-5 h-5" viewBox="0 0 533.5 544.3" xmlns="http://www.w3.org/2000/svg">
            <path fill="#4285F4" d="M533.5 278.4c0-17.4-1.6-34.1-4.6-50.4H272v95.4h147.5c-6.4 34.9-25.9 64.4-55.2 84.1v69h89c52.3-48.2 82.2-119.3 82.2-197.1z"/>
            <path fill="#34A853" d="M272 544.3c73.6 0 135.5-24.5 180.7-66.5l-89-69c-25 17-57 27-91.7 27-70.6 0-130.3-47.6-151.7-111.2h-90v69.9C63.7 481 160.6 544.3 272 544.3z"/>
            <path fill="#FBBC05" d="M120.3 324.6c-8.8-26.6-8.8-55.2 0-81.8v-69.9h-90C6.6 229.9 0 252.7 0 278.4s6.6 48.6 30.3 105.5l90-69.3z"/>
            <path fill="#EA4335" d="M272 109.6c39.9 0 75.8 13.7 104 40.6l78-78C404.6 24.5 342.7 0 272 0 160.6 0 63.7 63.4 30.3 153.8l90 69.9C141.7 157.2 201.4 109.6 272 109.6z"/>
          </svg>
          Continue with Google
        </button>

        <div className="mt-4 text-center text-sm text-gray-400">
          New here?{" "}
          <a href="/register" className="text-indigo-300 hover:text-indigo-200 underline">
            Create account
          </a>
        </div>
      </div>
    </div>
  );
}