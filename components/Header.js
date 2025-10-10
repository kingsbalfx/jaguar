// components/Header.js
import React, { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation"; // Next.js 13

const NAV_ITEMS = [
  { label: "Home", href: "/" },
  { label: "Pricing", href: "/pricing" },
  { label: "Login", href: "/login" },
];

export default function Header() {
  const [open, setOpen] = useState(false);
  const pathname = usePathname?.() || "/";

  useEffect(() => setOpen(false), [pathname]);

  const isActive = (href) => {
    if (!href) return false;
    if (href === "/") return pathname === "/";
    return pathname === href || pathname.startsWith(href + "/");
  };

  return (
    <header className="w-full bg-gray-900 py-4 px-4 md:px-6">
      <div className="container mx-auto flex items-center justify-between">
        <a href="/" aria-label="KINGSBALFX homepage" className="flex items-center gap-3">
          <img
            src="/jaguar.png"
            alt="KINGSBALFX jaguar logo"
            width={150}
            height={40}
            className="block w-[150px] h-[40px] object-contain"
          />
          <span className="text-white font-bold hidden sm:inline">KINGSBALFX</span>
        </a>

        {/* Desktop nav */}
        <nav className="hidden md:flex items-center gap-3">
          {NAV_ITEMS.map((item) => {
            const active = isActive(item.href);
            return (
              <Link key={item.href} href={item.href} legacyBehavior>
                <a
                  className={`px-3 py-2 rounded text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 ${
                    active
                      ? "text-white bg-indigo-600"
                      : "text-gray-200 hover:text-white hover:bg-white/5"
                  }`}
                  aria-current={active ? "page" : undefined}
                >
                  {item.label}
                </a>
              </Link>
            );
          })}
        </nav>

        {/* Mobile menu button */}
        <div className="md:hidden">
          <button
            aria-expanded={open}
            aria-controls="mobile-menu"
            aria-label={open ? "Close menu" : "Open menu"}
            onClick={() => setOpen((v) => !v)}
            className="inline-flex items-center justify-center p-2 rounded-md text-gray-200 hover:text-white hover:bg-white/5 focus:outline-none focus:ring-2 focus:ring-indigo-500"
          >
            {open ? (
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            ) : (
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            )}
          </button>
        </div>
      </div>

      {/* Mobile menu panel */}
      {open && (
        <div id="mobile-menu" className="md:hidden mt-2 bg-black/30 backdrop-blur-sm">
          <div className="container mx-auto px-4 py-3 flex flex-col gap-1">
            {NAV_ITEMS.map((item) => {
              const active = isActive(item.href);
              return (
                <Link key={item.href} href={item.href} legacyBehavior>
                  <a
                    className={`block px-3 py-2 rounded text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 ${
                      active ? "text-white bg-indigo-600" : "text-gray-200 hover:text-white hover:bg-white/5"
                    }`}
                    aria-current={active ? "page" : undefined}
                  >
                    {item.label}
                  </a>
                </Link>
              );
            })}
          </div>
        </div>
      )}
    </header>
  );
}