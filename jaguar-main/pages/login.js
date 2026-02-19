// pages/login.js
import React, { useState, useEffect } from "react";
import { useRouter } from "next/router";
import Image from "next/image";
import { supabase, isSupabaseConfigured } from "../lib/supabaseClient";
import { getURL } from "../lib/getURL";

export default function Login() {
  if (!isSupabaseConfigured || !supabase) {
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

  const router = useRouter();
  const next =
    typeof router.query?.next === "string" ? router.query.next : "";

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [errMsg, setErrMsg] = useState("");

  const base = getURL();

  const handleEmailLogin = async (e) => {
    e.preventDefault();
    setErrMsg("");
    setLoading(true);
    try {
      const { error } = await supabase.auth.signInWithPassword({ email, password });
      if (error) throw error;

      const nextParam = next ? `?next=${encodeURIComponent(next)}` : "";
      router.push(`/auth/callback${nextParam}`);
    } catch (err) {
      setErrMsg(err.message || "Login failed");
      setLoading(false);
    }
  };

  const handleGoogleLogin = async () => {
    setErrMsg("");
    setLoading(true);
    try {
      const redirectTo = next
        ? `${base}auth/callback?next=${encodeURIComponent(next)}`
        : `${base}auth/callback`;

      const { error } = await supabase.auth.signInWithOAuth({
        provider: "google",
        options: { redirectTo },
      });
      if (error) throw error;
    } catch (err) {
      setErrMsg(err.message || "Google login failed");
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
  }, [next, router]);

  return (
    <div className="min-h-[calc(100vh-160px)] flex items-center justify-center bg-gradient-to-br from-gray-900 via-black to-indigo-900 text-white px-6 py-10">
      <div className="max-w-md w-full bg-black/70 p-8 rounded-lg">
        <div className="flex flex-col items-center mb-5">
          <Image src="/jaguar.png" alt="logo" width={80} height={80} />
          <h1 className="text-2xl font-bold mt-3">KINGSBALFX</h1>
        </div>

        {errMsg && <p className="text-red-400 mb-4">{errMsg}</p>}

        <form onSubmit={handleEmailLogin} className="space-y-4">
          <input
            type="email"
            placeholder="you@example.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full px-3 py-2 bg-white/10 rounded"
            required
          />
          <input
            type="password"
            placeholder="Your password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full px-3 py-2 bg-white/10 rounded"
            required
          />
          <button
            type="submit"
            disabled={loading}
            className="w-full py-3 bg-indigo-600 rounded hover:bg-indigo-700 disabled:opacity-50"
          >
            {loading ? "Signing in..." : "Sign in"}
          </button>
        </form>

        <div className="mt-4 flex items-center gap-2">
          <hr className="flex-1 border-white/20" />
          <span className="text-xs text-gray-400">or</span>
          <hr className="flex-1 border-white/20" />
        </div>

        <button
          onClick={handleGoogleLogin}
          disabled={loading}
          className="w-full mt-3 py-3 bg-white/10 border border-white/20 rounded flex justify-center items-center gap-2"
        >
          {/* Google icon or text */}
          Continue with Google
        </button>

        <p className="mt-5 text-center text-sm text-gray-400">
          New here? <a href="/register" className="text-indigo-400 underline">Create account</a>
        </p>
      </div>
    </div>
  );
}

export async function getServerSideProps() {
  return { props: {} };
}
