// pages/login.js
import React, { useState, useEffect } from "react";
import { useRouter } from "next/router";
import Image from "next/image";
import { supabase } from "../lib/supabaseClient";

export default function Login() {
  const router = useRouter();
  const { next } = router.query;

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // ✅ Determine base URL dynamically
  const base = process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000";

  // ✅ Email + Password Login
  const handleEmailLogin = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const { error } = await supabase.auth.signInWithPassword({ email, password });
      if (error) throw error;

      const nextParam = next ? `?next=${encodeURIComponent(next)}` : "";
      router.push(`/auth/callback${nextParam}`);
    } catch (err) {
      setError(err.message || "Login failed. Please check your credentials.");
      setLoading(false);
    }
  };

  // ✅ Google OAuth Login
  const handleGoogleLogin = async () => {
    setError("");
    setLoading(true);
    try {
      const redirectTo = next
        ? `${base}/auth/callback?next=${encodeURIComponent(next)}`
        : `${base}/auth/callback`;

      const { error } = await supabase.auth.signInWithOAuth({
        provider: "google",
        options: { redirectTo },
      });
      if (error) throw error;
      // Redirect handled by Supabase
    } catch (err) {
      setError(err.message || "Google login failed");
      setLoading(false);
    }
  };

  // ✅ If already logged in, go to callback
  useEffect(() => {
    (async () => {
      const { data } = await supabase.auth.getSession();
      if (data?.session?.user) {
        const nextParam = next ? `?next=${encodeURIComponent(next)}` : "";
        router.replace(`/auth/callback${nextParam}`);
      }
    })();
  }, [next, router]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-gray-900 via-black to-indigo-900 text-white px-6">
      <div className="max-w-md w-full bg-black/70 border border-white/10 backdrop-blur-xl rounded-2xl shadow-2xl p-8">
        <div className="flex flex-col items-center mb-6">
          <Image src="/jaguar.png" alt="logo" width={80} height={80} />
          <h1 className="text-2xl font-bold mt-3">KINGSBALFX</h1>
          <p className="text-xs text-gray-400">Forex • Mentorship • Premium Access</p>
        </div>

        {error && <p className="text-red-400 mb-4">{error}</p>}

        <form onSubmit={handleEmailLogin} className="space-y-4">
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@example.com"
            className="w-full px-4 py-3 rounded-lg bg-white/10 placeholder-gray-400 focus:bg-white/20 focus:ring-2 focus:ring-indigo-500 outline-none transition"
            required
          />
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Your password"
            className="w-full px-4 py-3 rounded-lg bg-white/10 placeholder-gray-400 focus:bg-white/20 focus:ring-2 focus:ring-indigo-500 outline-none transition"
            required
          />
          <button
            type="submit"
            disabled={loading}
            className="w-full py-3 bg-indigo-600 rounded-lg font-semibold hover:bg-indigo-700 disabled:opacity-60 transition"
          >
            {loading ? "Signing in..." : "Sign in"}
          </button>
        </form>

        <div className="mt-4 flex items-center gap-3">
          <hr className="flex-1 border-white/10" />
          <span className="text-xs text-gray-400">or</span>
          <hr className="flex-1 border-white/10" />
        </div>

        <button
          onClick={handleGoogleLogin}
          disabled={loading}
          className="w-full py-3 mt-2 bg-white/10 border border-white/20 rounded-lg hover:bg-white/20 flex items-center justify-center gap-2"
        >
          <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor">
            <path d="M21.35 11.1H12v2.8h5.3c-.2 1.2-.9 2.3-1.9 3l2.9 2.3c1.7-1.6 2.7-4 2.7-6.6 0-.6-.1-1.3-.2-1.9z" />
            <path d="M12 22c2.6 0 4.8-.9 6.4-2.4l-2.9-2.3c-.8.6-1.8 1-3.5 1-2.7 0-5-1.8-5.8-4.3H3.2v2.6C4.8 19.5 8.1 22 12 22z" />
            <path d="M6.2 13.9c-.2-.6-.3-1.2-.3-1.9s.1-1.3.3-1.9V7.5H3.2A9.8 9.8 0 0 0 2 12c0 1.5.3 3 1.2 4.5l3-2.6z" />
            <path d="M12 5.3c1.5 0 2.7.5 3.7 1.4l2.8-2.8C16.8 2.4 14.6 1.5 12 1.5 8.1 1.5 4.8 4 3.2 7.5l3 2.6c.7-2.5 3-4.3 5.8-4.3z" />
          </svg>
          Continue with Google
        </button>

        <p className="text-center text-sm text-gray-400 mt-6">
          New here?{" "}
          <a href="/register" className="text-indigo-400 hover:underline">
            Create an account
          </a>
        </p>
      </div>
    </div>
  );
}