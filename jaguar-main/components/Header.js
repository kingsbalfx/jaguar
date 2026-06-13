import React, { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/router";
import QuickNav from "./QuickNav";
import {
  getBrowserSupabaseClient,
  isSupabaseConfigured,
} from "../lib/supabaseClient";

const ROLE_DASHBOARD = {
  user: "/dashboard",
  premium: "/dashboard/premium",
  vip: "/dashboard/vip",
  pro: "/dashboard/pro",
  lifetime: "/dashboard/lifetime",
  admin: "/admin",
};

const NAV_ITEMS = [
  { label: "Home", href: "/" },
  { label: "Pricing", href: "/pricing" },
  { label: "Login", href: "/login" },
];

export default function Header() {
  const [menuOpen, setMenuOpen] = useState(false);
  const [liveMode, setLiveMode] = useState(true);
  const [signedIn, setSignedIn] = useState(false);
  const [role, setRole] = useState(null);
  const [userEmail, setUserEmail] = useState("");
  const router = useRouter();
  const pathname = router.pathname || "/";

  useEffect(() => setMenuOpen(false), [pathname]);

  useEffect(() => {
    let active = true;
    const resolveRole = async (session) => {
      const user = session?.user;
      if (!user) {
        setRole(null);
        setUserEmail("");
        return;
      }
      setUserEmail(user.email || "");
      try {
        const res = await fetch("/api/get-role", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ userId: user.id, userEmail: user.email }),
        });
        const json = await res.json();
        const resolvedRole = (json?.role || "user").toLowerCase();
        setRole(resolvedRole);
      } catch {
        setRole("user");
      }
    };

    const loadSession = async () => {
      if (!isSupabaseConfigured) return;
      const client = getBrowserSupabaseClient();
      if (!client) return;
      const { data } = await client.auth.getSession();
      if (!active) return;
      setSignedIn(Boolean(data?.session));
      await resolveRole(data?.session);
    };
    loadSession();
    let subscription = null;
    if (isSupabaseConfigured) {
      const client = getBrowserSupabaseClient();
      if (client) {
        subscription = client.auth.onAuthStateChange((_event, session) => {
          setSignedIn(Boolean(session));
          resolveRole(session);
        });
      }
    }
    return () => {
      active = false;
      subscription?.data?.subscription?.unsubscribe?.();
    };
  }, []);

  const isActive = (href) =>
    href === "/" ? pathname === "/" : pathname.startsWith(href);

  const isDashboard = pathname.startsWith("/dashboard");
  const isAdmin = pathname.startsWith("/admin");
  const hidePricing = isDashboard || isAdmin;
  const dashboardHref = (() => {
    const adminEmail = (
      process.env.NEXT_PUBLIC_ADMIN_EMAIL || ""
    ).toLowerCase();
    const isAdminEmail = adminEmail && userEmail.toLowerCase() === adminEmail;
    const effectiveRole = role === "admin" || isAdminEmail ? "admin" : role;
    return ROLE_DASHBOARD[effectiveRole] || "/dashboard";
  })();

  const navItems = NAV_ITEMS.map((item) => {
    if (item.label === "Home" && signedIn) {
      return { label: "Dashboard", href: dashboardHref };
    }
    return item;
  });

  const filteredNav = navItems.filter((item) => {
    if (item.label === "Login" && signedIn) return false;
    if (item.label === "Pricing" && hidePricing) return false;
    return true;
  });

  const handleSignOut = async () => {
    const client = getBrowserSupabaseClient();
    if (client) {
      await client.auth.signOut();
    }
    router.push("/login");
  };

  return (
    <header className="site-header">
      <div className="site-header-inner">
        <Link href="/" aria-label="KINGSBALFX homepage" className="site-brand">
          <img
            src="/jaguar.png"
            alt="KINGSBALFX jaguar logo"
            width={130}
            height={36}
            className="h-9 w-auto object-contain"
          />
          <span className="hidden sm:block">
            <span className="site-brand-name">KINGSBALFX</span>
            <span className="site-brand-meta">Trading Intelligence</span>
          </span>
        </Link>

        <nav className="hidden md:flex site-nav">
          {filteredNav.map((item) => {
            const active = isActive(item.href);
            const isLogin = item.label === "Login";
            const styles = active ? "is-active" : isLogin ? "is-login" : "";
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={`site-nav-link ${styles}`}
              >
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="site-header-actions">
          <button
            type="button"
            aria-pressed={liveMode}
            onClick={() => setLiveMode((v) => !v)}
            className="hidden lg:flex site-live-toggle neon-toggle"
          >
            <span
              className={`neon-dot ${liveMode ? "neon-dot-live" : "neon-dot-off"}`}
            />
            <span>{liveMode ? "Live" : "Preview"}</span>
          </button>
          <QuickNav />
          {signedIn ? (
            <button
              type="button"
              onClick={handleSignOut}
              className="hidden md:inline-flex site-account-action is-signout"
            >
              Sign Out
            </button>
          ) : (
            <Link
              href="/login"
              className="hidden md:inline-flex site-account-action"
            >
              Sign In
            </Link>
          )}

          <button
            aria-label={menuOpen ? "Close menu" : "Open menu"}
            onClick={() => setMenuOpen(!menuOpen)}
            className="site-menu-button"
          >
            {menuOpen ? (
              <svg className="w-6 h-6" fill="none" stroke="currentColor">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            ) : (
              <svg className="w-6 h-6" fill="none" stroke="currentColor">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M3 6h18M3 12h18M3 18h18"
                />
              </svg>
            )}
          </button>
        </div>
      </div>

      {/* Mobile Menu */}
      {menuOpen && (
        <nav className="md:hidden bg-black/70 backdrop-blur-md">
          <div className="px-4 py-3 flex flex-col gap-1">
            {filteredNav.map((item) => {
              const active = isActive(item.href);
              const isLogin = item.label === "Login";
              const styles = active
                ? "bg-indigo-600 text-white"
                : isLogin
                  ? "bg-indigo-500/20 text-indigo-100 hover:bg-indigo-500/30"
                  : "text-gray-300 hover:text-white hover:bg-white/10";
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  aria-current={active ? "page" : undefined}
                  className={`block px-3 py-2 rounded-md text-sm transition-colors ${styles}`}
                >
                  {item.label}
                </Link>
              );
            })}
            {signedIn && (
              <button
                type="button"
                onClick={handleSignOut}
                className="mt-2 px-3 py-2 rounded-md text-sm transition-colors bg-red-500/10 text-red-100 hover:bg-red-500/20"
              >
                Sign Out
              </button>
            )}
            <button
              type="button"
              aria-pressed={liveMode}
              onClick={() => setLiveMode((v) => !v)}
              className="mt-3 flex items-center gap-3 px-3 py-2 rounded-full border border-emerald-400/30 bg-emerald-500/10 text-emerald-200 text-xs uppercase tracking-widest neon-toggle"
            >
              <span
                className={`neon-dot ${liveMode ? "neon-dot-live" : "neon-dot-off"}`}
              />
              <span>{liveMode ? "Live Mode" : "Preview"}</span>
            </button>
          </div>
        </nav>
      )}
    </header>
  );
}
