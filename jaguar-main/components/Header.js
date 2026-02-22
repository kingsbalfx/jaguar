import React, { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/router";
import QuickNav from "./QuickNav";

const NAV_ITEMS = [
  { label: "Home", href: "/" },
  { label: "Pricing", href: "/pricing" },
  { label: "Login", href: "/login" },
];

export default function Header() {
  const [menuOpen, setMenuOpen] = useState(false);
  const [liveMode, setLiveMode] = useState(true);
  const router = useRouter();
  const pathname = router.pathname || "/";

  useEffect(() => setMenuOpen(false), [pathname]);

  const isActive = (href) =>
    href === "/" ? pathname === "/" : pathname.startsWith(href);

  return (
    <header className="sticky top-0 z-50 w-full bg-slate-950/80 text-gray-100 shadow-lg shadow-black/30 backdrop-blur border-b border-white/10">
      <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between gap-4">
        <Link href="/" aria-label="KINGSBALFX homepage" className="flex items-center gap-2">
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
        <nav className="hidden md:flex items-center gap-2">
          {NAV_ITEMS.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              aria-current={isActive(item.href) ? "page" : undefined}
              className={`px-3 py-2 rounded-md text-sm transition-colors ${
                isActive(item.href)
                  ? "bg-indigo-600 text-white"
                  : "text-gray-300 hover:text-white hover:bg-white/10"
              }`}
            >
              {item.label}
            </Link>
          ))}
        </nav>

        <div className="hidden md:flex items-center gap-3">
          <QuickNav />
          <button
            type="button"
            aria-pressed={liveMode}
            onClick={() => setLiveMode((v) => !v)}
            className="flex items-center gap-3 px-3 py-2 rounded-full border border-emerald-400/30 bg-emerald-500/10 text-emerald-200 text-xs uppercase tracking-widest neon-toggle"
          >
            <span className={`neon-dot ${liveMode ? "neon-dot-live" : "neon-dot-off"}`} />
            <span>{liveMode ? "Live Mode" : "Preview"}</span>
          </button>
        </div>

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

      {/* Mobile Menu */}
      {menuOpen && (
        <nav className="md:hidden bg-black/70 backdrop-blur-md">
          <div className="px-4 py-3 flex flex-col gap-1">
            {NAV_ITEMS.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                aria-current={isActive(item.href) ? "page" : undefined}
                className={`block px-3 py-2 rounded-md text-sm transition-colors ${
                  isActive(item.href)
                    ? "bg-indigo-600 text-white"
                    : "text-gray-300 hover:text-white hover:bg-white/10"
                }`}
              >
                {item.label}
              </Link>
            ))}
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
