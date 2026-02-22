import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/router";

const LINKS = [
  { label: "Home", href: "/" },
  { label: "Pricing", href: "/pricing" },
  { label: "Login", href: "/login" },
  { label: "Register", href: "/register" },
  { label: "Dashboard (Premium)", href: "/dashboard/premium" },
  { label: "Dashboard (VIP)", href: "/dashboard/vip" },
  { label: "Dashboard (Pro)", href: "/dashboard/pro" },
  { label: "Dashboard (Lifetime)", href: "/dashboard/lifetime" },
  { label: "Admin Home", href: "/admin" },
  { label: "Admin Messages", href: "/admin/messages" },
  { label: "Admin Settings", href: "/admin/settings" },
  { label: "Mentorship", href: "/admin/mentorship" },
];

export default function QuickNav() {
  const [open, setOpen] = useState(false);
  const router = useRouter();

  useEffect(() => {
    setOpen(false);
  }, [router.pathname]);

  return (
    <div className="fixed left-4 top-20 z-[60]">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="h-11 w-11 rounded-full bg-indigo-600 text-white shadow-lg shadow-black/30 border border-white/10 flex items-center justify-center"
        aria-expanded={open}
        aria-label="Quick navigation"
      >
        {open ? "×" : "≡"}
      </button>

      {open && (
        <div className="mt-3 w-56 rounded-xl bg-slate-950/95 border border-white/10 shadow-xl backdrop-blur p-2 text-sm">
          {LINKS.map((item) => (
            <Link key={item.href} href={item.href} className="block px-3 py-2 rounded-md text-gray-200 hover:bg-white/10">
              {item.label}
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
