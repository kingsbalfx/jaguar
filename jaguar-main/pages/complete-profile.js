import React, { useState, useEffect } from "react";
import { useRouter } from "next/router";
import { getBrowserSupabaseClient, isSupabaseConfigured } from "../lib/supabaseClient";

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

/**
 * CompleteProfile Page
 * --------------------
 * - Shown after user signs up but has no record in `profiles` table.
 * - Collects full name and phone.
 * - Saves or updates profile with default role: 'user'.
 * - Redirects to /dashboard after success.
 */

export default function CompleteProfile() {
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [address, setAddress] = useState("");
  const [country, setCountry] = useState("");
  const [ageConfirmed, setAgeConfirmed] = useState(false);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState("");
  const [user, setUser] = useState(null);
  const router = useRouter();
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

  //  Fetch authenticated user + prefill metadata
  useEffect(() => {
    const fetchUser = async () => {
      if (!isConfigured) return;
      const client = getBrowserSupabaseClient();
      if (!client) return;
      const {
        data: { user },
      } = await client.auth.getUser();

      if (!user) {
        router.push("/login");
      } else {
        setUser(user);
        const metadata = user.user_metadata || {};
        setName((prev) => prev || metadata.full_name || metadata.name || "");
        setPhone((prev) => prev || metadata.phone || "");
        setAddress((prev) => prev || metadata.address || "");
        setCountry((prev) => prev || metadata.country || "");
        if (metadata.age_confirmed === true || metadata.age_confirmed === "true") {
          setAgeConfirmed(true);
        }
      }
    };

    fetchUser();
  }, [isConfigured, router]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      const raw = window.localStorage.getItem("pending_profile");
      if (!raw) return;
      const pending = JSON.parse(raw);
      setName((prev) => prev || pending.fullName || "");
      setPhone((prev) => prev || pending.phone || "");
      setAddress((prev) => prev || pending.address || "");
      setCountry((prev) => prev || pending.country || "");
      if (pending.ageConfirmed) setAgeConfirmed(true);
    } catch {}
  }, []);

  //  Handle form submission
  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!user) return;

    setLoading(true);
    setErr("");

    try {
      if (!ageConfirmed) {
        setErr("You must confirm you are at least 16 years old.");
        setLoading(false);
        return;
      }
      if (!name || !phone || !address || !country) {
        setErr("Please complete all profile fields.");
        setLoading(false);
        return;
      }
      const res = await fetch("/api/profile/complete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, phone, address, country, ageConfirmed }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data?.error || "Failed to save profile");
      }
      if (typeof window !== "undefined") {
        window.localStorage.removeItem("pending_profile");
      }
      router.push("/dashboard");
    } catch (error) {
      setErr(error.message || "Something went wrong");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app-bg text-white relative overflow-hidden">
      <div className="candle-backdrop" aria-hidden="true" />
      <div className="app-content min-h-[calc(100vh-160px)] flex items-center justify-center bg-gradient-to-br from-gray-900 via-indigo-900 to-black p-4 py-10">
        <div className="w-full max-w-md bg-black/70 backdrop-blur-lg border border-white/10 rounded-2xl shadow-2xl p-8 text-white space-y-6">
        <h1 className="text-3xl font-bold text-center">Complete Your Profile</h1>
        <p className="text-sm text-gray-400 text-center">
          Please fill in your details to finish setting up your account.
        </p>

        {err && (
          <div className="bg-red-600/40 text-red-200 p-3 rounded text-center">
            {err}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label className="block text-sm text-gray-300 mb-1">Full Name</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              placeholder="John Doe"
              className="w-full px-4 py-3 rounded-lg bg-white/10 placeholder-gray-400 focus:bg-white/20 focus:ring-2 focus:ring-indigo-500 outline-none transition"
            />
          </div>

          <div>
            <label className="block text-sm text-gray-300 mb-1">Phone Number</label>
            <input
              type="tel"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              required
              placeholder="+2348012345678"
              className="w-full px-4 py-3 rounded-lg bg-white/10 placeholder-gray-400 focus:bg-white/20 focus:ring-2 focus:ring-indigo-500 outline-none transition"
            />
          </div>

          <div>
            <label className="block text-sm text-gray-300 mb-1">Address</label>
            <input
              type="text"
              value={address}
              onChange={(e) => setAddress(e.target.value)}
              required
              placeholder="Street, City, State"
              className="w-full px-4 py-3 rounded-lg bg-white/10 placeholder-gray-400 focus:bg-white/20 focus:ring-2 focus:ring-indigo-500 outline-none transition"
            />
          </div>

          <div>
            <label className="block text-sm text-gray-300 mb-1">Country</label>
            <select
              value={country}
              onChange={(e) => setCountry(e.target.value)}
              required
              className="w-full px-4 py-3 rounded-lg bg-white/10 text-white"
            >
              <option value="">Select country</option>
              {COUNTRIES.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>

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
            disabled={loading}
            className="w-full py-3 bg-indigo-600 rounded-lg font-semibold hover:bg-indigo-700 disabled:opacity-60 transition"
          >
            {loading ? "Saving..." : "Save & Continue"}
          </button>
        </form>
        </div>
      </div>
    </div>
  );
}

