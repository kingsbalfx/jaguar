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

function VideoTile({ stream, label, muted = false, cameraEnabled = true }) {
  const ref = useRef(null);
  useEffect(() => {
    if (ref.current) ref.current.srcObject = stream || null;
  }, [stream]);
  return (
    <div className="relative aspect-video min-h-[150px] overflow-hidden rounded-xl bg-black/60 sm:min-h-[180px]">
      <video ref={ref} autoPlay playsInline muted={muted} className="h-full w-full object-cover" />
      {!cameraEnabled && <div className="absolute inset-0 grid place-items-center bg-slate-900 text-3xl font-bold">{String(label || "?").slice(0, 1).toUpperCase()}</div>}
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
  const presentingRef = useRef(isHost);
  const [localStream, setLocalStream] = useState(null);
  const [remoteStreams, setRemoteStreams] = useState({});
  const [participants, setParticipants] = useState({});
  const [joined, setJoined] = useState(false);
  const [micEnabled, setMicEnabled] = useState(true);
  const [cameraEnabled, setCameraEnabled] = useState(true);
  const [sharingScreen, setSharingScreen] = useState(false);
  const [error, setError] = useState("");
  const [joining, setJoining] = useState(false);
  const [devices, setDevices] = useState({ audio: [], video: [] });
  const [audioDeviceId, setAudioDeviceId] = useState("");
  const [videoDeviceId, setVideoDeviceId] = useState("");
  const [stageRequests, setStageRequests] = useState([]);
  const [requestSent, setRequestSent] = useState("");
  const [presenting, setPresenting] = useState(isHost);

  const loadDevices = useCallback(async () => {
    if (!navigator.mediaDevices?.enumerateDevices) return;
    const available = await navigator.mediaDevices.enumerateDevices();
    setDevices({
      audio: available.filter((device) => device.kind === "audioinput"),
      video: available.filter((device) => device.kind === "videoinput"),
    });
  }, []);

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
      if (stream && (isHost || presentingRef.current)) {
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
    [attachRemoteStream, isHost, sendSignal],
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
    setJoining(true);
    try {
      if (!navigator.mediaDevices?.getUserMedia) throw new Error("Camera and microphone access is not supported by this browser.");
      if (isHost) {
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: audioDeviceId ? { deviceId: { exact: audioDeviceId }, echoCancellation: true, noiseSuppression: true } : { echoCancellation: true, noiseSuppression: true },
          video: videoDeviceId ? { deviceId: { exact: videoDeviceId }, width: { ideal: 1280 }, height: { ideal: 720 } } : { width: { ideal: 1280 }, height: { ideal: 720 } },
        });
        localStreamRef.current = stream;
        setLocalStream(stream);
      }
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
        if (payload.action === "approve-presenter") startPresenting(payload.kind || "camera");
        if (payload.action === "stop-presenter") stopPresenting();
        if (payload.action === "kick") leave();
      });
      channel.on("broadcast", { event: "stage-request" }, ({ payload }) => {
        if (!isHost || !payload?.source) return;
        setStageRequests((current) => [
          ...current.filter((item) => item.source !== payload.source),
          payload,
        ]);
      });
      channel.on("broadcast", { event: "presenter-ready" }, ({ payload }) => {
        if (!payload?.source || payload.source === clientId.current) return;
        peersRef.current.get(payload.source)?.close();
        peersRef.current.delete(payload.source);
        createPeer(payload.source, false);
      });
      channel.on("broadcast", { event: "presenter-stopped" }, ({ payload }) => {
        const peerId = payload?.source;
        if (!peerId) return;
        peersRef.current.get(peerId)?.close();
        peersRef.current.delete(peerId);
        setRemoteStreams((current) => {
          const next = { ...current };
          delete next[peerId];
          return next;
        });
      });
      channel.on("presence", { event: "sync" }, () => {
        const state = channel.presenceState();
        setParticipants(state);
        if (isHost) {
          Object.keys(state).forEach((peerId) => {
            if (peerId !== clientId.current) createPeer(peerId, true);
          });
        }
      });
      await channel.subscribe(async (status) => {
        if (status === "SUBSCRIBED") {
          await channel.track({ name: displayName || "Participant", host: isHost, joinedAt: new Date().toISOString() });
        }
      });
      setJoined(true);
      await loadDevices();
    } catch (err) {
      setError(err.message || "Unable to join the WebRTC room.");
    } finally {
      setJoining(false);
    }
  }, [audioDeviceId, createPeer, displayName, handleSignal, isHost, joined, loadDevices, roomName, supabase, videoDeviceId]);

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
    setMicEnabled(true);
    setCameraEnabled(true);
    setPresenting(isHost);
    presentingRef.current = isHost;
    setRequestSent("");
    setJoined(false);
  }, [isHost, supabase]);

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
      setError("");
      if (!navigator.mediaDevices?.getDisplayMedia) throw new Error("Screen sharing is not supported by this browser.");
      const screen = await navigator.mediaDevices.getDisplayMedia({ video: true, audio: true });
      const track = screen.getVideoTracks()[0];
      if (!track) throw new Error("No window or screen was selected.");
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

  const requestStage = async (kind) => {
    setRequestSent(kind);
    await channelRef.current?.send({
      type: "broadcast",
      event: "stage-request",
      payload: { source: clientId.current, name: displayName || "Participant", kind },
    });
  };

  const startPresenting = useCallback(async (kind) => {
    try {
      setError("");
      const stream = kind === "screen"
        ? await navigator.mediaDevices.getDisplayMedia({ video: true, audio: true })
        : await navigator.mediaDevices.getUserMedia({
            audio: audioDeviceId ? { deviceId: { exact: audioDeviceId }, echoCancellation: true, noiseSuppression: true } : { echoCancellation: true, noiseSuppression: true },
            video: videoDeviceId ? { deviceId: { exact: videoDeviceId } } : true,
          });
      localStreamRef.current?.getTracks().forEach((track) => track.stop());
      localStreamRef.current = stream;
      presentingRef.current = true;
      setLocalStream(stream);
      setPresenting(true);
      setRequestSent("");
      stream.getVideoTracks()[0]?.addEventListener("ended", stopPresenting);
      peersRef.current.forEach((peer) => peer.close());
      peersRef.current.clear();
      const participantIds = Object.keys(channelRef.current?.presenceState?.() || {});
      participantIds.forEach((peerId) => {
        if (peerId !== clientId.current) createPeer(peerId, true);
      });
      await channelRef.current?.send({
        type: "broadcast",
        event: "presenter-ready",
        payload: { source: clientId.current, name: displayName || "Participant" },
      });
    } catch (err) {
      setError(err.message || "Unable to start presenting.");
    }
  }, [audioDeviceId, createPeer, displayName, videoDeviceId]);

  const stopPresenting = useCallback(async () => {
    if (isHost) return;
    localStreamRef.current?.getTracks().forEach((track) => track.stop());
    localStreamRef.current = null;
    presentingRef.current = false;
    setLocalStream(null);
    setPresenting(false);
    peersRef.current.forEach((peer) => peer.close());
    peersRef.current.clear();
    await channelRef.current?.send({
      type: "broadcast",
      event: "presenter-stopped",
      payload: { source: clientId.current },
    });
  }, [isHost]);

  const moderate = async (target, action) => {
    await channelRef.current?.send({ type: "broadcast", event: "moderation", payload: { target, action } });
  };

  const approvePresenter = async (request) => {
    setStageRequests((current) => current.filter((item) => item.source !== request.source));
    await channelRef.current?.send({
      type: "broadcast",
      event: "moderation",
      payload: { target: request.source, action: "approve-presenter", kind: request.kind },
    });
  };

  const toggleMic = () => {
    const track = localStreamRef.current?.getAudioTracks()[0];
    if (!track) return;
    track.enabled = !track.enabled;
    setMicEnabled(track.enabled);
  };

  const toggleCamera = () => {
    const track = localStreamRef.current?.getVideoTracks()[0];
    if (!track) return;
    track.enabled = !track.enabled;
    setCameraEnabled(track.enabled);
  };

  useEffect(() => {
    loadDevices().catch(() => {});
    if (autoJoin) join();
    return () => {
      leave();
    };
  }, []);

  const participantCount = Object.keys(participants).length || (joined ? 1 : 0);

  return (
    <div className="rounded-2xl border border-white/10 bg-gradient-to-b from-slate-900 to-slate-950 p-3 text-white shadow-2xl sm:p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="text-xs uppercase tracking-widest text-emerald-300">WebRTC Mentorship Room</div>
          <div className="font-semibold">{roomName}</div>
          <div className="mt-2 flex flex-wrap gap-2 text-xs">
            <span className={`rounded-full px-2 py-1 ${joined ? "bg-emerald-500/20 text-emerald-200" : "bg-white/10 text-gray-300"}`}>{joined ? "Connected" : "Ready to join"}</span>
            <span className="rounded-full bg-white/10 px-2 py-1 text-gray-300">{participantCount} participant{participantCount === 1 ? "" : "s"}</span>
          </div>
        </div>
        {!joined ? (
          <button onClick={join} disabled={joining} className="w-full rounded-xl bg-emerald-600 px-5 py-3 font-semibold shadow-lg disabled:opacity-60 sm:w-auto">{joining ? "Joining..." : "Join room"}</button>
        ) : (
          <div className="grid w-full grid-cols-1 gap-2 rounded-xl bg-black/30 p-2 sm:grid-cols-2 lg:flex lg:w-auto lg:flex-wrap">
            {!isHost && !presenting && <button onClick={() => requestStage("camera")} disabled={Boolean(requestSent)} className="rounded-lg bg-sky-600 px-3 py-2 text-sm disabled:opacity-60 sm:px-4">{requestSent === "camera" ? "Camera request sent" : "Raise hand for camera"}</button>}
            {!isHost && !presenting && <button onClick={() => requestStage("screen")} disabled={Boolean(requestSent)} className="rounded-lg bg-violet-600 px-3 py-2 text-sm disabled:opacity-60 sm:px-4">{requestSent === "screen" ? "Screen request sent" : "Request screen share"}</button>}
            {!isHost && presenting && <button onClick={stopPresenting} className="rounded-lg bg-red-600 px-3 py-2 text-sm sm:px-4">Leave stage</button>}
            {(isHost || presenting) && <>
            <button onClick={toggleMic} className={`rounded-lg px-3 py-2 text-sm sm:px-4 ${micEnabled ? "bg-white/10" : "bg-amber-600"}`}>{micEnabled ? "Mute microphone" : "Unmute microphone"}</button>
            <button onClick={toggleCamera} className={`rounded-lg px-3 py-2 text-sm sm:px-4 ${cameraEnabled ? "bg-white/10" : "bg-amber-600"}`}>{cameraEnabled ? "Turn camera off" : "Turn camera on"}</button>
            {isHost && <button onClick={sharingScreen ? stopScreenShare : shareScreen} className="rounded-lg bg-indigo-600 px-3 py-2 text-sm sm:px-4">{sharingScreen ? "Stop sharing" : "Share screen"}</button>}
            </>}
            <button onClick={leave} className="rounded-lg bg-red-600 px-3 py-2 text-sm sm:px-4">Leave room</button>
          </div>
        )}
      </div>
      {!joined && (
        <div className="mt-4 grid gap-3 rounded-xl border border-white/10 bg-black/20 p-3 md:grid-cols-2">
          <label className="text-xs text-gray-300">Microphone
            <select value={audioDeviceId} onChange={(e) => setAudioDeviceId(e.target.value)} className="mt-1 w-full rounded bg-slate-900 p-2 text-white">
              <option value="">Default microphone</option>
              {devices.audio.map((device, index) => <option key={device.deviceId} value={device.deviceId}>{device.label || `Microphone ${index + 1}`}</option>)}
            </select>
          </label>
          <label className="text-xs text-gray-300">Camera
            <select value={videoDeviceId} onChange={(e) => setVideoDeviceId(e.target.value)} className="mt-1 w-full rounded bg-slate-900 p-2 text-white">
              <option value="">Default camera</option>
              {devices.video.map((device, index) => <option key={device.deviceId} value={device.deviceId}>{device.label || `Camera ${index + 1}`}</option>)}
            </select>
          </label>
        </div>
      )}
      {error && <div className="mt-3 rounded bg-red-950/60 p-2 text-sm text-red-200">{error}</div>}
      <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {localStream && <VideoTile stream={sharingScreen ? screenStreamRef.current : localStream} label={`${displayName || "You"} (you)`} muted cameraEnabled={sharingScreen || cameraEnabled} />}
        {Object.entries(remoteStreams).map(([peerId, stream]) => {
          const presence = participants[peerId]?.[0] || {};
          return <VideoTile key={peerId} stream={stream} label={presence.name || "Participant"} />;
        })}
      </div>
      {isHost && joined && (
        <div className="mt-4">
          {stageRequests.length > 0 && (
            <div className="mb-4 rounded-xl border border-sky-400/20 bg-sky-500/10 p-3">
              <div className="text-sm font-semibold">Stage requests</div>
              <div className="mt-2 space-y-2">
                {stageRequests.map((request) => (
                  <div key={request.source} className="flex flex-wrap items-center justify-between gap-2 text-sm">
                    <span>{request.name} requests {request.kind === "screen" ? "screen sharing" : "camera access"}</span>
                    <button onClick={() => approvePresenter(request)} className="rounded bg-emerald-600 px-3 py-2">Approve</button>
                  </div>
                ))}
              </div>
            </div>
          )}
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
