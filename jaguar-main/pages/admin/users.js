import { useState } from "react";
import { createPagesServerClient } from "@supabase/auth-helpers-nextjs";
import { getSupabaseClient } from "../../lib/supabaseClient";

export const getServerSideProps = async (ctx) => {
  try {
    const supabase = createPagesServerClient(ctx);
    const {
      data: { session },
    } = await supabase.auth.getSession();

    if (!session || !session.user) return { redirect: { destination: "/login", permanent: false } };

    const supabaseAdmin = getSupabaseClient({ server: true });
    const userId = session.user.id;
    const { data: profile } = await supabaseAdmin.from("profiles").select("role").eq("id", userId).maybeSingle();
    const role = (profile?.role || "user").toLowerCase();
    if (role !== "admin") return { redirect: { destination: "/", permanent: false } };

    const { data: users } = await supabaseAdmin.from("profiles").select("id,email,name,role,lifetime,created_at").order("created_at", { ascending: false }).limit(1000);

    return { props: { users: users || [] } };
  } catch (e) {
    console.error(e);
    return { props: { users: [] } };
  }
};

export default function UsersAdmin({ users }) {
  const [list, setList] = useState(users || []);

  async function toggleLifetime(email, current) {
    try {
      const resp = await fetch(`/api/admin/toggle-lifetime`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, set: !current }),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data?.error || "failed");
      setList((s) => s.map((u) => (u.email === email ? { ...u, lifetime: !current } : u)));
    } catch (e) {
      alert("Failed to toggle lifetime: " + e.message);
    }
  }

  return (
    <main className="container mx-auto p-6">
      <h1 className="text-2xl font-bold mb-4">User Management</h1>
      <div className="overflow-x-auto bg-white/5 rounded-lg p-4">
        <table className="min-w-full text-left">
          <thead>
            <tr>
              <th className="px-2 py-1">Email</th>
              <th className="px-2 py-1">Name</th>
              <th className="px-2 py-1">Role</th>
              <th className="px-2 py-1">Lifetime</th>
              <th className="px-2 py-1">Actions</th>
            </tr>
          </thead>
          <tbody>
            {list.map((u) => (
              <tr key={u.id} className="border-t border-white/5">
                <td className="px-2 py-2 text-sm">{u.email}</td>
                <td className="px-2 py-2 text-sm">{u.name || "-"}</td>
                <td className="px-2 py-2 text-sm">{u.role}</td>
                <td className="px-2 py-2 text-sm">{u.lifetime ? "Yes" : "No"}</td>
                <td className="px-2 py-2 text-sm">
                  <button onClick={() => toggleLifetime(u.email, !!u.lifetime)} className="px-3 py-1 bg-indigo-600 text-white rounded">
                    {u.lifetime ? "Revoke" : "Grant"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </main>
  );
}
