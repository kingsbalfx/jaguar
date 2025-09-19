import { useState } from "react";
import { useRouter } from "next/router";
import Link from "next/link";
import { supabase } from "../lib/supabaseClient";
import Header from "../components/Header";
import Footer from "../components/Footer";

export default function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [errorMsg, setErrorMsg] = useState("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  const handleLogin = async (e) => {
    e.preventDefault();
    setLoading(true);
    setErrorMsg("");

    // Sign in with email and password (Supabase Auth)
    const { data, error } = await supabase.auth.signInWithPassword({
      email: email,
      password: password,
    });
    if (error) {
      setErrorMsg(error.message);
      setLoading(false);
    } else {
      const user = data.user || data.session?.user;
      if (user) {
        try {
          // Fetch the user's subscription role from backend
          const res = await fetch("/api/get-role", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ userId: user.id }),
          });
          if (res.ok) {
            const { role } = await res.json();
            if (role) {
              // Subscriber -> dashboard
              router.push("/dashboard");
            } else {
              // Free user -> home
              router.push("/");
            }
          } else {
            router.push("/");
          }
        } catch (err) {
          console.error("Error fetching role:", err);
          router.push("/");
        }
      } else {
        setErrorMsg("Login failed: no user returned");
        setLoading(false);
      }
    }
  };

  const handleGoogle = async () => {
    setLoading(true);
    const { error } = await supabase.auth.signInWithOAuth({
      provider: "google",
      options: { redirectTo: window.location.origin + "/auth/callback" },
    });
    if (error) {
      console.error("OAuth error:", error);
      setErrorMsg(error.message);
      setLoading(false);
    }
    // On success, Supabase will redirect to /auth/callback
  };

  return (
    <>
      <Header />
      <main className="container mx-auto px-6 py-12">
        <div className="max-w-md mx-auto bg-gray-800 p-6 rounded-lg">
          <h2 className="text-2xl font-bold mb-4">Login</h2>
          <form onSubmit={handleLogin} className="flex flex-col gap-4">
            <input
              type="email"
              placeholder="Email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full px-4 py-2 rounded bg-gray-700 border border-gray-600 text-white placeholder-gray-400"
              required
            />
            <input
              type="password"
              placeholder="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-4 py-2 rounded bg-gray-700 border border-gray-600 text-white placeholder-gray-400"
              required
            />
            <button
              type="submit"
              disabled={loading}
              className="w-full bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded disabled:opacity-50"
            >
              {loading ? "Logging in..." : "Login"}
            </button>
          </form>
          <button
            onClick={handleGoogle}
            disabled={loading}
            className="w-full bg-red-600 hover:bg-red-700 text-white font-bold py-2 px-4 rounded mt-4"
          >
            {loading ? "Redirecting to Google..." : "Sign in with Google"}
          </button>
          <p className="mt-4">
            Don&apos;t have an account?{" "}
            <Link href="/register" className="text-blue-400 hover:underline">
              Register
            </Link>
          </p>
          {errorMsg && <p className="text-red-500 mt-2">{errorMsg}</p>}
        </div>
      </main>
      <Footer />
    </>
  );
}
