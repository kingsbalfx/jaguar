// pages/register.js
import React, { useState } from "react";
import { useRouter } from "next/router";
import { getBrowserSupabaseClient, isSupabaseConfigured } from "../lib/supabaseClient";
import { getURL } from "../lib/getURL";
import { FcGoogle } from "react-icons/fc";

export default function Register() {
  const router = useRouter();
  const next =
    typeof router.query?.next === "string" ? router.query.next : "";
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [errMsg, setErrMsg] = useState("");
  const [successMsg, setSuccessMsg] = useState("");
  const [loading, setLoading] = useState(false);
  const isConfigured = Boolean(isSupabaseConfigured);

  if (!isConfigured) {
    return (
      <div className="min-h-[calc(100vh-160px)] flex items-center justify-center bg-black text-white px-6 py-10">
        <div className="max-w-lg w-full bg-black/60 border border-white/10 rounded-xl p-6 text-center">
          <h1 className="text-2xl font-bold mb-2">Configuration Required</h1>
          <p className="text-gray-300">
            Supabase is not configured. Set <code className="bg-white/10 px-1 rounded">NEXT_PUBLIC_SUPABASE_URL</code> and{" "}
            <code className="bg-white/10 px-1 rounded">NEXT_PUBLIC_SUPABASE_ANON_KEY</code> in Vercel.
          </p>
        </div>
      </div>
    );
  }

  const handleEmailSignUp = async (e) => {
    e.preventDefault();
    setLoading(true);
    setErrMsg("");
    setSuccessMsg("");
    try {
      if (!isConfigured) {
        setErrMsg("Supabase is not configured.");
        setLoading(false);
        return;
      }
      const base = getURL().replace(/\/$/, "");
      const redirectTo = next
        ? `${base}/auth/callback?next=${encodeURIComponent(next)}`
        : `${base}/auth/callback`;
      const client = getBrowserSupabaseClient();
      if (!client) throw new Error("Supabase client not available.");
      const { data, error } = await client.auth.signUp({
        email,
        password,
        options: { redirectTo }
      });
      if (error) throw error;
      if (data?.session) {
        const nextParam = next ? `?next=${encodeURIComponent(next)}` : "";
        router.push(`/auth/callback${nextParam}`);
      } else {
        setSuccessMsg("Signup successful. Please check your email to confirm your account.");
        setLoading(false);
      }
    } catch (err) {
      console.error("signup error:", err);
      setErrMsg(err?.message || "Sign up failed");
      setLoading(false);
    }
  };

  const handleGoogleSignIn = async () => {
    setLoading(true);
    setErrMsg("");
    setSuccessMsg("");
    try {
      if (!isConfigured) {
        setErrMsg("Supabase is not configured.");
        setLoading(false);
        return;
      }
      const base = getURL().replace(/\/$/, "");
      const redirectTo = next
        ? `${base}/auth/callback?next=${encodeURIComponent(next)}`
        : `${base}/auth/callback`;
      const client = getBrowserSupabaseClient();
      if (!client) throw new Error("Supabase client not available.");
      const { error } = await client.auth.signInWithOAuth({
        provider: "google",
        options: { redirectTo }
      });
      if (error) throw error;
    } catch (err) {
      console.error("google signup err:", err);
      setErrMsg(err?.message || "Google sign-in failed");
      setLoading(false);
    }
  };

  return (
    <div className="app-bg text-white relative overflow-hidden">
      <div className="candle-backdrop" aria-hidden="true" />
      <div className="app-content min-h-[calc(100vh-160px)] flex items-center justify-center bg-gradient-to-br from-slate-900 via-indigo-900 to-black p-4 py-10">
        <div className="w-full max-w-md bg-black/70 backdrop-blur-lg border border-white/10 rounded-2xl shadow-2xl p-8 text-white">
        <h1 className="text-3xl font-bold text-center mb-2">Create an Account</h1>
        <p className="text-sm text-gray-400 text-center mb-4">Sign up with email or use Google</p>

        {errMsg && <div className="bg-red-600/40 text-red-200 p-3 rounded mb-4 text-center">{errMsg}</div>}
        {successMsg && (
          <div className="bg-emerald-600/30 text-emerald-100 p-3 rounded mb-4 text-center">
            {successMsg}
          </div>
        )}

        <form onSubmit={handleEmailSignUp} className="space-y-4">
          <input type="email" value={email} onChange={(e)=>setEmail(e.target.value)} required placeholder="you@example.com" className="w-full px-4 py-3 rounded-lg bg-white/10" />
          <input type="password" value={password} onChange={(e)=>setPassword(e.target.value)} required placeholder="********" className="w-full px-4 py-3 rounded-lg bg-white/10" />
          <button type="submit" disabled={loading} className="w-full py-3 bg-indigo-600 rounded-lg text-white">
            {loading ? "Creating account..." : "Sign Up"}
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
    </div>
  );
}

