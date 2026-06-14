import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/router";
import { getBrowserSupabaseClient } from "../lib/supabaseClient";

const ROLE_DASHBOARD = {
  user: { label: "Dashboard", href: "/dashboard", group: "Account" },
  premium: {
    label: "Academy",
    href: "/dashboard/premium",
    group: "Account",
  },
  vip: { label: "VIP Desk", href: "/dashboard/vip", group: "Account" },
  pro: { label: "Pro Desk", href: "/dashboard/pro", group: "Account" },
  lifetime: {
    label: "Lifetime Desk",
    href: "/dashboard/lifetime",
    group: "Account",
  },
};

function getDashboardPathFromRoute(pathname = "") {
  if (pathname.startsWith("/dashboard/lifetime")) return "/dashboard/lifetime";
  if (pathname.startsWith("/dashboard/premium")) return "/dashboard/premium";
  if (pathname.startsWith("/dashboard/vip")) return "/dashboard/vip";
  if (pathname.startsWith("/dashboard/pro")) return "/dashboard/pro";
  if (pathname.startsWith("/dashboard")) return "/dashboard";
  return null;
}

function resolveRoleFromPath(pathname = "") {
  if (pathname.startsWith("/dashboard/premium")) return "premium";
  if (pathname.startsWith("/dashboard/vip")) return "vip";
  if (pathname.startsWith("/dashboard/pro")) return "pro";
  if (pathname.startsWith("/dashboard/lifetime")) return "lifetime";
  if (pathname.startsWith("/dashboard")) return "user";
  if (pathname.startsWith("/admin")) return "admin";
  return null;
}

function dedupeLinks(links) {
  return links.filter(
    (item, idx) => links.findIndex((x) => x.href === item.href) === idx,
  );
}

function buildLinks(role, pathname) {
  const links = [{ label: "Home", href: "/", group: "Main" }];
  const currentDashboardPath = getDashboardPathFromRoute(pathname);
  const dashboard = ROLE_DASHBOARD[role];

  if (dashboard) {
    links.push(dashboard);
  }

  if (currentDashboardPath && currentDashboardPath !== "/dashboard") {
    links.push({
      label: "Bot Access",
      href: `${currentDashboardPath}#bot-access`,
      group: "Trading",
    });
    links.push({
      label: "Mentorship",
      href: `${currentDashboardPath}#mentorship-content`,
      group: "Trading",
    });
  }

  if (role && role !== "admin" && role !== "lifetime") {
    links.push({ label: "Upgrade", href: "/pricing", group: "Account" });
  }

  if (role && role !== "admin") {
    links.push({ label: "Live Room", href: "/live-pen", group: "Trading" });
    links.push({
      label: "Profile",
      href: "/complete-profile",
      group: "Account",
    });
  }

  if (role === "admin") {
    links.push(
      { label: "Command", href: "/admin", group: "Admin" },
      { label: "Users & Limits", href: "/admin/users", group: "Admin" },
      {
        label: "Market Edge",
        href: "/admin/bot-logs#market-edge",
        group: "Bot Desk",
      },
      { label: "Bot Logs", href: "/admin/bot-logs", group: "Bot Desk" },
      { label: "MT5 Status", href: "/admin/settings", group: "Bot Desk" },
      { label: "Payments", href: "/admin/payments", group: "Business" },
      {
        label: "Subscriptions",
        href: "/admin/subscriptions",
        group: "Business",
      },
      { label: "Messages", href: "/admin/messages", group: "Community" },
      { label: "Mentorship", href: "/admin/mentorship", group: "Community" },
      { label: "Content", href: "/admin/content", group: "Community" },
    );
  }

  links.push({ label: "Support", href: "/contact", group: "Main" });
  return dedupeLinks(links);
}

function isActiveHref(pathname, href) {
  const cleanHref = href.split("#")[0];
  if (cleanHref === "/") return pathname === "/";
  return pathname === cleanHref || pathname.startsWith(`${cleanHref}/`);
}

function groupLinks(links) {
  return links.reduce((groups, item) => {
    const group = item.group || "Main";
    if (!groups[group]) groups[group] = [];
    groups[group].push(item);
    return groups;
  }, {});
}

function NavPanel({ links, role, pathname, onSignOut, compact = false }) {
  const grouped = groupLinks(links);

  return (
    <div
      className={`${compact ? "w-[min(22rem,calc(100vw-2rem))] max-w-full" : "w-72"} quick-nav-panel`}
    >
      <div className="quick-nav-header">
        <div className="flex items-center justify-between gap-3">
          <div>
            <div className="quick-nav-kicker">Quick Navigator</div>
            <div className="text-sm font-semibold text-white mt-1 capitalize">
              {role || "member"} workspace
            </div>
          </div>
          <span className="quick-nav-live">
            <span className="h-2 w-2 rounded-sm bg-emerald-300" />
            Live
          </span>
        </div>
      </div>

      <nav className="quick-nav-body">
        {Object.entries(grouped).map(([group, items]) => (
          <div key={group} className="quick-nav-group">
            <div className="quick-nav-group-title">{group}</div>
            <div className="quick-nav-grid">
              {items.map((item) => {
                const active = isActiveHref(pathname, item.href);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`quick-nav-tile ${active ? "is-active" : ""}`}
                  >
                    <span className="quick-nav-tile-mark" aria-hidden="true">
                      {item.label.slice(0, 2).toUpperCase()}
                    </span>
                    <span>{item.label}</span>
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
        <button type="button" onClick={onSignOut} className="quick-nav-signout">
          Sign Out
        </button>
      </nav>
    </div>
  );
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
      if (!user || !active) return;
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
        if (active) setRole(resolvedRole);
      } catch {
        if (active) setRole(resolveRoleFromPath(pathname) || "user");
      }
    };

    loadRole();
    return () => {
      active = false;
    };
  }, [pathname]);

  useEffect(() => {
    setOpen(false);
  }, [pathname]);

  const effectiveRole = useMemo(() => {
    const adminEmail = (
      process.env.NEXT_PUBLIC_ADMIN_EMAIL || ""
    ).toLowerCase();
    const isAdminEmail = adminEmail && userEmail.toLowerCase() === adminEmail;
    const fallbackRole = resolveRoleFromPath(pathname);
    return role === "admin" || isAdminEmail ? "admin" : role || fallbackRole;
  }, [role, userEmail, pathname]);

  const links = useMemo(
    () => buildLinks(effectiveRole, pathname),
    [effectiveRole, pathname],
  );

  if (!allowed) return null;
  const showSidebar =
    pathname.startsWith("/dashboard") || pathname.startsWith("/admin");

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
          <NavPanel
            links={links}
            role={effectiveRole}
            pathname={pathname}
            onSignOut={handleSignOut}
          />
        </aside>
        <div className="relative z-40 lg:hidden">
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            className="quick-nav-trigger"
            aria-expanded={open}
            aria-label="Quick navigation"
          >
            <span
              className={`neon-dot ${open ? "neon-dot-live" : "neon-dot-off"}`}
            />
            <span>{open ? "Close Nav" : "Quick Nav"}</span>
          </button>
          {open && (
            <div className="quick-nav-popover">
              <NavPanel
                links={links}
                role={effectiveRole}
                pathname={pathname}
                onSignOut={handleSignOut}
                compact
              />
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
        className="quick-nav-trigger"
        aria-expanded={open}
        aria-label="Quick navigation"
      >
        <span
          className={`neon-dot ${open ? "neon-dot-live" : "neon-dot-off"}`}
        />
        <span>{open ? "Close Nav" : "Quick Nav"}</span>
      </button>
      {open && (
        <div className="quick-nav-popover">
          <NavPanel
            links={links}
            role={effectiveRole}
            pathname={pathname}
            onSignOut={handleSignOut}
            compact
          />
        </div>
      )}
    </div>
  );
}
