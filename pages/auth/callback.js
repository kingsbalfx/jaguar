import { useEffect } from "react";
import { useRouter } from "next/router";
import { createClient } from "@supabase/supabase-js";

export default function Callback() {
  const router = useRouter();

  useEffect(() => {
    let mounted = true;
    async function handleCallback() {
      const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
      const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

      if (!url || !key) {
        console.warn("Missing NEXT_PUBLIC_SUPABASE_* envs; redirecting to /dashboard");
        router.replace("/dashboard");
        return;
      }

      const supabase = createClient(url, key);

      try {
        if (typeof supabase.auth.getSessionFromUrl === "function") {
          try {
            await supabase.auth.getSessionFromUrl({ storeSession: true });
          } catch (e) {
            console.debug("getSessionFromUrl non-fatal:", e?.message || e);
          }
        }

        const { data: sessionData } = await supabase.auth.getSession();
        const user = sessionData?.session?.user ?? null;
        if (!user) {
          router.replace("/register");
          return;
        }

        const r = await fetch("/api/get-role", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ userId: user.id }),
        });

        if (!mounted) return;
        if (!r.ok) {
          router.replace("/dashboard");
          return;
        }

        const json = await r.json();
        const role = json?.role;

        if (role === "vip") router.replace("/dashboard/vip");
        else if (role === "premium") router.replace("/dashboard/premium");
        else router.replace("/dashboard");
      } catch (err) {
        console.error("Callback handling error:", err);
        router.replace("/dashboard");
      }
    }

    handleCallback();
    return () => { mounted = false; };
  }, [router]);

  return <div className="p-6">Signing you in — redirecting to your dashboard...</div>;
}
