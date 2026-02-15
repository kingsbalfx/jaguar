import { createPagesServerClient } from "@supabase/auth-helpers-nextjs";
import { getSupabaseClient } from "../../lib/supabaseClient";

export const getServerSideProps = async (ctx) => {
  try {
    const supabase = createPagesServerClient(ctx);
    const {
      data: { session },
    } = await supabase.auth.getSession();

    if (!session || !session.user) {
      return { redirect: { destination: "/login", permanent: false } };
    }

    const supabaseAdmin = getSupabaseClient({ server: true });
    // Only allow admins
    const userId = session.user.id;
    const { data: profile } = await supabaseAdmin.from("profiles").select("role,email").eq("id", userId).maybeSingle();
    const role = (profile?.role || "user").toLowerCase();
    if (role !== "admin") {
      return { redirect: { destination: "/", permanent: false } };
    }

    const { data: payments } = await supabaseAdmin.from("payments").select("id,amount,plan,status,received_at,customer_email").order("received_at", { ascending: false }).limit(500);

    return { props: { payments: payments || [] } };
  } catch (e) {
    console.error(e);
    return { props: { payments: [] } };
  }
};

export default function AdminPayments({ payments }) {
  return (
    <main className="container mx-auto p-6">
      <h1 className="text-2xl font-bold mb-4">Payments</h1>
      <div className="overflow-x-auto bg-white/5 rounded-lg p-4">
        <table className="min-w-full text-left">
          <thead>
            <tr>
              <th className="px-2 py-1">ID</th>
              <th className="px-2 py-1">Amount</th>
              <th className="px-2 py-1">Plan</th>
              <th className="px-2 py-1">Status</th>
              <th className="px-2 py-1">Email</th>
              <th className="px-2 py-1">Received</th>
            </tr>
          </thead>
          <tbody>
            {payments.map((p) => (
              <tr key={p.id} className="border-t border-white/5">
                <td className="px-2 py-2 text-sm">{p.id}</td>
                <td className="px-2 py-2 text-sm">{(Number(p.amount || 0) / 100).toFixed(2)}</td>
                <td className="px-2 py-2 text-sm">{p.plan || "lifetime"}</td>
                <td className="px-2 py-2 text-sm">{p.status}</td>
                <td className="px-2 py-2 text-sm">{p.customer_email || "-"}</td>
                <td className="px-2 py-2 text-sm">{p.received_at}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </main>
  );
}
