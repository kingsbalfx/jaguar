// pages/auth/callback.js
import React from "react";
import { createPagesServerClient } from "@supabase/auth-helpers-nextjs";

export const getServerSideProps = async (ctx) => {
  const supabase = createPagesServerClient(ctx);

  // finalize UIDs / OAuth redirect exchange, and get session
  const {
    data: { session },
    error: sessionError,
  } = await supabase.auth.getSession();

  if (sessionError) {
    console.error("Supabase getSession error:", sessionError.message || sessionError);
    return {
      redirect: {
        destination: "/login",
        permanent: false,
      },
    };
  }

  const user = session?.user;
  if (!user || !user.email) {
    return {
      redirect: {
        destination: "/login",
        permanent: false,
      },
    };
  }

  // fetch role from profiles table
  const { data: profile, error: profileError } = await supabase
    .from("profiles")
    .select("role")
    .eq("id", user.id)
    .maybeSingle();

  if (profileError) {
    console.error("Supabase profile fetch error:", profileError.message || profileError);
    // fallback redirect
    return {
      redirect: {
        destination: "/dashboard",
        permanent: false,
      },
    };
  }

  const role = profile?.role ?? null;
  const email = user.email;

  // Role-based redirection
  if (role === "admin" || email.toLowerCase() === "shafiuabdullahi.sa3@gmail.com") {
    return {
      redirect: {
        destination: "/admin",
        permanent: false,
      },
    };
  } else if (role === "vip") {
    return {
      redirect: {
        destination: "/dashboard/vip",
        permanent: false,
      },
    };
  } else if (role === "premium") {
    return {
      redirect: {
        destination: "/dashboard/premium",
        permanent: false,
      },
    };
  } else {
    return {
      redirect: {
        destination: "/dashboard",
        permanent: false,
      },
    };
  }
};

export default function Callback() {
  return <div className="p-6 text-center">Redirecting…</div>;
}

