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
  const links = [{ label: "Home", href: "/" }];

  if (ROLE_DASHBOARD[role]) {
    links.push(ROLE_DASHBOARD[role]);
  }

  if (role && role !== "admin" && role !== "lifetime") {
    links.push({ label: "Upgrade Plan", href: "/pricing" });
  }

  if (role && role !== "admin") {
    links.push({ label: "Live Room", href: "/live-pen" });
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

  links.push({ label: "Support", href: "/contact" });
  return links;
}

export default function QuickNav() {
  const [role, setRole] = useState(null);
  const [allowed, setAllowed] = useState(false);
  const [userEmail, setUserEmail] = useState("");
  const router = useRouter();
  const pathname = router.pathname || "/";

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
  const showSidebar = pathname.startsWith("/dashboard") || pathname.startsWith("/admin");
  if (!showSidebar) return null;

  const handleSignOut = async () => {
    const client = getBrowserSupabaseClient();
    if (client) {
      await client.auth.signOut();
    }
    router.push("/login");
  };

  return (
    <aside className="fixed left-4 top-28 z-40 hidden lg:block">
      <div className="w-64 rounded-2xl border border-white/10 bg-slate-950/90 shadow-2xl shadow-black/40 backdrop-blur">
        <div className="px-4 py-3 border-b border-white/10">
          <div className="text-xs uppercase tracking-widest text-gray-400">Quick Navigator</div>
          <div className="text-sm font-semibold text-white mt-1 capitalize">{role || "member"} access</div>
        </div>
        <nav className="px-2 py-3 space-y-1 text-sm">
          {links.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="block px-3 py-2 rounded-lg text-gray-200 hover:bg-white/10"
            >
              {item.label}
            </Link>
          ))}
          <button
            type="button"
            onClick={handleSignOut}
            className="w-full text-left px-3 py-2 rounded-lg text-red-200 hover:bg-white/10"
          >
            Sign Out
          </button>
        </nav>
      </div>
    </aside>
  );
}
