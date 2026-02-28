import React, { useState, useEffect } from "react";
import { useRouter } from "next/router";
import { getBrowserSupabaseClient, isSupabaseConfigured } from "../lib/supabaseClient";
import { getURL } from "../lib/getURL";

export default function LoginPage() {
  const router = useRouter();
  const next =
    typeof router.query?.next === "string" ? router.query.next : "";
  const oauthError =
    typeof router.query?.error === "string" ? router.query.error : "";
  const isConfigured = Boolean(isSupabaseConfigured);

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
      if (!isConfigured) {
        setErrMsg("Supabase is not configured.");
        setLoading(false);
        return;
      }
      const client = getBrowserSupabaseClient();
      if (!client) throw new Error("Supabase client not available.");
      const { error } = await client.auth.signInWithPassword({ email, password });
      if (error) throw error;

      try {
        await client.auth.signOut({ scope: "others" });
      } catch {}
      if (typeof window !== "undefined") {
        window.localStorage.setItem("enforce_single_session", "1");
      }
      const nextParam = next ? `?next=${encodeURIComponent(next)}` : "";
      router.push(`/auth/callback${nextParam}`);
    } catch (err) {
      const message = err?.message || "Login failed";
      if (message.toLowerCase().includes("invalid login credentials")) {
        setErrMsg("Invalid credentials or email not confirmed. Check your email for a confirmation link or reset your password.");
      } else {
        setErrMsg(message);
      }
      setLoading(false);
    }
  };

  const handleGoogleLogin = async () => {
    setErrMsg("");
    setLoading(true);
    try {
      if (!isConfigured) {
        setErrMsg("Supabase is not configured.");
        setLoading(false);
        return;
      }
      const redirectTo = next
        ? `${base}auth/callback?next=${encodeURIComponent(next)}`
        : `${base}auth/callback`;

      const client = getBrowserSupabaseClient();
      if (!client) throw new Error("Supabase client not available.");
      if (typeof window !== "undefined") {
        window.localStorage.setItem("enforce_single_session", "1");
      }
      const { error } = await client.auth.signInWithOAuth({
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
    if (oauthError) {
      setErrMsg(`Google login failed: ${oauthError}`);
    }
  }, [oauthError]);

  useEffect(() => {
    if (!router.isReady) return;
    const code = typeof router.query?.code === "string" ? router.query.code : null;
    if (!code) return;
    const query = router.asPath.includes("?") ? router.asPath.slice(router.asPath.indexOf("?")) : "";
    router.replace(`/auth/callback${query}`);
  }, [router]);

  useEffect(() => {
    if (!isConfigured) return;
    if (!router.isReady) return;
    if (router.query?.code) return;
    const client = getBrowserSupabaseClient();
    if (!client) return;
    client.auth.signOut().catch(() => {});
  }, [isConfigured, router]);

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

  return (
    <div className="app-bg text-white relative overflow-hidden">
      <div className="candle-backdrop" aria-hidden="true" />
      <div className="app-content min-h-[calc(100vh-160px)] flex items-center justify-center px-6 py-12">
        <div className="login-shell">
          <div className="login-side">
            <div className="login-brand">
              <img src="/jaguar.png" alt="logo" width={72} height={72} />
              <div>
                <div className="login-brand-title">KINGSBALFX</div>
                <div className="login-brand-sub">Trade Lab Access</div>
              </div>
            </div>
            <h1 className="login-hero-title">Sign in to your trading command center.</h1>
            <p className="login-hero-text">
              Private signals, live mentorship rooms, and tiered bot intelligence—built for precision.
            </p>
            <div className="login-bullets">
              <div>• Real‑time market setups and entry alerts</div>
              <div>• Secure access to Pro + Lifetime content</div>
              <div>• 1:1 mentorship and replay libraries</div>
            </div>
            <div className="login-badge">Secure • Encrypted • 24/7 Access</div>
          </div>

          <div className="login-panel">
            <div className="login-panel-header">
              <h2>Welcome back</h2>
              <p>Enter your credentials to continue.</p>
            </div>

            {errMsg && <div className="login-error">{errMsg}</div>}

            <form onSubmit={handleEmailLogin} className="login-form">
              <label>
                Email
                <input
                  type="email"
                  placeholder="you@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                />
              </label>
              <label>
                Password
                <input
                  type="password"
                  placeholder="Your password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                />
              </label>
              <button type="submit" disabled={loading} className="login-primary">
                {loading ? "Signing in..." : "Sign in"}
              </button>
            </form>

            <div className="login-divider">
              <span>or</span>
            </div>

            <button
              onClick={handleGoogleLogin}
              disabled={loading}
              className="login-oauth"
            >
              Continue with Google
            </button>

            <p className="login-footer">
              New here?{" "}
              <a href={next ? `/register?next=${encodeURIComponent(next)}` : "/register"}>
                Create account
              </a>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
