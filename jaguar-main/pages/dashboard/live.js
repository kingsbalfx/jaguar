import { createPagesServerClient } from "@supabase/auth-helpers-nextjs";
import LiveSessionPanel from "../../components/LiveSessionPanel";
import { getSupabaseClient } from "../../lib/supabaseClient";
import { getPaidAccess } from "../../lib/subscription-status";
import { getMentorshipGroup, getMentorshipGroupLabel } from "../../lib/mentorship-groups";

export async function getServerSideProps(ctx) {
  const supabase = createPagesServerClient(ctx);
  const { data: { session } } = await supabase.auth.getSession();

  if (!session?.user) {
    return {
      redirect: {
        destination: `/login?next=${encodeURIComponent("/dashboard/live")}`,
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
    role = String(data?.role || "user").toLowerCase();
  }

  if (role === "admin") {
    return { redirect: { destination: "/admin/mentorship", permanent: false } };
  }

  const access = await getPaidAccess({ supabaseAdmin, email: session.user.email, role });
  return {
    props: {
      activePlan: access.active ? access.plan : "free",
    },
  };
}

export default function DashboardLive({ activePlan }) {
  const group = getMentorshipGroup(activePlan || "free");
  const label = activePlan && activePlan !== "free" ? getMentorshipGroupLabel(activePlan) : "Starter Resources";

  return (
    <section className="relative min-h-[calc(100vh-160px)] overflow-hidden px-4 py-8 text-white sm:px-6">
      <div className="candle-backdrop" aria-hidden="true" />
      <div className="app-content mx-auto max-w-6xl">
        <div className={`mb-6 overflow-hidden rounded-3xl border border-white/10 bg-gradient-to-br ${group.accent} p-[1px] shadow-2xl`}>
          <div className="rounded-3xl bg-black/75 p-5 backdrop-blur sm:p-7">
            <div className="text-xs uppercase tracking-[0.25em] text-emerald-200">Live Room</div>
            <h1 className="mt-2 text-2xl font-bold">KINGSBALFX Live Mentorship</h1>
            <p className="mt-2 text-sm text-gray-300">
              This page shows the active live room and chat for your account. Current tier: {label}.
            </p>
          </div>
        </div>
        <LiveSessionPanel heading={`${label} Live Room`} />
      </div>
    </section>
  );
}
