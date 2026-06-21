import dynamic from "next/dynamic";
import { useEffect, useMemo, useState } from "react";
import { createPagesServerClient } from "@supabase/auth-helpers-nextjs";
import { getSupabaseClient } from "../../lib/supabaseClient";
import FeedbackMessage from "../../components/FeedbackMessage";
import { MENTORSHIP_GROUPS, formatMentorshipSegmentList, getMentorshipGroupLabel, parseMentorshipSegments } from "../../lib/mentorship-groups";

const WebRTCRoom = dynamic(() => import("../../components/WebRTCRoom"), { ssr: false });
const Chat = dynamic(() => import("../../components/Chat"), { ssr: false });
const EmbeddedLivePlayer = dynamic(() => import("../../components/EmbeddedLivePlayer"), { ssr: false });
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
  const [selectedSegments, setSelectedSegments] = useState(["vip"]);
  const [roomMode, setRoomMode] = useState("group");
  const [roomName, setRoomName] = useState(`mentorship-${Date.now()}`);
  const [deliveryMode, setDeliveryMode] = useState("webrtc");
  const [mediaUrl, setMediaUrl] = useState("");
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
        const savedSegments = parseMentorshipSegments(data.session.segment || "vip");
        setSegment(savedSegments[0] || "vip");
        setSelectedSegments(savedSegments);
        setRoomMode(data.session.room_mode || "group");
        setRoomName(data.session.room_name || roomName);
        setDeliveryMode(data.session.media_type || "webrtc");
        setMediaUrl(data.session.media_url || "");
        setStatus(data.session.status || "scheduled");
        setSelectedUsers(data.session.target_user_ids || []);
      }
    });
  }, []);

  const filteredUsers = useMemo(
    () => users.filter((user) => selectedSegments.includes("all") || selectedSegments.includes(user.activePlan)),
    [selectedSegments, users],
  );

  const toggleSegment = (value) => {
    setSelectedUsers([]);
    setSelectedSegments((current) => {
      if (value === "all") {
        setSegment("all");
        return ["all"];
      }
      const withoutAll = current.filter((item) => item !== "all");
      const next = withoutAll.includes(value)
        ? withoutAll.filter((item) => item !== value)
        : [...withoutAll, value];
      const safeNext = next.length ? next : [value];
      setSegment(safeNext[0]);
      return safeNext;
    });
  };

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
        segment: selectedSegments.includes("all") ? "all" : selectedSegments.join(","),
        roomName: nextRoomName,
        roomMode,
        targetUserIds: roomMode === "one_to_one" ? selectedUsers : [],
        mediaType: deliveryMode,
        mediaUrl: deliveryMode === "webrtc" ? null : mediaUrl,
      }),
    });
    const data = await response.json();
    if (!response.ok) return setMessage(data.error || "Unable to save room.");
    setSession(data.session);
    setTitle(data.session.title || title);
    setRoomName(data.session.room_name || roomName);
    setDeliveryMode(data.session.media_type || deliveryMode);
    setMediaUrl(data.session.media_url || mediaUrl);
    setStartsAt(data.session.starts_at?.slice(0, 16) || startsAt);
    setEndsAt(data.session.ends_at?.slice(0, 16) || endsAt);
    setLive(data.session.status === "live");
    const notified = data.notifications?.notified || 0;
    const emailed = data.notifications?.emailed || 0;
    setMessage(`WebRTC mentorship room saved. ${notified} in-app alert${notified === 1 ? "" : "s"} created; ${emailed} email${emailed === 1 ? "" : "s"} sent.`);
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
          <label className="text-xs text-gray-300">Delivery mode
            <select value={deliveryMode} onChange={(e) => setDeliveryMode(e.target.value)} className="mt-1 w-full rounded bg-black/30 p-2">
              <option value="webrtc">Interactive WebRTC room (best for small groups)</option>
              <option value="youtube">YouTube/stream embed (best for 100-200+ viewers)</option>
              <option value="iframe">External broadcast embed URL</option>
            </select>
          </label>
          {deliveryMode !== "webrtc" && (
            <label className="text-xs text-gray-300">Broadcast/watch URL
              <input
                value={mediaUrl}
                onChange={(e) => setMediaUrl(e.target.value)}
                className="mt-1 w-full rounded bg-black/30 p-2"
                placeholder="https://youtube.com/watch?v=... or provider embed URL"
                required={deliveryMode !== "webrtc"}
              />
              <span className="mt-1 block text-[11px] text-amber-200">Use this for broad mentorships over 100 viewers. Questions still run through the room chat.</span>
            </label>
          )}
          <div className="rounded-xl border border-white/10 bg-black/20 p-3">
            <div className="mb-2 text-xs font-semibold uppercase tracking-widest text-gray-300">Classes allowed to join</div>
            <div className="grid gap-2 sm:grid-cols-2">
              {MENTORSHIP_GROUPS.map((group) => (
                <label key={group.value} className="flex items-center gap-2 rounded-lg bg-white/5 p-2 text-xs">
                  <input
                    type="checkbox"
                    checked={selectedSegments.includes(group.value)}
                    onChange={() => toggleSegment(group.value)}
                  />
                  <span>{group.label}</span>
                </label>
              ))}
            </div>
            <div className="mt-2 text-xs text-emerald-200">Selected: {formatMentorshipSegmentList(selectedSegments.join(","))}</div>
          </div>
          <label className="text-xs text-gray-300">Room identifier (updates with title when saved)
            <input value={roomNameFromTitle(title)} readOnly className="mt-1 w-full rounded bg-black/20 p-2 text-gray-300" />
          </label>
          <select value={status} onChange={(e) => setStatus(e.target.value)} className="w-full rounded bg-black/30 p-2">
            <option value="scheduled">Scheduled</option><option value="live">Live</option><option value="completed">Completed</option>
          </select>
          <div>
            <div className="mb-2 text-sm font-semibold">Allowed subscribers</div>
            {roomMode === "group" && (
              <div className="mb-2 rounded-lg border border-emerald-300/20 bg-emerald-500/10 p-2 text-xs text-emerald-100">
                Group rooms now follow the selected mentorship audience automatically. Any signed-in learner in {formatMentorshipSegmentList(selectedSegments.join(","))} can see and join this room.
              </div>
            )}
            <div className="max-h-56 space-y-1 overflow-auto rounded bg-black/20 p-2">
              {roomMode === "one_to_one" && filteredUsers.map((user) => (
                <label key={user.id} className="flex gap-2 text-xs">
                  <input type="checkbox" checked={selectedUsers.includes(user.id)} onChange={(e) => setSelectedUsers((current) => e.target.checked ? roomMode === "one_to_one" ? [user.id] : [...new Set([...current, user.id])] : current.filter((id) => id !== user.id))} />
                  <span>{user.username || user.name || "Subscriber"} ({getMentorshipGroupLabel(user.activePlan)})</span>
                </label>
              ))}
              {roomMode === "group" && <div className="text-xs text-gray-300">{filteredUsers.length} active subscriber{filteredUsers.length === 1 ? "" : "s"} currently match this audience.</div>}
              {roomMode === "one_to_one" && filteredUsers.length === 0 && <div className="text-xs text-gray-400">No active subscribers in this mentorship group.</div>}
            </div>
          </div>
          <button className="w-full rounded bg-emerald-600 py-2">Save room</button>
          <button type="button" onClick={() => setLive((value) => !value)} className="w-full rounded bg-indigo-600 py-2">{live ? "Close local room view" : "Open live room"}</button>
          <FeedbackMessage message={message} type={/unable|failed|error/i.test(message) ? "error" : "success"} />
        </form>
        <div className="space-y-5">
          {live && deliveryMode === "webrtc" && <WebRTCRoom key={roomName} roomName={roomName} roomTitle={title} displayName={adminName} isHost recordingTitle={title} recordingSegment={segment} />}
          {live && deliveryMode !== "webrtc" && <EmbeddedLivePlayer mediaType={deliveryMode} mediaUrl={mediaUrl} title={title} />}
          <Chat key={`chat-${roomName}`} channel={segment} roomId={roomName} />
        </div>
      </div>
    </div>
  );
}
