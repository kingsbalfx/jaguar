import { useEffect, useState } from "react";
import dynamic from "next/dynamic";

const TwilioVideoClient = dynamic(() => import("./TwilioVideoClient"), { ssr: false });

function toYouTubeEmbed(url) {
  try {
    const parsed = new URL(url);
    if (parsed.hostname.includes("youtu.be")) {
      const id = parsed.pathname.replace("/", "");
      return `https://www.youtube.com/embed/${id}`;
    }
    if (parsed.searchParams.get("v")) {
      return `https://www.youtube.com/embed/${parsed.searchParams.get("v")}`;
    }
    return url;
  } catch {
    return url;
  }
}

export default function LiveSessionPanel({ heading = "Live Session" }) {
  const [session, setSession] = useState(null);
  const [status, setStatus] = useState("loading");
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;

    async function loadSession() {
      try {
        const res = await fetch("/api/live-session");
        const data = await res.json();
        if (!active) return;

        if (!res.ok) {
          setError(data?.error || "Unable to load live session.");
          setStatus("error");
          return;
        }

        setSession(data?.session || null);
        setStatus("ready");
      } catch (err) {
        if (!active) return;
        setError("Unable to load live session.");
        setStatus("error");
      }
    }

    loadSession();
    return () => {
      active = false;
    };
  }, []);

  if (status === "loading") {
    return (
      <div className="glass-panel rounded-2xl p-5">
        <div className="text-sm text-gray-300">Loading live session...</div>
      </div>
    );
  }

  if (status === "error") {
    return (
      <div className="glass-panel rounded-2xl p-5">
        <div className="text-sm text-gray-300">{error}</div>
      </div>
    );
  }

  if (!session) {
    return (
      <div className="glass-panel rounded-2xl p-5">
        <div className="text-sm text-gray-300">No live session scheduled yet.</div>
      </div>
    );
  }

  return (
    <div className="glass-panel rounded-2xl p-5">
      <div className="text-xs uppercase tracking-widest text-emerald-200">{heading}</div>
      <div className="mt-2 text-lg font-semibold text-white">
        {session.title || "Next Live Session"}
      </div>
      <div className="mt-1 text-sm text-gray-300">
        {session.starts_at ? new Date(session.starts_at).toLocaleString() : "Time not set"}
        {session.ends_at ? ` - ${new Date(session.ends_at).toLocaleTimeString()}` : ""}
        {session.timezone ? ` (${session.timezone})` : ""}
      </div>

      <div className="mt-4">
        {session.media_type === "youtube" && session.media_url && (
          <div className="aspect-video w-full overflow-hidden rounded-lg border border-white/10">
            <iframe
              title="YouTube Live"
              src={toYouTubeEmbed(session.media_url)}
              className="w-full h-full"
              allow="autoplay; encrypted-media"
              allowFullScreen
            />
          </div>
        )}

        {(session.media_type === "twilio_video" || session.media_type === "twilio_audio") && (
          <div className="mt-3">
            <TwilioVideoClient
              roomName={session.room_name || "global-room"}
              audioOnly={Boolean(session.audio_only)}
            />
          </div>
        )}

        {!session.media_type && (
          <div className="text-sm text-gray-300">Live session media is not configured yet.</div>
        )}
      </div>
    </div>
  );
}
