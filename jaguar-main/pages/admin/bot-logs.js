import { useEffect, useState } from "react";
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

    return { props: {} };
  } catch (e) {
    console.error(e);
    return { props: {} };
  }
};

export default function BotLogs() {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const resp = await fetch("/api/admin/bot-logs?limit=200");
        const data = await resp.json();
        setLogs(data.logs || []);
      } catch (e) {
        console.error("Failed to fetch logs:", e);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  if (loading) return <main className="container mx-auto p-6">Loading...</main>;

  return (
    <main className="container mx-auto p-6">
      <h1 className="text-2xl font-bold mb-4">Bot Logs</h1>
      <div className="overflow-x-auto bg-white/5 rounded-lg p-4">
        <div className="text-gray-400 mb-3">Total logs: {logs.length}</div>
        <table className="min-w-full text-left text-sm">
          <thead>
            <tr>
              <th className="px-2 py-1">Event</th>
              <th className="px-2 py-1">Payload</th>
              <th className="px-2 py-1">Created</th>
            </tr>
          </thead>
          <tbody>
            {logs.map((log, i) => (
              <tr key={i} className="border-t border-white/5">
                <td className="px-2 py-2">{log.event}</td>
                <td className="px-2 py-2 text-xs font-mono">{JSON.stringify(log.payload || {}).substring(0, 100)}...</td>
                <td className="px-2 py-2 text-xs">{new Date(log.created_at).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </main>
  );
}
