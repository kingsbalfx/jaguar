import React from "react";
import Link from "next/link";
import { createPagesServerClient } from "@supabase/auth-helpers-nextjs";
import { getSupabaseClient } from "../../lib/supabaseClient";

export async function getServerSideProps(ctx) {
  const supabase = createPagesServerClient(ctx);
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session?.user) {
    return {
      redirect: {
        destination: "/login",
        permanent: false,
      },
    };
  }

  const supabaseAdmin = getSupabaseClient({ server: true });
  let role = "user";
  if (supabaseAdmin) {
    const { data } = await supabaseAdmin
      .from("profiles")
      .select("role")
      .eq("id", session.user.id)
      .maybeSingle();
    role = (data?.role || "user").toLowerCase();
  }

  const redirectMap = {
    admin: "/admin",
    premium: "/dashboard/premium",
    vip: "/dashboard/vip",
    pro: "/dashboard/pro",
    lifetime: "/dashboard/lifetime",
  };

  if (redirectMap[role]) {
    return {
      redirect: {
        destination: redirectMap[role],
        permanent: false,
      },
    };
  }

  return {
    props: {
      email: session.user.email || "",
    },
  };
}

export default function DashboardHome({ email }) {
  return (
    <div className="app-bg text-white relative overflow-hidden min-h-[calc(100vh-160px)]">
      <div className="candle-backdrop" aria-hidden="true" />
      <div className="app-content container mx-auto px-6 py-16">
        <div className="max-w-2xl mx-auto bg-black/70 border border-white/10 rounded-2xl p-8 text-center">
          <h1 className="text-3xl font-bold mb-3">Welcome back</h1>
          <p className="text-gray-300 mb-6">
            Your account is ready. Choose a subscription tier to unlock your dashboard and live sessions.
          </p>
          {email && <p className="text-sm text-gray-500 mb-6">Signed in as {email}</p>}
          <div className="flex flex-wrap justify-center gap-3">
            <Link href="/pricing">
              <a className="px-5 py-3 rounded-lg bg-indigo-600 text-white font-semibold">View Pricing</a>
            </Link>
            <Link href="/checkout?plan=premium">
              <a className="px-5 py-3 rounded-lg border border-white/20 text-white/90">Upgrade Now</a>
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
