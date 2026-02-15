"use client";
import React, { useState } from "react";
import { supabase } from "../../lib/supabaseClient";
import { getURL } from "../../lib/getURL";
import { useRouter } from "next/navigation";

export default function AuthSignupPage() {
  const router = useRouter();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const urlParams = new URL(window.location.href).searchParams;
  const next = urlParams.get("next");

  const handleSignUp = async (e) => {
    e.preventDefault();
    setError("");
    const { error: signError } = await supabase.auth.signUp({
      email,
      password,
      options: {
        data: { full_name: fullName },
      },
    });
    if (signError) {
      setError(signError.message);
    } else {
      setSuccess("Signup success. Check email.");
      setTimeout(() => {
        router.push(`/login${next ? `?next=${encodeURIComponent(next)}` : ""}`);
      }, 1500);
    }
  };

  const handleGoogle = async () => {
    const base = getURL();
    const redirectTo = next
      ? `${base}auth/callback?next=${encodeURIComponent(next)}`
      : `${base}auth/callback`;
    const { data, error: oauthErr } = await supabase.auth.signInWithOAuth({
      provider: "google",
      options: { redirectTo },
    });
    if (oauthErr) {
      setError(oauthErr.message);
    } else if (data?.url) {
      window.location.href = data.url;
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <div className="max-w-md w-full bg-gray-800 p-6 rounded">
        <h2 className="text-xl font-bold mb-4">Signup</h2>
        {error && <p className="text-red-400">{error}</p>}
        {success && <p className="text-green-400">{success}</p>}

        <form onSubmit={handleSignUp} className="space-y-4">
          <input
            type="text"
            placeholder="Full Name"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            className="w-full p-2 rounded bg-gray-700"
            required
          />
          <input
            type="email"
            placeholder="you@example.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full p-2 rounded bg-gray-700"
            required
          />
          <input
            type="password"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full p-2 rounded bg-gray-700"
            required
          />
          <button type="submit" className="w-full py-2 bg-indigo-600 rounded">
            Sign Up
          </button>
        </form>

        <div className="mt-4">
          <button onClick={handleGoogle} className="w-full py-2 bg-blue-500 rounded">
            Continue with Google
          </button>
        </div>
      </div>
    </div>
  );
}