import { useEffect, useState } from "react";
import { createPagesServerClient } from "@supabase/auth-helpers-nextjs";
import { getSupabaseClient } from "../../lib/supabaseClient";

export const getServerSideProps = async (ctx) => {
  try {
    const supabase = createPagesServerClient(ctx);
    const {
      data: { session },
      error: sessionError,
    } = await supabase.auth.getSession();

    if (sessionError || !session?.user) {
      return { redirect: { destination: "/login", permanent: false } };
    }

    const supabaseAdmin = getSupabaseClient({ server: true });
    const userId = session.user.id;
    const { data: profile } = await supabaseAdmin
      .from("profiles")
      .select("id, role, email, name")
      .eq("id", userId)
      .maybeSingle();

    if (!profile) {
      return { redirect: { destination: "/complete-profile", permanent: false } };
    }

    const role = (profile.role || "user").toLowerCase();
    if (role !== "admin") {
      return { redirect: { destination: "/", permanent: false } };
    }

    return {
      props: {
        profile: {
          id: profile.id,
          email: profile.email ?? null,
          name: profile.name ?? null,
          role,
        },
      },
    };
  } catch (err) {
    console.error("admin settings auth error:", err);
    return { redirect: { destination: "/login", permanent: false } };
  }
};

export default function Settings({ profile }) {
  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const [server, setServer] = useState("");
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState(null);
  const [hasPassword, setHasPassword] = useState(false);

  useEffect(() => {
    let isMounted = true;

    async function loadCredentials() {
      try {
        const res = await fetch("/api/admin/mt5-credentials");
        const data = await res.json();
        if (!res.ok) throw new Error(data?.error || "Failed to load credentials");
        if (!isMounted) return;
        setLogin(data.credentials?.login || "");
        setServer(data.credentials?.server || "");
        setHasPassword(Boolean(data.credentials?.hasPassword));
      } catch (err) {
        if (isMounted) setStatus({ type: "error", message: err.message || String(err) });
      } finally {
        if (isMounted) setLoading(false);
      }
    }

    loadCredentials();
    return () => {
      isMounted = false;
    };
  }, []);

  async function onSubmit(e) {
    e.preventDefault();
    setStatus(null);

    try {
      const res = await fetch("/api/admin/mt5-credentials", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ login, password, server }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.error || "Failed to save credentials");
      setPassword("");
      setHasPassword(true);
      setStatus({ type: "success", message: "MT5 credentials saved to Supabase." });
    } catch (err) {
      setStatus({ type: "error", message: err.message || String(err) });
    }
  }

  return (
    <main className="container mx-auto px-6 py-8">
      <div className="mb-6">
        <div className="text-sm text-gray-400">Signed in as</div>
        <div className="text-white font-semibold">{profile?.name || profile?.email || "Admin"}</div>
      </div>

      <section className="p-6 rounded-lg bg-black/20">
        <h1 className="text-2xl font-bold mb-2">MT5 Credentials</h1>
        <p className="text-gray-300 mb-6">
          Store MetaTrader 5 login details in Supabase so the trading bot never reads them from environment files.
        </p>

        {status?.message && (
          <div
            className={`mb-4 rounded px-3 py-2 text-sm ${
              status.type === "success" ? "bg-green-600/20 text-green-200" : "bg-red-600/20 text-red-200"
            }`}
          >
            {status.message}
          </div>
        )}

        <form onSubmit={onSubmit} className="space-y-4 max-w-xl">
          <div>
            <label className="block text-sm text-gray-300 mb-1">MT5 Login</label>
            <input
              className="w-full rounded bg-black/40 border border-white/10 px-3 py-2 text-white"
              placeholder="Account number"
              value={login}
              onChange={(e) => setLogin(e.target.value)}
              disabled={loading}
              required
            />
          </div>
          <div>
            <label className="block text-sm text-gray-300 mb-1">MT5 Password</label>
            <input
              className="w-full rounded bg-black/40 border border-white/10 px-3 py-2 text-white"
              placeholder={hasPassword ? "Stored in Supabase (enter new to rotate)" : "Account password"}
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={loading}
              required
            />
          </div>
          <div>
            <label className="block text-sm text-gray-300 mb-1">MT5 Server</label>
            <input
              className="w-full rounded bg-black/40 border border-white/10 px-3 py-2 text-white"
              placeholder="Broker server name"
              value={server}
              onChange={(e) => setServer(e.target.value)}
              disabled={loading}
              required
            />
          </div>
          <button
            className="px-4 py-2 rounded bg-indigo-600 text-white disabled:opacity-60"
            type="submit"
            disabled={loading}
          >
            Save Credentials
          </button>
        </form>
      </section>
    </main>
  );
}
