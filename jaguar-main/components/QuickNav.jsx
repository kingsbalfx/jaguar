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

  const dashboard = ROLE_DASHBOARD[role];
  if (dashboard) {
    links.push(dashboard);
    links.push({ label: "Bot Access", href: `${dashboard.href}#bot-access` });
    links.push({ label: "Mentorship Content", href: `${dashboard.href}#mentorship-content` });
  }

  if (role && role !== "admin" && role !== "lifetime") {
    links.push({ label: "Upgrade Plan", href: "/pricing" });
  }

  if (role && role !== "admin") {
    links.push({ label: "Live Room", href: "/live-pen" });
    links.push({ label: "Profile", href: "/complete-profile" });
  }

  if (role === "admin") {
    links.push(
      { label: "Admin Home", href: "/admin" },
      { label: "Payments History", href: "/admin/payments" },
      { label: "Bot Logs", href: "/admin/bot-logs" },
      { label: "MT5 Status", href: "/admin/settings" },
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
  const [open, setOpen] = useState(false);
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

  useEffect(() => {
    setOpen(false);
  }, [pathname]);

  const links = useMemo(() => {
    const adminEmail = (process.env.NEXT_PUBLIC_ADMIN_EMAIL || "").toLowerCase();
    const isAdminEmail = adminEmail && userEmail.toLowerCase() === adminEmail;
    const effectiveRole = role === "admin" || isAdminEmail ? "admin" : role;
    return buildLinks(effectiveRole);
  }, [role, userEmail]);

  if (!allowed) return null;
  const showSidebar = pathname.startsWith("/dashboard") || pathname.startsWith("/admin");

  const handleSignOut = async () => {
    const client = getBrowserSupabaseClient();
    if (client) {
      await client.auth.signOut();
    }
    router.push("/login");
  };

  if (showSidebar) {
    return (
      <>
        <aside className="fixed left-4 top-24 z-40 hidden lg:block">
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
        <div className="relative z-40 lg:hidden">
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            className="flex items-center gap-2 px-4 py-2 rounded-full border border-white/10 bg-white/5 text-xs uppercase tracking-widest text-gray-200 hover:bg-white/10 transition-colors"
            aria-expanded={open}
            aria-label="Quick navigation"
          >
            <span className={`neon-dot ${open ? "neon-dot-live" : "neon-dot-off"}`} />
            <span>{open ? "Close Nav" : "Quick Nav"}</span>
          </button>
          {open && (
            <div className="absolute right-0 mt-3 w-64 rounded-2xl bg-slate-950/95 border border-white/10 shadow-xl backdrop-blur p-2 text-sm">
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
      </>
    );
  }

  return (
    <div className="relative z-40">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 px-4 py-2 rounded-full border border-white/10 bg-white/5 text-xs uppercase tracking-widest text-gray-200 hover:bg-white/10 transition-colors"
        aria-expanded={open}
        aria-label="Quick navigation"
      >
        <span className={`neon-dot ${open ? "neon-dot-live" : "neon-dot-off"}`} />
        <span>{open ? "Close Nav" : "Quick Nav"}</span>
      </button>
      {open && (
        <div className="absolute right-0 mt-3 w-64 rounded-2xl bg-slate-950/95 border border-white/10 shadow-xl backdrop-blur p-2 text-sm">
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
