// pages/register.js
import React, { useState } from "react";
import { useRouter } from "next/router";
import { getBrowserSupabaseClient, isSupabaseConfigured } from "../lib/supabaseClient";
import { getURL } from "../lib/getURL";
import { FcGoogle } from "react-icons/fc";

const COUNTRIES = [
  "Nigeria",
  "United States",
  "United Kingdom",
  "Canada",
  "Ghana",
  "South Africa",
  "Kenya",
  "Egypt",
  "United Arab Emirates",
  "Saudi Arabia",
  "France",
  "Germany",
  "Italy",
  "Spain",
  "Netherlands",
  "Sweden",
  "Norway",
  "Denmark",
  "Ireland",
  "Portugal",
  "Switzerland",
  "Austria",
  "Belgium",
  "Poland",
  "Turkey",
  "India",
  "Pakistan",
  "Bangladesh",
  "Sri Lanka",
  "China",
  "Japan",
  "South Korea",
  "Indonesia",
  "Malaysia",
  "Philippines",
  "Thailand",
  "Vietnam",
  "Australia",
  "New Zealand",
  "Mexico",
  "Brazil",
  "Argentina",
  "Chile",
  "Colombia",
  "Peru",
  "Morocco",
  "Algeria",
  "Tunisia",
  "Uganda",
  "Tanzania",
  "Rwanda",
  "Zambia",
  "Zimbabwe",
];

export default function Register() {
  const router = useRouter();
  const next = typeof router.query?.next === "string" ? router.query.next : "";
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [username, setUsername] = useState("");
  const [phone, setPhone] = useState("");
  const [address, setAddress] = useState("");
  const [country, setCountry] = useState("");
  const [ageConfirmed, setAgeConfirmed] = useState(false);
  const [errMsg, setErrMsg] = useState("");
  const [successMsg, setSuccessMsg] = useState("");
  const [loading, setLoading] = useState(false);
  const isConfigured = Boolean(isSupabaseConfigured);
  const passwordsMatch = password && confirmPassword && password === confirmPassword;
  const normalizedUsername = username.trim().toLowerCase();
  const usernameValid = /^[a-z0-9_.-]{3,20}$/.test(normalizedUsername);

  if (!isConfigured) {
    return (
      <div className="min-h-[calc(100vh-160px)] flex items-center justify-center bg-black text-white px-6 py-10">
        <div className="max-w-lg w-full bg-black/60 border border-white/10 rounded-xl p-6 text-center">
          <h1 className="text-2xl font-bold mb-2">Configuration Required</h1>
          <p className="text-gray-300">
            Supabase is not configured. Set <code className="bg-white/10 px-1 rounded">NEXT_PUBLIC_SUPABASE_URL</code>{" "}
            and <code className="bg-white/10 px-1 rounded">NEXT_PUBLIC_SUPABASE_ANON_KEY</code> in Vercel.
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
      if (!ageConfirmed) {
        setErrMsg("You must confirm you are at least 16 years old.");
        setLoading(false);
        return;
      }
      if (!password || password.length < 6) {
        setErrMsg("Password must be at least 6 characters.");
        setLoading(false);
        return;
      }
      if (!normalizedUsername || !usernameValid) {
        setErrMsg("Username must be 3-20 characters (letters, numbers, _ . -).");
        setLoading(false);
        return;
      }
      if (password !== confirmPassword) {
        setErrMsg("Passwords do not match.");
        setLoading(false);
        return;
      }
      if (!fullName || !phone || !address || !country) {
        setErrMsg("Please complete all profile fields.");
        setLoading(false);
        return;
      }
      const base = getURL().replace(/\/$/, "");
      const redirectTo = next
        ? `${base}/auth/callback?next=${encodeURIComponent(next)}`
        : `${base}/auth/callback`;
      const client = getBrowserSupabaseClient();
      if (!client) throw new Error("Supabase client not available.");
      const apiRes = await fetch("/api/auth/signup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email,
          password,
          fullName,
          username: normalizedUsername,
          phone,
          address,
          country,
          ageConfirmed: true,
        }),
      });

      if (!apiRes.ok) {
        const apiJson = await apiRes.json().catch(() => ({}));
        const apiError = apiJson?.error || "Unable to create account.";
        if (apiRes.status === 409) {
          setErrMsg("An account with this email already exists. Please sign in.");
          setLoading(false);
          return;
        }
        setErrMsg(apiError);
        setLoading(false);
        return;
      }

      const { data: loginData, error: loginError } = await client.auth.signInWithPassword({
        email,
        password,
      });
      if (loginError || !loginData?.session) {
        setSuccessMsg(
          "Account created but auto-login failed. Please sign in to continue."
        );
        setLoading(false);
        return;
      }

      if (typeof window !== "undefined") {
        window.localStorage.setItem("enforce_single_session", "1");
      }
      const nextParam = next ? `?next=${encodeURIComponent(next)}` : "";
      router.push(`/auth/callback${nextParam}`);
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
      if (!ageConfirmed) {
        setErrMsg("You must confirm you are at least 16 years old.");
        setLoading(false);
        return;
      }
      if (!fullName || !phone || !address || !country) {
        setErrMsg("Please complete all profile fields before continuing.");
        setLoading(false);
        return;
      }
      if (!normalizedUsername || !usernameValid) {
        setErrMsg("Username must be 3-20 characters (letters, numbers, _ . -).");
        setLoading(false);
        return;
      }
      const base = getURL().replace(/\/$/, "");
      const redirectTo = next
        ? `${base}/auth/callback?next=${encodeURIComponent(next)}`
        : `${base}/auth/callback`;
      const client = getBrowserSupabaseClient();
      if (!client) throw new Error("Supabase client not available.");

      if (typeof window !== "undefined") {
        const payload = { fullName, username: normalizedUsername, phone, address, country, ageConfirmed: true };
        window.localStorage.setItem("pending_profile", JSON.stringify(payload));
        window.localStorage.setItem("enforce_single_session", "1");
      }

      const { error } = await client.auth.signInWithOAuth({
        provider: "google",
        options: { redirectTo },
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
      <div className="app-content min-h-[calc(100vh-160px)] flex items-center justify-center px-6 py-12">
        <div className="login-shell">
          <div className="login-side">
            <div className="login-brand">
              <img src="/jaguar.png" alt="logo" width={72} height={72} />
              <div>
                <div className="login-brand-title">KINGSBALFX</div>
                <div className="login-brand-sub">Create Your Access</div>
              </div>
            </div>
            <h1 className="login-hero-title">Join the trading desk in minutes.</h1>
            <p className="login-hero-text">
              Secure your seat, unlock mentorship rooms, and start tracking the signals that matter.
            </p>
            <div className="login-bullets">
              <div>• Structured onboarding with profile completion</div>
              <div>• Tiered dashboard access and live room entry</div>
              <div>• Upgrade anytime with instant plan switches</div>
            </div>
            <div className="login-badge">Trusted • Private • Built for focus</div>
          </div>

          <div className="login-panel">
            <div className="login-panel-header">
              <h2>Create your account</h2>
              <p>Sign up with email or use Google.</p>
            </div>

            {errMsg && <div className="login-error">{errMsg}</div>}
            {successMsg && <div className="login-success">{successMsg}</div>}

            <form onSubmit={handleEmailSignUp} className="login-form">
              <label>
                Full name
                <input
                  type="text"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  required
                  placeholder="Shafiu Abdullahi"
                />
              </label>
              <label>
                Username
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  required
                  placeholder="kingsbalfx"
                />
              </label>
              {!usernameValid && username.length > 0 && (
                <div className="login-hint error">
                  Username must be 3-20 characters (letters, numbers, _ . -).
                </div>
              )}
              <label>
                Phone number
                <input
                  type="tel"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  required
                  placeholder="07034322065"
                />
              </label>
              <label>
                Address
                <input
                  type="text"
                  value={address}
                  onChange={(e) => setAddress(e.target.value)}
                  required
                  placeholder="No 5 Nakasari, Eastern Bypass"
                />
              </label>
              <label>
                Country
                <select
                  value={country}
                  onChange={(e) => setCountry(e.target.value)}
                  required
                >
                  <option value="">Select country</option>
                  {COUNTRIES.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Email
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  placeholder="you@example.com"
                />
              </label>
              <label>
                Password
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  placeholder="********"
                />
              </label>
              <label>
                Confirm password
                <input
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  required
                  placeholder="Confirm password"
                />
              </label>
              {confirmPassword && !passwordsMatch && (
                <div className="login-hint error">Passwords do not match.</div>
              )}
              <label className="login-checkbox">
                <input
                  type="checkbox"
                  checked={ageConfirmed}
                  onChange={(e) => setAgeConfirmed(e.target.checked)}
                  required
                />
                I confirm that I am at least 16 years old.
              </label>
              <button
                type="submit"
                disabled={loading || (confirmPassword && !passwordsMatch)}
                className="login-primary"
              >
                {loading ? "Creating account..." : "Sign Up"}
              </button>
            </form>

            <div className="login-divider">
              <span>or</span>
            </div>

            <button
              onClick={handleGoogleSignIn}
              disabled={loading}
              className="login-oauth"
            >
              <FcGoogle size={20} /> Continue with Google
            </button>

            <p className="login-footer">
              Already have an account?{" "}
              <a href={next ? `/login?next=${encodeURIComponent(next)}` : "/login"}>
                Sign in
              </a>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
