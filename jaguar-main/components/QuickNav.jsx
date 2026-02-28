import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/router";
import { getBrowserSupabaseClient } from "../lib/supabaseClient";

const ROLE_DASHBOARD = {
  user: { label: "Dashboard", href: "/dashboard" },
  premium: { label: "Dashboard (Premium)", href: "/dashboard/premium" },
  vip: { label: "Dashboard (VIP)", href: "/dashboard/vip" },
  pro: { label: "Dashboard (Pro)", href: "/dashboard/pro" },
  lifetime: { label: "Dashboard (Lifetime)", href: "/dashboard/lifetime" },
};

function buildLinks(role) {
  const links = [
    { label: "Home", href: "/" },
    { label: "Pricing", href: "/pricing" },
  ];

  if (ROLE_DASHBOARD[role]) {
    links.push(ROLE_DASHBOARD[role]);
  }

  if (role === "admin") {
    links.push(
      { label: "Admin Home", href: "/admin" },
      { label: "Admin Settings", href: "/admin/settings" },
      { label: "Admin Messages", href: "/admin/messages" },
      { label: "Mentorship", href: "/admin/mentorship" },
      { label: "Users", href: "/admin/users" },
      { label: "Subscriptions", href: "/admin/subscriptions" }
    );
  }

  return links;
}

export default function QuickNav() {
  const [open, setOpen] = useState(false);
  const [role, setRole] = useState(null);
  const [allowed, setAllowed] = useState(false);
  const [userEmail, setUserEmail] = useState("");
  const router = useRouter();

  useEffect(() => {
    setOpen(false);
  }, [router.pathname]);

  useEffect(() => {
    let active = true;
    const loadRole = async () => {
      const client = getBrowserSupabaseClient();
      if (!client) return;
      const { data } = await client.auth.getSession();
      const user = data?.session?.user;
      if (!user) return;
      if (!active) return;
      setAllowed(true);
      setUserEmail(user.email || "");

      try {
        const res = await fetch("/api/get-role", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ userId: user.id, userEmail: user.email }),
        });
        const json = await res.json();
        const resolvedRole = (json?.role || "user").toLowerCase();
        if (!active) return;
        setRole(resolvedRole);
      } catch {
        if (!active) return;
        setRole("user");
      }
    };

    loadRole();
    return () => {
      active = false;
    };
  }, []);

  const links = useMemo(() => {
    const adminEmail = (process.env.NEXT_PUBLIC_ADMIN_EMAIL || "").toLowerCase();
    const isAdminEmail = adminEmail && userEmail.toLowerCase() === adminEmail;
    const effectiveRole = role === "admin" || isAdminEmail ? "admin" : role;
    return buildLinks(effectiveRole);
  }, [role, userEmail]);

  if (!allowed) return null;

  const handleSignOut = async () => {
    const client = getBrowserSupabaseClient();
    if (client) {
      await client.auth.signOut();
    }
    router.push("/login");
  };

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="h-10 w-10 rounded-full bg-indigo-600 text-white shadow-lg shadow-black/30 border border-white/10 flex items-center justify-center"
        aria-expanded={open}
        aria-label="Quick navigation"
      >
        {open ? "×" : "≡"}
      </button>

      {open && (
        <div className="absolute left-0 mt-3 w-60 rounded-xl bg-slate-950/95 border border-white/10 shadow-xl backdrop-blur p-2 text-sm">
          {links.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="block px-3 py-2 rounded-md text-gray-200 hover:bg-white/10"
            >
              {item.label}
            </Link>
          ))}
          <button
            type="button"
            onClick={handleSignOut}
            className="w-full text-left px-3 py-2 rounded-md text-red-200 hover:bg-white/10"
          >
            Sign Out
          </button>
        </div>
      )}
    </div>
  );
}
