import React, { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/router";
import QuickNav from "./QuickNav";
import { getBrowserSupabaseClient, isSupabaseConfigured } from "../lib/supabaseClient";

const NAV_ITEMS = [
  { label: "Home", href: "/" },
  { label: "Pricing", href: "/pricing" },
  { label: "Login", href: "/login" },
];

export default function Header() {
  const [menuOpen, setMenuOpen] = useState(false);
  const [liveMode, setLiveMode] = useState(true);
  const [signedIn, setSignedIn] = useState(false);
  const router = useRouter();
  const pathname = router.pathname || "/";

  useEffect(() => setMenuOpen(false), [pathname]);

  useEffect(() => {
    let active = true;
    const loadSession = async () => {
      if (!isSupabaseConfigured) return;
      const client = getBrowserSupabaseClient();
      if (!client) return;
      const { data } = await client.auth.getSession();
      if (!active) return;
      setSignedIn(Boolean(data?.session));
    };
    loadSession();
    let subscription = null;
    if (isSupabaseConfigured) {
      const client = getBrowserSupabaseClient();
      if (client) {
        subscription = client.auth.onAuthStateChange((_event, session) => {
          setSignedIn(Boolean(session));
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
  const filteredNav = NAV_ITEMS.filter((item) => {
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
    <header className="sticky top-0 z-50 w-full bg-slate-950/80 text-gray-100 shadow-lg shadow-black/30 backdrop-blur border-b border-white/10">
      <div className="max-w-7xl mx-auto px-4 py-3 grid grid-cols-[1fr_auto_1fr] items-center gap-4">
        <div className="hidden md:block" />

        <div className="flex flex-col items-center gap-2">
          <Link href="/" aria-label="KINGSBALFX homepage" className="flex items-center gap-2 justify-center">
            <img
              src="/jaguar.png"
              alt="KINGSBALFX jaguar logo"
              width={130}
              height={36}
              className="h-9 w-auto object-contain"
            />
            <span className="font-bold tracking-tight hidden sm:inline">KINGSBALFX</span>
          </Link>

          {/* Desktop Nav */}
          <nav className="hidden md:flex items-center gap-1 rounded-full border border-white/10 bg-white/5 p-1">
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
                  className={`px-4 py-2 rounded-full text-sm font-medium transition-colors ${styles}`}
                >
                  {item.label}
                </Link>
              );
            })}
          </nav>
        </div>

        <div className="flex items-center justify-end gap-3">
          <QuickNav />
          {signedIn ? (
            <button
              type="button"
              onClick={handleSignOut}
              className="hidden md:inline-flex items-center px-4 py-2 rounded-full border border-red-400/30 bg-red-500/10 text-red-100 text-xs uppercase tracking-widest hover:bg-red-500/20 transition-colors"
            >
              Sign Out
            </button>
          ) : (
            <Link
              href="/login"
              className="hidden md:inline-flex items-center px-4 py-2 rounded-full border border-indigo-400/30 bg-indigo-500/10 text-indigo-100 text-xs uppercase tracking-widest hover:bg-indigo-500/20 transition-colors"
            >
              Sign In
            </Link>
          )}
          <button
            type="button"
            aria-pressed={liveMode}
            onClick={() => setLiveMode((v) => !v)}
            className="hidden md:flex items-center gap-3 px-3 py-2 rounded-full border border-emerald-400/30 bg-emerald-500/10 text-emerald-200 text-xs uppercase tracking-widest neon-toggle"
          >
            <span className={`neon-dot ${liveMode ? "neon-dot-live" : "neon-dot-off"}`} />
            <span>{liveMode ? "Live Mode" : "Preview"}</span>
          </button>

          {/* Mobile button */}
          <button
            aria-label={menuOpen ? "Close menu" : "Open menu"}
            onClick={() => setMenuOpen(!menuOpen)}
            className="md:hidden p-2 text-gray-300 hover:text-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            {menuOpen ? (
              <svg className="w-6 h-6" fill="none" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            ) : (
              <svg className="w-6 h-6" fill="none" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 6h18M3 12h18M3 18h18" />
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
              <span className={`neon-dot ${liveMode ? "neon-dot-live" : "neon-dot-off"}`} />
              <span>{liveMode ? "Live Mode" : "Preview"}</span>
            </button>
          </div>
        </nav>
      )}
    </header>
  );
}
