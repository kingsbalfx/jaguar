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
  const [errMsg, setErrMsg] = useState("");

  const getBaseUrl = () => {
    const envUrl = process.env.NEXT_PUBLIC_SITE_URL;
    if (envUrl) return envUrl.replace(/\/$/, "");
    if (typeof window !== "undefined" && window.location?.origin) return window.location.origin;
    return "http://localhost:3000";
  };

  const handleEmailLogin = async (e) => {
    e.preventDefault();
    setErrMsg("");
    setLoading(true);
    try {
      console.debug("Login attempt", { email });
      const { error } = await supabase.auth.signInWithPassword({ email, password });
      if (error) throw error;
      const nextParam = next ? `?next=${encodeURIComponent(next)}` : "";
      router.push(`/auth/callback${nextParam}`);
    } catch (err) {
      console.error("signIn error:", err);
      setErrMsg(err?.message || "Login failed. Check credentials.");
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
      // Supabase will redirect to google; no further action
    } catch (err) {
      console.error("Google sign-in error:", err);
      setErrMsg(err?.message || "Google sign-in failed");
      setLoading(false);
    }
  };

  useEffect(() => {
    (async () => {
      try {
        const { data } = await supabase.auth.getSession();
        if (data?.session?.user) {
          const nextParam = next ? `?next=${encodeURIComponent(next)}` : "";
          router.replace(`/auth/callback${nextParam}`);
        }
      } catch (e) {
        // ignore
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-900 via-black to-indigo-900 p-6">
      <div className="max-w-md w-full bg-black/60 ring-1 ring-white/10 rounded-2xl p-8 text-white shadow-2xl">
        <div className="flex flex-col items-center mb-6">
          <Image src="/jaguar.png" alt="logo" width={80} height={80} />
          <h1 className="text-2xl font-extrabold mt-4">KINGSBALFX</h1>
          <p className="text-xs text-gray-300 mt-1">Trade smart • Live smart</p>
        </div>

        {errMsg && <div className="mb-4 text-sm bg-red-700/30 text-red-200 px-4 py-2 rounded">{errMsg}</div>}

        <form onSubmit={handleEmailLogin} className="space-y-4">
          <label className="block">
            <span className="text-xs text-gray-300">Email</span>
            <input type="email" value={email} onChange={(e)=>setEmail(e.target.value)} required className="mt-1 w-full px-4 py-3 rounded-lg bg-white/5" placeholder="you@example.com" />
          </label>
          <label className="block">
            <span className="text-xs text-gray-300">Password</span>
            <input type="password" value={password} onChange={(e)=>setPassword(e.target.value)} required className="mt-1 w-full px-4 py-3 rounded-lg bg-white/5" placeholder="Your password" />
          </label>

          <button type="submit" disabled={loading} className="w-full py-3 rounded-lg bg-gradient-to-r from-emerald-500 to-lime-400 text-black font-semibold">
            {loading ? "Signing in…" : "Sign in"}
          </button>
        </form>

        <div className="my-4 flex items-center gap-3">
          <hr className="flex-1 border-white/10" />
          <span className="text-xs text-gray-400">or</span>
          <hr className="flex-1 border-white/10" />
        </div>

        <button onClick={handleGoogle} disabled={loading} className="w-full py-3 border border-white/10 rounded-lg flex items-center justify-center gap-3">
          Continue with Google
        </button>

        <div className="mt-4 text-center text-sm text-gray-400">
          New here? <a href="/register" className="text-indigo-300 underline">Create account</a>
        </div>
      </div>
    </div>
  );
}