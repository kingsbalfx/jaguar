"use client";
import React from "react";
import { supabase } from "../../lib/supabaseClient";
import { getURL } from "../../lib/getURL";
import { useRouter } from "next/navigation";
import { useState } from "react";

export default function AuthRegisterPage() {
  const router = useRouter();
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const urlParams = new URL(window.location.href).searchParams;
  const next = urlParams.get("next");

  const handleGoogle = async () => {
    setError("");
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
        <h2 className="text-xl font-bold mb-4">Register / OAuth</h2>
        {error && <p className="text-red-400">{error}</p>}
        {success && <p className="text-green-400">{success}</p>}
        <button onClick={handleGoogle} className="w-full py-2 bg-blue-500 rounded">
          Register / Sign in with Google
        </button>
      </div>
    </div>
  );
}