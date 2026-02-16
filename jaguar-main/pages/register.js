// pages/register.js
import React, { useState } from "react";
import { useRouter } from "next/router";
import { supabase } from "../lib/supabaseClient";
import { FcGoogle } from "react-icons/fc";

export default function Register() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [errMsg, setErrMsg] = useState("");
  const [loading, setLoading] = useState(false);

  const getBaseUrl = () => {
    const envUrl = process.env.NEXT_PUBLIC_SITE_URL;
    if (envUrl) return envUrl.replace(/\/$/, "");
    if (typeof window !== "undefined" && window.location?.origin) return window.location.origin;
    return "http://localhost:3000";
  };

  const handleEmailSignUp = async (e) => {
    e.preventDefault();
    setLoading(true);
    setErrMsg("");
    try {
      const base = getBaseUrl();
      const { error } = await supabase.auth.signUp({
        email, password, options: { redirectTo: `${base}/auth/callback` }
      });
      if (error) throw error;
      router.push("/auth/callback");
    } catch (err) {
      console.error("signup error:", err);
      setErrMsg(err?.message || "Sign up failed");
      setLoading(false);
    }
  };

  const handleGoogleSignIn = async () => {
    setLoading(true);
    setErrMsg("");
    try {
      const base = getBaseUrl();
      const { error } = await supabase.auth.signInWithOAuth({
        provider: "google",
        options: { redirectTo: `${base}/auth/callback` }
      });
      if (error) throw error;
    } catch (err) {
      console.error("google signup err:", err);
      setErrMsg(err?.message || "Google sign-in failed");
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-900 via-indigo-900 to-black p-4">
      <div className="w-full max-w-md bg-black/70 backdrop-blur-lg border border-white/10 rounded-2xl shadow-2xl p-8 text-white">
        <h1 className="text-3xl font-bold text-center mb-2">Create an Account</h1>
        <p className="text-sm text-gray-400 text-center mb-4">Sign up with email or use Google</p>

        {errMsg && <div className="bg-red-600/40 text-red-200 p-3 rounded mb-4 text-center">{errMsg}</div>}

        <form onSubmit={handleEmailSignUp} className="space-y-4">
          <input type="email" value={email} onChange={(e)=>setEmail(e.target.value)} required placeholder="you@example.com" className="w-full px-4 py-3 rounded-lg bg-white/10" />
          <input type="password" value={password} onChange={(e)=>setPassword(e.target.value)} required placeholder="••••••••" className="w-full px-4 py-3 rounded-lg bg-white/10" />
          <button type="submit" disabled={loading} className="w-full py-3 bg-indigo-600 rounded-lg text-white">
            {loading ? "Creating account…" : "Sign Up"}
          </button>
        </form>

        <div className="mt-4 flex items-center gap-3 text-gray-500">
          <hr className="flex-1 border-gray-600" /><span className="text-xs uppercase">or</span><hr className="flex-1 border-gray-600" />
        </div>

        <button onClick={handleGoogleSignIn} disabled={loading} className="mt-4 w-full py-3 border border-gray-600 rounded-lg flex items-center justify-center gap-3">
          <FcGoogle size={20} /> Continue with Google
        </button>

        <div className="mt-4 text-center text-sm">
          Already have an account? <a href="/login" className="text-indigo-300 underline">Sign in</a>
        </div>
      </div>
    </div>
  );
}