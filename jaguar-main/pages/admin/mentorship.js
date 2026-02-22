import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import { createPagesServerClient } from "@supabase/auth-helpers-nextjs";
import { getSupabaseClient } from "../../lib/supabaseClient";

const Chat = dynamic(() => import("../../components/Chat"), { ssr: false });

export const getServerSideProps = async (ctx) => {
  try {
    const supabase = createPagesServerClient(ctx);
    const {
      data: { session },
    } = await supabase.auth.getSession();

    if (!session?.user) {
      return { redirect: { destination: "/login", permanent: false } };
    }

    const supabaseAdmin = getSupabaseClient({ server: true });
    const userId = session.user.id;
    const { data: profile } = await supabaseAdmin
      .from("profiles")
      .select("role")
      .eq("id", userId)
      .maybeSingle();

    const role = (profile?.role || "user").toLowerCase();
    if (role !== "admin") {
      return { redirect: { destination: "/", permanent: false } };
    }

    return { props: {} };
  } catch (err) {
    console.error("Admin mentorship auth error:", err);
    return { redirect: { destination: "/login", permanent: false } };
  }
};

export default function Mentorship() {
  const [channel, setChannel] = useState("premium");
  const [title, setTitle] = useState("");
  const [startsAt, setStartsAt] = useState("");
  const [endsAt, setEndsAt] = useState("");
  const [timezone, setTimezone] = useState("Africa/Lagos");
  const [status, setStatus] = useState("scheduled");
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState("");

  useEffect(() => {
    let active = true;
    fetch("/api/admin/live-session")
      .then((res) => res.json())
      .then((data) => {
        if (!active || !data?.session) return;
        const session = data.session;
        setTitle(session.title || "");
        setStartsAt(session.starts_at ? session.starts_at.slice(0, 16) : "");
        setEndsAt(session.ends_at ? session.ends_at.slice(0, 16) : "");
        setTimezone(session.timezone || "Africa/Lagos");
        setStatus(session.status || "scheduled");
      })
      .catch(() => {
        if (!active) return;
        setSaveMsg("Could not load live session settings.");
      });
    return () => {
      active = false;
    };
  }, []);

  const saveLiveSession = async (e) => {
    e.preventDefault();
    setSaveMsg("");
    setSaving(true);
    try {
      const res = await fetch("/api/admin/live-session", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title,
          startsAt,
          endsAt,
          timezone,
          status,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.error || "Failed to save live session");
      setSaveMsg("Live session saved and now showing on the landing page.");
    } catch (err) {
      setSaveMsg(err.message || "Failed to save live session");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="min-h-[calc(100vh-160px)] p-6">
      <h2 className="text-2xl font-bold">Mentorship Dashboard</h2>
      <p className="mt-2">
        Toggle between Premium and VIP community chats and view mentorship-specific stats.
      </p>
      <div className="mt-4 flex gap-2">
        <button onClick={() => setChannel("premium")} className="card px-3">
          Premium Community
        </button>
        <button onClick={() => setChannel("vip")} className="card px-3">
          VIP Community
        </button>
      </div>

      <div className="mt-6 grid md:grid-cols-2 gap-4">
        <div>
          <h3 className="font-semibold">Community Chat â€” {channel.toUpperCase()}</h3>
          <Chat channel={channel} />
        </div>
        <div>
          <h3 className="font-semibold">Mentorship Controls</h3>
          <div className="mt-2 card p-4">
            <p className="text-sm text-gray-300 mb-4">
              Schedule your next live mentorship session. This will appear on the landing page.
            </p>
            <form onSubmit={saveLiveSession} className="space-y-3">
              <div>
                <label className="block text-xs text-gray-400 mb-1">Session Title</label>
                <input
                  className="w-full rounded bg-black/40 border border-white/10 px-3 py-2 text-white"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="Live Market Breakdown"
                  required
                />
              </div>
              <div>
                <label className="block text-xs text-gray-400 mb-1">Start Time</label>
                <input
                  type="datetime-local"
                  className="w-full rounded bg-black/40 border border-white/10 px-3 py-2 text-white"
                  value={startsAt}
                  onChange={(e) => setStartsAt(e.target.value)}
                  required
                />
              </div>
              <div>
                <label className="block text-xs text-gray-400 mb-1">End Time (optional)</label>
                <input
                  type="datetime-local"
                  className="w-full rounded bg-black/40 border border-white/10 px-3 py-2 text-white"
                  value={endsAt}
                  onChange={(e) => setEndsAt(e.target.value)}
                />
              </div>
              <div>
                <label className="block text-xs text-gray-400 mb-1">Timezone</label>
                <input
                  className="w-full rounded bg-black/40 border border-white/10 px-3 py-2 text-white"
                  value={timezone}
                  onChange={(e) => setTimezone(e.target.value)}
                  placeholder="Africa/Lagos"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-400 mb-1">Status</label>
                <select
                  className="w-full rounded bg-black/40 border border-white/10 px-3 py-2 text-white"
                  value={status}
                  onChange={(e) => setStatus(e.target.value)}
                >
                  <option value="scheduled">Scheduled</option>
                  <option value="live">Live</option>
                  <option value="completed">Completed</option>
                </select>
              </div>
              <button
                type="submit"
                disabled={saving}
                className="w-full rounded bg-emerald-600 text-white py-2 disabled:opacity-60"
              >
                {saving ? "Saving..." : "Save Live Session"}
              </button>
              {saveMsg && <p className="text-xs text-gray-300">{saveMsg}</p>}
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}
