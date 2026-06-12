import dynamic from "next/dynamic";
import { useEffect, useState } from "react";

const WebRTCRoom = dynamic(() => import("./WebRTCRoom"), { ssr: false });
const Chat = dynamic(() => import("./Chat"), { ssr: false });

export default function LiveSessionPanel({ heading = "Live Mentorship" }) {
  const [session, setSession] = useState(null);
  const [role, setRole] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/live-session")
      .then(async (response) => {
        const data = await response.json();
        if (!response.ok) throw new Error(data?.error || "Unable to load live session.");
        setSession(data.session || null);
        setRole(data.role || "");
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="glass-panel rounded-2xl p-5 text-sm text-gray-300">Loading mentorship room...</div>;
  if (error) return <div className="glass-panel rounded-2xl p-5 text-sm text-red-300">{error}</div>;
  if (!session) return <div className="glass-panel rounded-2xl p-5 text-sm text-gray-300">No mentorship room is active for your account.</div>;

  return (
    <div className="space-y-4">
      <div className="glass-panel rounded-2xl p-5 text-white">
        <div className="text-xs uppercase tracking-widest text-emerald-200">{heading}</div>
        <div className="mt-2 text-xl font-semibold">{session.title || "Live mentorship session"}</div>
        <div className="mt-1 text-sm text-gray-300">
          {session.starts_at ? new Date(session.starts_at).toLocaleString() : "Available now"}
          {session.room_mode ? ` · ${session.room_mode === "one_to_one" ? "Private 1:1" : "Group room"}` : ""}
        </div>
      </div>
      <WebRTCRoom roomName={session.room_name || session.id} displayName={role || "Subscriber"} />
      <Chat channel={session.segment || role || "mentorship"} roomId={session.room_name || session.id} />
    </div>
  );
}
