"use client";
import React, { useEffect, useState } from "react";
import { supabase } from "../../lib/supabaseClient";
import { getURL } from "../../lib/getURL";
import { useRouter } from "next/navigation";

export default function AuthRegisterPage() {
  const router = useRouter();
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [redirectUrl, setRedirectUrl] = useState("");

  useEffect(() => {
    // Ensure `window.location` runs in the browser
    const urlParams = new URL(window.location.href).searchParams;
    const next = urlParams.get("next");
    const base = getURL();
    const redirectTo = next
      ? `${base}auth/callback?next=${encodeURIComponent(next)}`
      : `${base}auth/callback`;
    setRedirectUrl(redirectTo);
  }, []);

  const handleGoogle = async () => {
    setError("");
    try {
      const { data, error: oauthErr } = await supabase.auth.signInWithOAuth({
        provider: "google",
        options: { redirectTo: redirectUrl },
      });

      if (oauthErr) {
        throw new Error(oauthErr.message);
      }
      if (data?.url) {
        window.location.href = data.url;
      }
    } catch (err) {
      setError(err.message || "An unexpected error occurred during sign-in.");
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-gray-900 text-white">
      <div className="max-w-md w-full bg-gray-800 p-6 rounded shadow-lg">
        <h2 className="text-2xl font-bold mb-4">Register / OAuth</h2>
        {error && <p className="text-red-400 mb-2">{error}</p>}
        {success && <p className="text-green-400 mb-2">{success}</p>}
        <button
          onClick={handleGoogle}
          className="w-full py-2 bg-blue-500 hover:bg-blue-600 rounded text-white font-semibold focus:outline-none focus:ring-2 focus:ring-blue-300"
          aria-label="Register or Sign in with Google"
        >
          Register / Sign in with Google
        </button>
      </div>
    </div>
  );
}