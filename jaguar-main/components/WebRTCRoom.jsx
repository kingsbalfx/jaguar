import { useCallback, useEffect, useRef, useState } from "react";
import { getBrowserSupabaseClient } from "../lib/supabaseClient";

const DEFAULT_ICE_SERVERS = [{ urls: "stun:stun.l.google.com:19302" }, { urls: "stun:stun1.l.google.com:19302" }];

function iceServers() {
  try {
    const configured = JSON.parse(process.env.NEXT_PUBLIC_WEBRTC_ICE_SERVERS || "[]");
    return Array.isArray(configured) && configured.length ? configured : DEFAULT_ICE_SERVERS;
  } catch {
    return DEFAULT_ICE_SERVERS;
  }
}

function VideoTile({ stream, label, muted = false }) {
  const ref = useRef(null);
  useEffect(() => {
    if (ref.current) ref.current.srcObject = stream || null;
  }, [stream]);
  return (
    <div className="relative overflow-hidden rounded-xl bg-black/60 min-h-[180px]">
      <video ref={ref} autoPlay playsInline muted={muted} className="h-full w-full object-contain" />
      <div className="absolute bottom-2 left-2 rounded bg-black/70 px-2 py-1 text-xs text-white">{label}</div>
    </div>
  );
}

export default function WebRTCRoom({ roomName, displayName, isHost = false, autoJoin = false }) {
  const supabase = getBrowserSupabaseClient();
  const clientId = useRef(typeof crypto !== "undefined" ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`);
  const channelRef = useRef(null);
  const peersRef = useRef(new Map());
  const screenAudioSendersRef = useRef(new Map());
  const localStreamRef = useRef(null);
  const screenStreamRef = useRef(null);
  const [localStream, setLocalStream] = useState(null);
  const [remoteStreams, setRemoteStreams] = useState({});
  const [participants, setParticipants] = useState({});
  const [joined, setJoined] = useState(false);
  const [micEnabled, setMicEnabled] = useState(true);
  const [cameraEnabled, setCameraEnabled] = useState(true);
  const [sharingScreen, setSharingScreen] = useState(false);
  const [error, setError] = useState("");

  const sendSignal = useCallback(async (target, type, data) => {
    if (!channelRef.current) return;
    await channelRef.current.send({
      type: "broadcast",
      event: "webrtc-signal",
      payload: { source: clientId.current, target, type, data },
    });
  }, []);

  const attachRemoteStream = useCallback((peerId, stream) => {
    setRemoteStreams((current) => ({ ...current, [peerId]: stream }));
  }, []);

  const createPeer = useCallback(
    (peerId, initiator) => {
      if (peersRef.current.has(peerId)) return peersRef.current.get(peerId);
      const peer = new RTCPeerConnection({ iceServers: iceServers() });
      peersRef.current.set(peerId, peer);
      const stream = localStreamRef.current;
      if (stream) {
        const outgoing = new MediaStream();
        stream.getAudioTracks().forEach((track) => outgoing.addTrack(track));
        const videoTrack = screenStreamRef.current?.getVideoTracks()[0] || stream.getVideoTracks()[0];
        if (videoTrack) outgoing.addTrack(videoTrack);
        const systemAudio = screenStreamRef.current?.getAudioTracks()[0];
        if (systemAudio) outgoing.addTrack(systemAudio);
        outgoing.getTracks().forEach((track) => {
          const sender = peer.addTrack(track, outgoing);
          if (track === systemAudio) screenAudioSendersRef.current.set(peerId, sender);
        });
      }
      peer.onicecandidate = (event) => {
        if (event.candidate) sendSignal(peerId, "candidate", event.candidate);
      };
      peer.ontrack = (event) => attachRemoteStream(peerId, event.streams[0]);
      peer.onconnectionstatechange = () => {
        if (["closed", "failed", "disconnected"].includes(peer.connectionState)) {
          peer.close();
          peersRef.current.delete(peerId);
          setRemoteStreams((current) => {
            const next = { ...current };
            delete next[peerId];
            return next;
          });
        }
      };
      if (initiator) {
        peer.createOffer()
          .then((offer) => peer.setLocalDescription(offer).then(() => sendSignal(peerId, "offer", offer)))
          .catch((err) => setError(err.message));
      }
      return peer;
    },
    [attachRemoteStream, sendSignal],
  );

  const handleSignal = useCallback(
    async ({ payload }) => {
      if (!payload || payload.target !== clientId.current || payload.source === clientId.current) return;
      const peer = createPeer(payload.source, false);
      if (payload.type === "offer") {
        await peer.setRemoteDescription(new RTCSessionDescription(payload.data));
        const answer = await peer.createAnswer();
        await peer.setLocalDescription(answer);
        await sendSignal(payload.source, "answer", answer);
      } else if (payload.type === "answer") {
        await peer.setRemoteDescription(new RTCSessionDescription(payload.data));
      } else if (payload.type === "candidate") {
        await peer.addIceCandidate(new RTCIceCandidate(payload.data));
      }
    },
    [createPeer, sendSignal],
  );

  const join = useCallback(async () => {
    if (!supabase || joined || !roomName) return;
    setError("");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: true });
      localStreamRef.current = stream;
      setLocalStream(stream);
      const channel = supabase.channel(`mentorship-room:${roomName}`, {
        config: { private: true, presence: { key: clientId.current }, broadcast: { self: false } },
      });
      channelRef.current = channel;
      channel.on("broadcast", { event: "webrtc-signal" }, handleSignal);
      channel.on("broadcast", { event: "moderation" }, ({ payload }) => {
        if (payload?.target !== clientId.current) return;
        if (payload.action === "mute") {
          localStreamRef.current?.getAudioTracks().forEach((track) => {
            track.enabled = false;
          });
          setMicEnabled(false);
        }
        if (payload.action === "kick") leave();
      });
      channel.on("presence", { event: "sync" }, () => {
        const state = channel.presenceState();
        setParticipants(state);
        Object.keys(state).forEach((peerId) => {
          if (peerId !== clientId.current) createPeer(peerId, clientId.current < peerId);
        });
      });
      await channel.subscribe(async (status) => {
        if (status === "SUBSCRIBED") {
          await channel.track({ name: displayName || "Participant", host: isHost, joinedAt: new Date().toISOString() });
        }
      });
      setJoined(true);
    } catch (err) {
      setError(err.message || "Unable to join the WebRTC room.");
    }
  }, [createPeer, displayName, handleSignal, isHost, joined, roomName, supabase]);

  const leave = useCallback(async () => {
    screenStreamRef.current?.getTracks().forEach((track) => track.stop());
    screenAudioSendersRef.current.clear();
    localStreamRef.current?.getTracks().forEach((track) => track.stop());
    peersRef.current.forEach((peer) => peer.close());
    peersRef.current.clear();
    if (channelRef.current && supabase) await supabase.removeChannel(channelRef.current);
    channelRef.current = null;
    localStreamRef.current = null;
    screenStreamRef.current = null;
    setLocalStream(null);
    setRemoteStreams({});
    setParticipants({});
    setSharingScreen(false);
    setJoined(false);
  }, [supabase]);

  const replaceTrack = useCallback(async (track) => {
    const operations = [];
    peersRef.current.forEach((peer) => {
      const sender = peer.getSenders().find((item) => item.track?.kind === track.kind);
      if (sender) operations.push(sender.replaceTrack(track));
    });
    await Promise.all(operations);
  }, []);

  const stopScreenShare = useCallback(async () => {
    const cameraTrack = localStreamRef.current?.getVideoTracks()[0];
    if (cameraTrack) await replaceTrack(cameraTrack);
    screenAudioSendersRef.current.forEach((sender, peerId) => {
      const peer = peersRef.current.get(peerId);
      if (peer) peer.removeTrack(sender);
    });
    screenAudioSendersRef.current.clear();
    screenStreamRef.current?.getTracks().forEach((track) => track.stop());
    screenStreamRef.current = null;
    setSharingScreen(false);
  }, [replaceTrack]);

  const shareScreen = useCallback(async () => {
    try {
      const screen = await navigator.mediaDevices.getDisplayMedia({ video: { cursor: "always" }, audio: true });
      const track = screen.getVideoTracks()[0];
      const systemAudio = screen.getAudioTracks()[0];
      screenStreamRef.current = screen;
      track.onended = stopScreenShare;
      await replaceTrack(track);
      if (systemAudio) {
        peersRef.current.forEach((peer, peerId) => {
          screenAudioSendersRef.current.set(peerId, peer.addTrack(systemAudio, screen));
        });
      }
      setSharingScreen(true);
    } catch (err) {
      setError(err.message || "Screen sharing was cancelled.");
    }
  }, [replaceTrack, stopScreenShare]);

  const moderate = async (target, action) => {
    await channelRef.current?.send({ type: "broadcast", event: "moderation", payload: { target, action } });
  };

  useEffect(() => {
    if (autoJoin) join();
    return () => {
      leave();
    };
  }, []);

  return (
    <div className="rounded-2xl border border-white/10 bg-slate-950/70 p-4 text-white">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="text-xs uppercase tracking-widest text-emerald-300">WebRTC Mentorship Room</div>
          <div className="font-semibold">{roomName}</div>
        </div>
        {!joined ? (
          <button onClick={join} className="rounded bg-emerald-600 px-4 py-2">Join room</button>
        ) : (
          <div className="flex flex-wrap gap-2">
            <button onClick={() => { localStreamRef.current?.getAudioTracks().forEach((t) => { t.enabled = !t.enabled; setMicEnabled(t.enabled); }); }} className="rounded bg-white/10 px-3 py-2">{micEnabled ? "Mute" : "Unmute"}</button>
            <button onClick={() => { localStreamRef.current?.getVideoTracks().forEach((t) => { t.enabled = !t.enabled; setCameraEnabled(t.enabled); }); }} className="rounded bg-white/10 px-3 py-2">{cameraEnabled ? "Camera off" : "Camera on"}</button>
            <button onClick={sharingScreen ? stopScreenShare : shareScreen} className="rounded bg-indigo-600 px-3 py-2">{sharingScreen ? "Stop sharing" : "Share entire screen"}</button>
            <button onClick={leave} className="rounded bg-red-600 px-3 py-2">Leave</button>
          </div>
        )}
      </div>
      {error && <div className="mt-3 rounded bg-red-950/60 p-2 text-sm text-red-200">{error}</div>}
      <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {localStream && <VideoTile stream={sharingScreen ? screenStreamRef.current : localStream} label={`${displayName || "You"} (you)`} muted />}
        {Object.entries(remoteStreams).map(([peerId, stream]) => {
          const presence = participants[peerId]?.[0] || {};
          return <VideoTile key={peerId} stream={stream} label={presence.name || "Participant"} />;
        })}
      </div>
      {isHost && joined && (
        <div className="mt-4">
          <div className="text-sm font-semibold">Participants</div>
          <div className="mt-2 grid gap-2 md:grid-cols-2">
            {Object.entries(participants).filter(([id]) => id !== clientId.current).map(([id, records]) => (
              <div key={id} className="flex items-center justify-between rounded bg-white/5 p-2 text-sm">
                <span>{records?.[0]?.name || id}</span>
                <span className="flex gap-2">
                  <button onClick={() => moderate(id, "mute")} className="rounded bg-amber-600 px-2 py-1">Mute</button>
                  <button onClick={() => moderate(id, "kick")} className="rounded bg-red-600 px-2 py-1">Remove</button>
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
