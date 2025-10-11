// pages/login.js
import React, { useState, useEffect } from "react";
import { useRouter } from "next/router";
import { supabase } from "../lib/supabaseClient";
import Image from "next/image";

export default function Login() {
  const router = useRouter();
  const { next } = router.query;

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [errMsg, setErrMsg] = useState("");

  const getBaseUrl = () => {
    const envUrl = process.env.NEXT_PUBLIC_SITE_URL;
    if (envUrl) return envUrl.replace(/\/$/, "");
    if (typeof window !== "undefined" && window.location?.origin)
      return window.location.origin;
    return "http://localhost:3000";
  };

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
      const nextParam = next ? `?next=${encodeURIComponent(next)}` : "";
      router.push(`/auth/callback${nextParam}`);
    } catch (err) {
      setErrMsg(err?.message || "Login failed. Check credentials.");
      setLoading(false);
    }
  };

  const handleGoogle = async () => {
    setErrMsg("");
    setLoading(true);
    try {
      const base = getBaseUrl();
      const redirectTo = next
        ? `${base}/auth/callback?next=${encodeURIComponent(next)}`
        : `${base}/auth/callback`;

      const { error } = await supabase.auth.signInWithOAuth({
        provider: "google",
        options: { redirectTo },
      });
      if (error) throw error;
      // Browser is redirected automatically
    } catch (err) {
      setErrMsg(err?.message || "Google sign-in failed");
      setLoading(false);
    }
  };

  useEffect(() => {
    (async () => {
      const { data } = await supabase.auth.getSession();
      if (data?.session?.user) {
        const nextParam = next ? `?next=${encodeURIComponent(next)}` : "";
        router.replace(`/auth/callback${nextParam}`);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-900 via-black to-indigo-900 p-6">
      <div className="max-w-md w-full bg-black/60 ring-1 ring-white/10 rounded-2xl p-8 text-white shadow-2xl backdrop-blur-lg">
        <div className="flex flex-col items-center mb-6">
          <Image
            src="/jaguar.png"
            alt="KingsbalFX Jaguar"
            width={80}
            height={80}
            className="transform transition-transform duration-700 ease-out scale-90 opacity-0 animate-logo-reveal"
          />
          <h1 className="text-3xl font-extrabold tracking-tight mt-4">KINGSBALFX</h1>
          <p className="text-xs text-gray-300 mt-1">Trade smart • Live smart</p>
        </div>
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

        {errMsg && (
          <div className="mb-4 text-sm bg-red-700/30 text-red-200 px-4 py-2 rounded">
            {errMsg}
          </div>
        )}

        <form onSubmit={handleEmailLogin} className="space-y-4">
          <div>
            <label className="block text-xs text-gray-300">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              placeholder="you@example.com"
              className="mt-1 w-full bg-white/5 px-4 py-3 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 transition"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-300">Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              placeholder="••••••••"
              className="mt-1 w-full bg-white/5 px-4 py-3 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 transition"
            />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="w-full py-3 rounded-lg bg-gradient-to-r from-emerald-500 to-lime-400 text-black font-semibold hover:from-emerald-600 hover:to-lime-300 disabled:opacity-60 transition transform hover:-translate-y-0.5"
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
          disabled={loading}
          className="w-full flex items-center justify-center gap-3 py-3 border border-white/10 rounded-lg hover:bg-white/5 transition"
        >
          <svg className="w-5 h-5" viewBox="0 0 533.5 544.3">
            {/* SVG paths */}
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