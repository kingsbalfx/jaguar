"use client";
import { useState } from "react";
import { supabase } from "../../lib/supabaseClient"; // if you have a shared client
import { getURL } from "../../lib/getURL";
import { useRouter } from "next/navigation";
import Link from "next/link";

export default function AuthLoginPage() {
  const router = useRouter();
  const [name, setName] = useState(""); // maybe unused if this is login
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const urlParams = new URL(window.location.href).searchParams;
  const next = urlParams.get("next");

  // If this page is meant for registration, but you also want it to support Google login:
  const handleGoogle = async () => {
    setError("");
    try {
      const base = getURL();
      const redirectTo = next
        ? `${base}auth/callback?next=${encodeURIComponent(next)}`
        : `${base}auth/callback`;

      const { data, error: oauthError } = await supabase.auth.signInWithOAuth({
        provider: "google",
        options: { redirectTo },
      });
      if (oauthError) {
        setError(oauthError.message);
      } else if (data?.url) {
        // supabase returns a URL to redirect to
        window.location.href = data.url;
      }
    } catch (e) {
      console.error("Google login error:", e);
      setError("Google login failed");
    }
  };

  // If this page is actually a registration (name, phone, etc.), your handleSubmit should do signUp
  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setSuccess("");

    if (!name || !phone || !email || !password || !confirmPassword) {
      setError("All fields are required");
      return;
    }
    if (password !== confirmPassword) {
      setError("Passwords do not match");
      return;
    }

    const { error: signUpError } = await supabase.auth.signUp({
      email,
      password,
      options: {
        data: { name, phone },
      },
    });

    if (signUpError) {
      setError(signUpError.message);
    } else {
      setSuccess("Registered! Check your email.");
      // Optionally redirect
      setTimeout(() => {
        router.push(`/login${next ? `?next=${encodeURIComponent(next)}` : ""}`);
      }, 1500);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <div className="max-w-md w-full bg-gray-800 p-8 rounded">
        <h2 className="text-2xl font-bold mb-4">Auth Login / Register</h2>
        {error && <p className="text-red-400">{error}</p>}
        {success && <p className="text-green-400">{success}</p>}

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* name, phone, email, password fields */}
          <input
            type="text"
            placeholder="Full name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full p-2 rounded bg-gray-700"
            required
          />
          <input
            type="text"
            placeholder="Phone"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
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
          <input
            type="password"
            placeholder="Confirm password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            className="w-full p-2 rounded bg-gray-700"
            required
          />

          <button type="submit" className="w-full py-2 bg-indigo-600 rounded">
            {success ? "Redirecting..." : "Submit / Register"}
          </button>
        </form>

        <div className="mt-4">
          <button onClick={handleGoogle} className="w-full py-2 bg-blue-500 rounded">
            Continue with Google
          </button>
        </div>

        <div className="mt-4 text-sm text-center">
          Already have account? <Link href="/login">Login</Link>
        </div>
      </div>
    </div>
  );
}