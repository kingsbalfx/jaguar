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
  const [phone, setPhone] = useState("");
  const [address, setAddress] = useState("");
  const [country, setCountry] = useState("");
  const [ageConfirmed, setAgeConfirmed] = useState(false);
  const [errMsg, setErrMsg] = useState("");
  const [successMsg, setSuccessMsg] = useState("");
  const [loading, setLoading] = useState(false);
  const isConfigured = Boolean(isSupabaseConfigured);
  const passwordsMatch = password && confirmPassword && password === confirmPassword;

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
      const { data, error } = await client.auth.signUp({
        email,
        password,
        options: {
          redirectTo,
          data: {
            full_name: fullName,
            phone,
            address,
            country,
            age_confirmed: true,
          },
        },
      });
      if (error) throw error;
      if (data?.session) {
        if (typeof window !== "undefined") {
          window.localStorage.setItem("enforce_single_session", "1");
        }
        const nextParam = next ? `?next=${encodeURIComponent(next)}` : "";
        router.push(`/auth/callback${nextParam}`);
      } else {
        try {
          await new Promise((resolve) => setTimeout(resolve, 800));
          const { data: loginData, error: loginError } = await client.auth.signInWithPassword({
            email,
            password,
          });
          if (loginError || !loginData?.session) {
            setSuccessMsg(
              "Signup successful. Email confirmation is enabled on this project, so you must confirm your email before login. Disable email confirmation in Supabase Auth settings to allow instant login."
            );
            setLoading(false);
            return;
          }
          if (typeof window !== "undefined") {
            window.localStorage.setItem("enforce_single_session", "1");
          }
          const nextParam = next ? `?next=${encodeURIComponent(next)}` : "";
          router.push(`/auth/callback${nextParam}`);
        } catch (loginErr) {
          setSuccessMsg(
            "Signup successful. Email confirmation is enabled on this project, so you must confirm your email before login. Disable email confirmation in Supabase Auth settings to allow instant login."
          );
          setLoading(false);
        }
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
      const base = getURL().replace(/\/$/, "");
      const redirectTo = next
        ? `${base}/auth/callback?next=${encodeURIComponent(next)}`
        : `${base}/auth/callback`;
      const client = getBrowserSupabaseClient();
      if (!client) throw new Error("Supabase client not available.");

      if (typeof window !== "undefined") {
        const payload = { fullName, phone, address, country, ageConfirmed: true };
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
            <input
              type="text"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              required
              placeholder="Full name"
              className="w-full px-4 py-3 rounded-lg bg-white/10"
            />
            <input
              type="tel"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              required
              placeholder="Phone number"
              className="w-full px-4 py-3 rounded-lg bg-white/10"
            />
            <input
              type="text"
              value={address}
              onChange={(e) => setAddress(e.target.value)}
              required
              placeholder="Address"
              className="w-full px-4 py-3 rounded-lg bg-white/10"
            />
            <select
              value={country}
              onChange={(e) => setCountry(e.target.value)}
              required
              className="w-full px-4 py-3 rounded-lg bg-white/10"
            >
              <option value="">Select country</option>
              {COUNTRIES.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              placeholder="you@example.com"
              className="w-full px-4 py-3 rounded-lg bg-white/10"
            />
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              placeholder="********"
              className="w-full px-4 py-3 rounded-lg bg-white/10"
            />
            <input
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
              placeholder="Confirm password"
              className="w-full px-4 py-3 rounded-lg bg-white/10"
            />
            {confirmPassword && !passwordsMatch && (
              <div className="text-xs text-red-300">Passwords do not match.</div>
            )}
            <label className="flex items-start gap-2 text-sm text-gray-300">
              <input
                type="checkbox"
                className="mt-1"
                checked={ageConfirmed}
                onChange={(e) => setAgeConfirmed(e.target.checked)}
                required
              />
              I confirm that I am at least 16 years old.
            </label>
            <button
              type="submit"
              disabled={loading || (confirmPassword && !passwordsMatch)}
              className="w-full py-3 bg-indigo-600 rounded-lg text-white disabled:opacity-60"
            >
              {loading ? "Creating account..." : "Sign Up"}
            </button>
          </form>

          <div className="mt-4 flex items-center gap-3 text-gray-500">
            <hr className="flex-1 border-gray-600" />
            <span className="text-xs uppercase">or</span>
            <hr className="flex-1 border-gray-600" />
          </div>

          <button
            onClick={handleGoogleSignIn}
            disabled={loading}
            className="mt-4 w-full py-3 border border-gray-600 rounded-lg flex items-center justify-center gap-3"
          >
            <FcGoogle size={20} /> Continue with Google
          </button>

          <div className="mt-4 text-center text-sm">
            Already have an account?{" "}
            <a
              href={next ? `/login?next=${encodeURIComponent(next)}` : "/login"}
              className="text-indigo-300 underline"
            >
              Sign in
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}
