// pages/admin/index.js
import Link from "next/link";
import { useState } from "react";
import { createPagesServerClient } from "@supabase/auth-helpers-nextjs";
import { getSupabaseClient } from "../../lib/supabaseClient";

export const getServerSideProps = async (ctx) => {
  try {
    const supabase = createPagesServerClient(ctx);
    const {
      data: { session },
      error: sessionError,
    } = await supabase.auth.getSession();

    // Not signed in -> redirect to login
    if (sessionError || !session?.user) {
      return { redirect: { destination: "/login", permanent: false } };
    }

    // Create an admin supabase client with service role key
    const supabaseAdmin = getSupabaseClient({ server: true });
    if (!supabaseAdmin) {
      console.error("Missing Supabase admin client (SERVICE_ROLE_KEY).");
      return { redirect: { destination: "/", permanent: false } };
    }

    // Fetch user profile from DB
    const userId = session.user.id;
    const { data: profile, error: profileError } = await supabaseAdmin
      .from("profiles")
      .select("id, role, email, name")
      .eq("id", userId)
      .maybeSingle();

    if (profileError) {
      console.error("Profile error:", profileError);
    }
    if (!profile) {
      // No profile yet -> complete profile flow
      return { redirect: { destination: "/complete-profile", permanent: false } };
    }

    // Only allow admin or SUPER admin (from env)
    const SUPER = (process.env.SUPER_ADMIN_EMAIL || "").toLowerCase();
    const userEmail = (session.user.email || "").toLowerCase();
    const role = (profile.role || "user").toLowerCase();
    if (role !== "admin" && userEmail !== SUPER) {
      // Not an admin
      return { redirect: { destination: "/", permanent: false } };
    }

    // Collect simple metrics
    const [{ data: allProfiles }, { data: payments }] = await Promise.all([
      supabaseAdmin.from("profiles").select("id"),
      supabaseAdmin.from("payments").select("amount, plan, status"),
    ]);
    const usersCount = Array.isArray(allProfiles) ? allProfiles.length : 0;
    const paymentsCount = Array.isArray(payments) ? payments.length : 0;
    const revenue = Array.isArray(payments)
      ? payments.reduce((sum, p) => sum + (Number(p?.amount || 0) / 100 || 0), 0)
      : 0;

    return {
      props: {
        profile: {
          id: profile.id,
          email: profile.email ?? null,
          name: profile.name ?? null,
          role,
        },
        metrics: { usersCount, paymentsCount, revenue },
      },
    };
  } catch (err) {
    console.error("getServerSideProps admin error:", err);
    return { redirect: { destination: "/login", permanent: false } };
  }
};

export default function AdminPage({ profile, metrics }) {
  const [menuOpen, setMenuOpen] = useState(true);
  const [selected, setSelected] = useState("overview");
  const fmtCurrency = (n) =>
    new Intl.NumberFormat("en-NG", { style: "currency", currency: "NGN", maximumFractionDigits: 0 }).format(n);

  return (
    <main className="container mx-auto px-6 py-8">
      <div className="flex gap-6">
        {/* Sidebar */}
        <aside className={`w-64 p-4 rounded-lg bg-black/30 ${menuOpen ? "" : "hidden"}`}>
          <div className="flex justify-between items-center mb-4">
            <div>
              <div className="text-sm text-gray-300">Signed in as</div>
              <div className="font-semibold text-white">{profile?.name || profile?.email || "Admin"}</div>
              <div className="text-xs text-gray-400 capitalize mt-1">{profile?.role}</div>
            </div>
            <button
              onClick={() => setMenuOpen(!menuOpen)}
              className="text-sm px-2 py-1 bg-white/6 rounded hover:bg-white/10"
              aria-label="Toggle menu"
            >
              Toggle
            </button>
          </div>

          <nav className="flex flex-col gap-2">
            <button
              onClick={() => setSelected("overview")}
              className={`w-full text-left px-3 py-2 rounded ${selected === "overview" ? "bg-indigo-600 text-white" : "text-gray-200 hover:bg-white/5"}`}
            >
              Overview
            </button>
            <button
              onClick={() => setSelected("users")}
              className={`w-full text-left px-3 py-2 rounded ${selected === "users" ? "bg-indigo-600 text-white" : "text-gray-200 hover:bg-white/5"}`}
            >
              Users & Segments
            </button>
            <Link href="/admin/mentorship" legacyBehavior>
              <a
                onClick={() => setSelected("mentorship")}
                className={`block px-3 py-2 rounded ${selected === "mentorship" ? "bg-indigo-600 text-white" : "text-gray-200 hover:bg-white/5"}`}
              >
                Mentorship Dashboard
              </a>
            </Link>
            <button
              onClick={() => setSelected("subscriptions")}
              className={`w-full text-left px-3 py-2 rounded ${selected === "subscriptions" ? "bg-indigo-600 text-white" : "text-gray-200 hover:bg-white/5"}`}
            >
              Subscriptions
            </button>
            <Link href="/admin/settings" legacyBehavior>
              <a
                onClick={() => setSelected("settings")}
                className={`block px-3 py-2 rounded ${selected === "settings" ? "bg-indigo-600 text-white" : "text-gray-200 hover:bg-white/5"}`}
              >
                Settings (MT5)
              </a>
            </Link>
            <Link href="/admin/messages" legacyBehavior>
              <a className="text-sm text-gray-300 hover:text-white px-3 py-2 rounded hover:bg-white/5">Messages Manager</a>
            </Link>

            {/* Quick action buttons */}
            <div className="mt-4 border-t border-white/5 pt-3">
              <Link href="/admin/mentorship/upload" legacyBehavior>
                <a className="block text-sm bg-yellow-400 text-black px-3 py-2 rounded mb-2 text-center">Upload Lesson (Mentorship)</a>
              </Link>
              <Link href="/admin/subscriptions/manage" legacyBehavior>
                <a className="block text-sm bg-green-600 text-white px-3 py-2 rounded text-center">Manage Subscriptions</a>
              </Link>
              <Link href="/admin/users" legacyBehavior>
                <a className="block text-sm bg-red-600 text-white px-3 py-2 rounded mt-2 text-center">User Segmentation</a>
              </Link>
            </div>
          </nav>
        </aside>

        {/* Main content */}
        <section className="flex-1 p-4 bg-black/20 rounded-lg min-h-[60vh]">
          {selected === "overview" && (
            <div>
              <h2 className="text-2xl font-bold mb-4">Overview</h2>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
                <div className="p-4 bg-white/5 rounded">
                  <div className="text-xs text-gray-400">Total users</div>
                  <div className="text-2xl font-bold">{metrics?.usersCount ?? 0}</div>
                </div>
                <div className="p-4 bg-white/5 rounded">
                  <div className="text-xs text-gray-400">Payments</div>
                  <div className="text-2xl font-bold">{metrics?.paymentsCount ?? 0}</div>
                </div>
                <div className="p-4 bg-white/5 rounded">
                  <div className="text-xs text-gray-400">Revenue (est.)</div>
                  <div className="text-2xl font-bold">{fmtCurrency(metrics?.revenue ?? 0)}</div>
                </div>
              </div>

              <div className="mb-6">
                <h3 className="text-lg font-semibold mb-2">Quick actions</h3>
                <div className="flex flex-wrap gap-3">
                  <Link href="/admin/mentorship" legacyBehavior>
                    <a className="px-4 py-2 bg-indigo-600 text-white rounded">Open Mentorship</a>
                  </Link>
                  <Link href="/admin/users" legacyBehavior>
                    <a className="px-4 py-2 bg-yellow-500 text-black rounded">Manage Users</a>
                  </Link>
                  <Link href="/admin/subscriptions" legacyBehavior>
                    <a className="px-4 py-2 bg-green-600 text-white rounded">Subscriptions</a>
                  </Link>
              <Link href="/admin/messages" legacyBehavior>
                <a className="px-4 py-2 bg-gray-600 text-white rounded">Messages</a>
              </Link>
              <Link href="/admin/settings" legacyBehavior>
                <a className="px-4 py-2 bg-indigo-700 text-white rounded">MT5 Settings</a>
              </Link>
            </div>
          </div>

              <div>
                <h3 className="text-lg font-semibold mb-2">Notes</h3>
                <p className="text-gray-300">
                  Use the left menu to navigate admin tools. Pages like Mentorship or Upload should be created under <code className="bg-white/5 px-1 rounded">/pages/admin/mentorship*</code>.
                </p>
              </div>
            </div>
          )}

          {selected === "users" && (
            <div>
              <h2 className="text-2xl font-bold mb-4">Users & Segments</h2>
              <p className="text-gray-300 mb-4">
                Here you will list users, search, filter by role (vip / premium / admin) and edit roles. Link to <code>/admin/users</code> for a full management page.
              </p>
              <Link href="/admin/users" legacyBehavior>
                <a className="px-4 py-2 bg-indigo-600 text-white rounded">Open Users Manager</a>
              </Link>
            </div>
          )}

          {selected === "mentorship" && (
            <div>
              <h2 className="text-2xl font-bold mb-4">Mentorship</h2>
              <p className="text-gray-300 mb-4">
                Manage lessons, upload videos, and publish to landing pages. Use the upload page to add mp4/jpg/pdf resources for VIP/Premium.
              </p>
              <div className="flex gap-3">
                <Link href="/admin/mentorship/upload" legacyBehavior>
                  <a className="px-4 py-2 bg-yellow-400 text-black rounded">Upload Lesson</a>
                </Link>
                <Link href="/admin/mentorship" legacyBehavior>
                  <a className="px-4 py-2 bg-indigo-600 text-white rounded">Open Mentorship Dashboard</a>
                </Link>
              </div>
            </div>
          )}

          {selected === "subscriptions" && (
            <div>
              <h2 className="text-2xl font-bold mb-4">Subscriptions</h2>
              <p className="text-gray-300 mb-4">
                Webhook logs, manual adjustments for users, and payment history. Go to the Subscriptions manager for more.
              </p>
              <Link href="/admin/subscriptions" legacyBehavior>
                <a className="px-4 py-2 bg-green-600 text-white rounded">Open Subscriptions</a>
              </Link>
            </div>
          )}
        </section>
      </div>

      <div className="mt-8 text-sm text-gray-400">
        <div>
          Super admin actions: use the upload and manage pages to publish content, adjust roles and view webhook logs.
        </div>
      </div>
    </main>
  );
}
