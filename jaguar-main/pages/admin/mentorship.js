import dynamic from "next/dynamic";
import { useEffect, useMemo, useState } from "react";
import { createPagesServerClient } from "@supabase/auth-helpers-nextjs";
import { getSupabaseClient } from "../../lib/supabaseClient";
import FeedbackMessage from "../../components/FeedbackMessage";

const WebRTCRoom = dynamic(() => import("../../components/WebRTCRoom"), { ssr: false });
const Chat = dynamic(() => import("../../components/Chat"), { ssr: false });
const MENTORSHIP_GROUPS = [
  { value: "all", label: "All active mentorship students" },
  { value: "premium", label: "Academy group" },
  { value: "vip", label: "VIP review group" },
  { value: "pro", label: "Pro private mentorship" },
];

export const getServerSideProps = async (ctx) => {
  const supabase = createPagesServerClient(ctx);
  const { data: { session } } = await supabase.auth.getSession();
  if (!session?.user) return { redirect: { destination: "/login", permanent: false } };
  const admin = getSupabaseClient({ server: true });
  const { data: profile } = await admin.from("profiles").select("role").eq("id", session.user.id).maybeSingle();
  if ((profile?.role || "").toLowerCase() !== "admin") return { redirect: { destination: "/", permanent: false } };
  return { props: { adminName: "Admin" } };
};

function roomNameFromTitle(value) {
  const slug = String(value || "mentorship").trim().toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 60);
  return slug || "mentorship-room";
}

export default function Mentorship({ adminName }) {
  const [session, setSession] = useState(null);
  const [users, setUsers] = useState([]);
  const [selectedUsers, setSelectedUsers] = useState([]);
  const [title, setTitle] = useState("Live Market Mentorship");
  const [startsAt, setStartsAt] = useState("");
  const [endsAt, setEndsAt] = useState("");
  const [segment, setSegment] = useState("vip");
  const [roomMode, setRoomMode] = useState("group");
  const [roomName, setRoomName] = useState(`mentorship-${Date.now()}`);
  const [status, setStatus] = useState("scheduled");
  const [message, setMessage] = useState("");
  const [live, setLive] = useState(false);

  useEffect(() => {
    fetch("/api/admin/live-session").then((r) => r.json()).then((data) => {
      setUsers(data.users || []);
      if (data.session) {
        setSession(data.session);
        setTitle(data.session.title || title);
        setStartsAt(data.session.starts_at?.slice(0, 16) || "");
        setEndsAt(data.session.ends_at?.slice(0, 16) || "");
        setSegment(data.session.segment || "vip");
        setRoomMode(data.session.room_mode || "group");
        setRoomName(data.session.room_name || roomName);
        setStatus(data.session.status || "scheduled");
        setSelectedUsers(data.session.target_user_ids || []);
      }
    });
  }, []);

  const filteredUsers = useMemo(
    () => users.filter((user) => segment === "all" || user.activePlan === segment),
    [segment, users],
  );

  const save = async (event) => {
    event.preventDefault();
    setMessage("");
    const nextRoomName = roomNameFromTitle(title);
    const response = await fetch("/api/admin/live-session", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        sessionId: session?.id || null,
        title,
        startsAt: startsAt || new Date().toISOString(),
        endsAt,
        timezone: "Africa/Lagos",
        status,
        segment,
        roomName: nextRoomName,
        roomMode,
        targetUserIds: roomMode === "group" && selectedUsers.length === 0
          ? filteredUsers.map((user) => user.id)
          : selectedUsers,
        mediaType: "webrtc",
      }),
    });
    const data = await response.json();
    if (!response.ok) return setMessage(data.error || "Unable to save room.");
    setSession(data.session);
    setTitle(data.session.title || title);
    setRoomName(data.session.room_name || roomName);
    setStartsAt(data.session.starts_at?.slice(0, 16) || startsAt);
    setEndsAt(data.session.ends_at?.slice(0, 16) || endsAt);
    setLive(data.session.status === "live");
    setMessage("WebRTC mentorship room saved.");
  };

  return (
    <div className="min-h-screen p-4 text-white sm:p-6">
      <h1 className="text-2xl font-bold">WebRTC Mentorship Dashboard</h1>
      <p className="mt-1 text-sm text-gray-300">Create private one-to-one sessions or selected subscription-group WebRTC rooms.</p>
      <div className="mt-6 grid gap-6 xl:grid-cols-[380px_1fr]">
        <form onSubmit={save} className="card space-y-3 p-4">
          <label className="text-xs text-gray-300">Mentorship title
            <input value={title} onChange={(e) => setTitle(e.target.value)} className="mt-1 w-full rounded bg-black/30 p-2" placeholder="Session title" required />
          </label>
          <input type="datetime-local" value={startsAt} onChange={(e) => setStartsAt(e.target.value)} className="w-full rounded bg-black/30 p-2" />
          <input type="datetime-local" value={endsAt} onChange={(e) => setEndsAt(e.target.value)} className="w-full rounded bg-black/30 p-2" />
          <select value={roomMode} onChange={(e) => setRoomMode(e.target.value)} className="w-full rounded bg-black/30 p-2">
            <option value="group">Selected group</option>
            <option value="one_to_one">Private one-to-one</option>
          </select>
          <select value={segment} onChange={(e) => { setSegment(e.target.value); setSelectedUsers([]); }} className="w-full rounded bg-black/30 p-2">
            {MENTORSHIP_GROUPS.map((group) => <option key={group.value} value={group.value}>{group.label}</option>)}
          </select>
          <label className="text-xs text-gray-300">Room identifier (updates with title when saved)
            <input value={roomNameFromTitle(title)} readOnly className="mt-1 w-full rounded bg-black/20 p-2 text-gray-300" />
          </label>
          <select value={status} onChange={(e) => setStatus(e.target.value)} className="w-full rounded bg-black/30 p-2">
            <option value="scheduled">Scheduled</option><option value="live">Live</option><option value="completed">Completed</option>
          </select>
          <div>
            <div className="mb-2 text-sm font-semibold">Allowed subscribers</div>
            <div className="max-h-56 space-y-1 overflow-auto rounded bg-black/20 p-2">
              {filteredUsers.map((user) => (
                <label key={user.id} className="flex gap-2 text-xs">
                  <input type="checkbox" checked={selectedUsers.includes(user.id)} onChange={(e) => setSelectedUsers((current) => e.target.checked ? roomMode === "one_to_one" ? [user.id] : [...new Set([...current, user.id])] : current.filter((id) => id !== user.id))} />
                  <span>{user.username || user.name || "Subscriber"} ({MENTORSHIP_GROUPS.find((group) => group.value === user.activePlan)?.label || user.activePlan})</span>
                </label>
              ))}
              {filteredUsers.length === 0 && <div className="text-xs text-gray-400">No active subscribers in this mentorship group.</div>}
            </div>
          </div>
          <button className="w-full rounded bg-emerald-600 py-2">Save room</button>
          <button type="button" onClick={() => setLive((value) => !value)} className="w-full rounded bg-indigo-600 py-2">{live ? "Close local room view" : "Open live room"}</button>
          <FeedbackMessage message={message} type={/unable|failed|error/i.test(message) ? "error" : "success"} />
        </form>
        <div className="space-y-5">
          {live && <WebRTCRoom key={roomName} roomName={roomName} roomTitle={title} displayName={adminName} isHost recordingTitle={title} recordingSegment={segment} />}
          <Chat key={`chat-${roomName}`} channel={segment} roomId={roomName} />
        </div>
      </div>
    </div>
  );
}
