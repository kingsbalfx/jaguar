import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import FeedbackMessage from "./FeedbackMessage";
import EmbeddedLivePlayer from "./EmbeddedLivePlayer";

const WebRTCRoom = dynamic(() => import("./WebRTCRoom"), { ssr: false });
const Chat = dynamic(() => import("./Chat"), { ssr: false });

export default function LiveSessionPanel({ heading = "Live Mentorship" }) {
  const [session, setSession] = useState(null);
  const [role, setRole] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    const load = () => fetch("/api/live-session")
      .then(async (response) => {
        const data = await response.json();
        if (!response.ok) throw new Error(data?.error || "Unable to load live session.");
        if (!active) return;
        setSession(data.session || null);
        setRole(data.role || "");
        setDisplayName(data.displayName || data.role || "Subscriber");
        setError("");
      })
      .catch((err) => active && setError(err.message))
      .finally(() => active && setLoading(false));
    load();
    const timer = window.setInterval(load, 30000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, []);

  if (loading) return <div className="glass-panel rounded-2xl p-5 text-sm text-gray-300">Loading mentorship room...</div>;
  if (error) return <><div className="glass-panel rounded-2xl p-5 text-sm text-gray-300">The mentorship room is temporarily unavailable. Please refresh shortly.</div><FeedbackMessage message={error} type="error" /></>;
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
      {session.media_type === "webrtc" || !session.media_type ? (
        <WebRTCRoom key={session.room_name || session.id} roomName={session.room_name || session.id} roomTitle={session.title} displayName={displayName || role || "Subscriber"} />
      ) : (
        <div className="space-y-3 rounded-2xl border border-white/10 bg-slate-950/80 p-4">
          <div className="text-xs uppercase tracking-widest text-sky-200">Scalable broadcast mode</div>
          <EmbeddedLivePlayer mediaType={session.media_type} mediaUrl={session.media_url} title={session.title || "Live mentorship session"} />
          <div className="text-xs text-gray-400">Broadcast mode is recommended for 100-200+ viewers. Use the room chat below for questions.</div>
        </div>
      )}
      <Chat key={`chat-${session.room_name || session.id}`} channel={session.segment || role || "mentorship"} roomId={session.room_name || session.id} />
    </div>
  );
}
