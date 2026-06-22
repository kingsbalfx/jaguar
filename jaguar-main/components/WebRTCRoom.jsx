import { useCallback, useEffect, useRef, useState } from "react";
import { getBrowserSupabaseClient } from "../lib/supabaseClient";
import { formatUploadSize, storageLimitMessage, uploadToSignedUrlWithProgress } from "../lib/signed-upload-progress";
import FeedbackMessage from "./FeedbackMessage";

const DEFAULT_ICE_SERVERS = [{ urls: "stun:stun.l.google.com:19302" }, { urls: "stun:stun1.l.google.com:19302" }];
const CAMERA_VIDEO = { width: { ideal: 960, max: 1280 }, height: { ideal: 540, max: 720 }, frameRate: { ideal: 24, max: 30 } };

async function optimizeSender(sender, kind) {
  if (!sender?.track) return;
  sender.track.contentHint = kind === "screen" ? "detail" : kind === "video" ? "motion" : "speech";
  if (sender.track.kind !== "video") return;
  const parameters = sender.getParameters();
  parameters.degradationPreference = kind === "screen" ? "maintain-resolution" : "maintain-framerate";
  parameters.encodings = parameters.encodings?.length ? parameters.encodings : [{}];
  parameters.encodings[0].maxBitrate = kind === "screen" ? 1400000 : 850000;
  parameters.encodings[0].maxFramerate = kind === "screen" ? 15 : 24;
  try { await sender.setParameters(parameters); } catch {}
}

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
  const containerRef = useRef(null);
  const [zoom, setZoom] = useState(1);
  const [fitMode, setFitMode] = useState("contain");
  useEffect(() => {
    if (ref.current && ref.current.srcObject !== stream) {
      ref.current.srcObject = stream || null;
      ref.current.play().catch(() => {});
    }
  }, [stream]);
  const zoomBy = (amount) => setZoom((current) => Math.max(1, Math.min(4, Number((current + amount).toFixed(1)))));
  const resetView = () => {
    setZoom(1);
    setFitMode("contain");
  };
  const openFullscreen = async () => {
    try {
      if (containerRef.current?.requestFullscreen) await containerRef.current.requestFullscreen();
      else if (ref.current?.webkitEnterFullscreen) ref.current.webkitEnterFullscreen();
    } catch {}
  };
  return (
    <div ref={containerRef} className="group relative aspect-video min-h-[150px] overflow-hidden rounded-xl bg-black/60 sm:min-h-[180px]">
      <video
        ref={ref}
        autoPlay
        playsInline
        muted={muted}
        className={`h-full w-full ${fitMode === "fill" ? "object-cover" : "object-contain"}`}
        style={{ transform: `scale(${zoom})`, transformOrigin: "center center" }}
      />
      {!cameraEnabled && <div className="absolute inset-0 grid place-items-center bg-slate-900 text-3xl font-bold">{String(label || "?").slice(0, 1).toUpperCase()}</div>}
      <div className="absolute bottom-2 left-2 rounded bg-black/70 px-2 py-1 text-xs text-white">{label}</div>
      <div className="pointer-events-none absolute right-3 top-3 flex items-center gap-2 rounded-xl border border-white/25 bg-black/75 px-3 py-2 text-xs font-black tracking-wider text-white shadow-2xl shadow-black/50 backdrop-blur-sm"><img src="/jaguar.png" alt="" className="h-8 w-8 object-contain" />KINGSBALFX</div>
      <div className="pointer-events-none absolute inset-0 grid place-items-center opacity-10">
        <div className="-rotate-12 text-4xl font-black tracking-[0.25em] text-white sm:text-6xl">KINGSBALFX</div>
      </div>
      <div className="absolute right-2 bottom-2 z-10 flex flex-wrap justify-end gap-1 rounded-xl border border-white/10 bg-black/70 p-1 text-xs text-white opacity-100 backdrop-blur sm:opacity-0 sm:transition sm:group-hover:opacity-100">
        <button type="button" onClick={() => zoomBy(-0.25)} className="rounded bg-white/10 px-2 py-1 hover:bg-white/20" aria-label="Zoom out">-</button>
        <span className="rounded bg-white/10 px-2 py-1">{Math.round(zoom * 100)}%</span>
        <button type="button" onClick={() => zoomBy(0.25)} className="rounded bg-white/10 px-2 py-1 hover:bg-white/20" aria-label="Zoom in">+</button>
        <button type="button" onClick={() => setFitMode((current) => current === "fill" ? "contain" : "fill")} className="rounded bg-white/10 px-2 py-1 hover:bg-white/20">{fitMode === "fill" ? "Fit" : "Fill"}</button>
        <button type="button" onClick={resetView} className="rounded bg-white/10 px-2 py-1 hover:bg-white/20">Reset</button>
        <button type="button" onClick={openFullscreen} className="rounded bg-emerald-600 px-2 py-1 hover:bg-emerald-500">Full</button>
      </div>
      <div className="pointer-events-none absolute inset-x-0 bottom-0 h-14 bg-gradient-to-t from-black/55 to-transparent" />
    </div>
  );
}

export default function WebRTCRoom({ roomName, roomTitle = "", displayName, isHost = false, autoJoin = false, recordingTitle = "", recordingSegment = "all" }) {
  const supabase = getBrowserSupabaseClient();
  const clientId = useRef(typeof crypto !== "undefined" ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`);
  const channelRef = useRef(null);
  const peersRef = useRef(new Map());
  const pendingCandidatesRef = useRef(new Map());
  const intentionalLeaveRef = useRef(false);
  const screenAudioSendersRef = useRef(new Map());
  const localStreamRef = useRef(null);
  const screenStreamRef = useRef(null);
  const presentingRef = useRef(isHost);
  const activityRegisteredRef = useRef(false);
  const recorderRef = useRef(null);
  const recordingChunksRef = useRef([]);
  const recordingTimerRef = useRef(null);
  const recordingRenderCleanupRef = useRef(null);
  const lastRecordingUrlRef = useRef("");
  const originalTitleRef = useRef("");
  const stageAlertTimerRef = useRef(null);
  const remoteMediaStreamsRef = useRef(new Map());
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
  const [approvedKind, setApprovedKind] = useState("");
  const [recording, setRecording] = useState(false);
  const [recordingSeconds, setRecordingSeconds] = useState(0);
  const [publishingRecording, setPublishingRecording] = useState(false);
  const [recordingStatus, setRecordingStatus] = useState("");
  const [lastRecording, setLastRecording] = useState(null);
  const [connectionStatus, setConnectionStatus] = useState("ready");
  const [stageAlert, setStageAlert] = useState(null);

  const setLiveRoomActivity = useCallback((active) => {
    if (typeof window === "undefined") return;
    if (activityRegisteredRef.current === active) return;
    activityRegisteredRef.current = active;
    const current = Number(window.__kingsbalActiveLiveRooms || 0);
    window.__kingsbalActiveLiveRooms = active ? current + 1 : Math.max(0, current - 1);
    window.dispatchEvent(new CustomEvent("kingsbal:live-room-activity", { detail: { active } }));
  }, []);

  const removePeer = useCallback((peerId) => {
    peersRef.current.get(peerId)?.close();
    peersRef.current.delete(peerId);
    pendingCandidatesRef.current.delete(peerId);
    screenAudioSendersRef.current.delete(peerId);
    remoteMediaStreamsRef.current.delete(peerId);
    setRemoteStreams((current) => {
      const next = { ...current };
      delete next[peerId];
      return next;
    });
  }, []);

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

  const attachRemoteTrack = useCallback((peerId, event) => {
    const incoming = event.streams?.[0] || remoteMediaStreamsRef.current.get(peerId) || new MediaStream();
    if (!event.streams?.[0] && event.track && !incoming.getTracks().some((track) => track.id === event.track.id)) {
      incoming.addTrack(event.track);
    }
    remoteMediaStreamsRef.current.set(peerId, incoming);
    setRemoteStreams((current) => ({ ...current, [peerId]: incoming }));
    event.track.onunmute = () => {
      setRemoteStreams((current) => ({ ...current, [peerId]: incoming }));
    };
  }, []);

  const notifyStageRequest = useCallback((payload) => {
    if (!payload?.source) return;
    setStageAlert(payload);
    if (typeof document !== "undefined") {
      originalTitleRef.current = originalTitleRef.current || document.title;
      document.title = `REQUEST: ${payload.name || "Student"} needs approval`;
      window.clearTimeout(stageAlertTimerRef.current);
      stageAlertTimerRef.current = window.setTimeout(() => {
        document.title = originalTitleRef.current || document.title;
      }, 20000);
    }
    try {
      const AudioContext = window.AudioContext || window.webkitAudioContext;
      if (AudioContext) {
        const ctx = new AudioContext();
        const oscillator = ctx.createOscillator();
        const gain = ctx.createGain();
        oscillator.frequency.value = 880;
        gain.gain.value = 0.08;
        oscillator.connect(gain);
        gain.connect(ctx.destination);
        oscillator.start();
        oscillator.stop(ctx.currentTime + 0.22);
      }
    } catch {}
    try {
      if ("Notification" in window && Notification.permission === "granted") {
        new Notification("KINGSBALFX stage request", {
          body: `${payload.name || "A student"} requests ${payload.kind === "screen" ? "screen sharing" : "camera/microphone"} approval.`,
          icon: "/jaguar.png",
        });
      }
    } catch {}
  }, []);

  const createPeer = useCallback(
    (peerId, initiator) => {
      if (peersRef.current.has(peerId)) return peersRef.current.get(peerId);
      const peer = new RTCPeerConnection({ iceServers: iceServers(), bundlePolicy: "max-bundle", iceCandidatePoolSize: 4 });
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
          void optimizeSender(sender, track === systemAudio ? "audio" : track.kind === "video" && screenStreamRef.current ? "screen" : track.kind);
          if (track === systemAudio) screenAudioSendersRef.current.set(peerId, sender);
        });
      }
      peer.onicecandidate = (event) => {
        if (event.candidate) sendSignal(peerId, "candidate", event.candidate);
      };
      peer.ontrack = (event) => attachRemoteTrack(peerId, event);
      peer.onconnectionstatechange = () => {
        if (peer.connectionState === "connected") {
          setConnectionStatus("connected");
          setError("");
        }
        if (["failed", "disconnected"].includes(peer.connectionState)) {
          setConnectionStatus("reconnecting");
          window.setTimeout(async () => {
            if (!["failed", "disconnected"].includes(peer.connectionState)) return;
            try {
              peer.restartIce?.();
              const offer = await peer.createOffer({ iceRestart: true });
              await peer.setLocalDescription(offer);
              await sendSignal(peerId, "offer", offer);
            } catch {
              removePeer(peerId);
              await channelRef.current?.send({
                type: "broadcast",
                event: "reconnect-request",
                payload: { source: clientId.current },
              });
            }
          }, 1500);
        }
      };
      if (initiator) {
        peer.createOffer()
          .then((offer) => peer.setLocalDescription(offer).then(() => sendSignal(peerId, "offer", offer)))
          .catch((err) => setError(err.message));
      }
      return peer;
    },
    [attachRemoteTrack, isHost, removePeer, sendSignal],
  );

  const handleSignal = useCallback(
    async ({ payload }) => {
      if (!payload || payload.target !== clientId.current || payload.source === clientId.current) return;
      let peer = peersRef.current.get(payload.source);
      if (payload.type === "offer" && peer) {
        removePeer(payload.source);
        peer = null;
      }
      peer = peer || createPeer(payload.source, false);
      if (payload.type === "offer") {
        await peer.setRemoteDescription(new RTCSessionDescription(payload.data));
        for (const candidate of pendingCandidatesRef.current.get(payload.source) || []) {
          await peer.addIceCandidate(candidate).catch(() => {});
        }
        pendingCandidatesRef.current.delete(payload.source);
        const answer = await peer.createAnswer();
        await peer.setLocalDescription(answer);
        await sendSignal(payload.source, "answer", answer);
      } else if (payload.type === "answer") {
        await peer.setRemoteDescription(new RTCSessionDescription(payload.data));
        for (const candidate of pendingCandidatesRef.current.get(payload.source) || []) {
          await peer.addIceCandidate(candidate).catch(() => {});
        }
        pendingCandidatesRef.current.delete(payload.source);
      } else if (payload.type === "candidate") {
        const candidate = new RTCIceCandidate(payload.data);
        if (peer.remoteDescription) await peer.addIceCandidate(candidate);
        else pendingCandidatesRef.current.set(payload.source, [...(pendingCandidatesRef.current.get(payload.source) || []), candidate]);
      }
    },
    [createPeer, removePeer, sendSignal],
  );

  const join = useCallback(async () => {
    if (!supabase || joined || !roomName) return;
    setError("");
    setJoining(true);
    setConnectionStatus("connecting");
    intentionalLeaveRef.current = false;
    try {
      if (!navigator.mediaDevices?.getUserMedia) throw new Error("Camera and microphone access is not supported by this browser.");
      if (isHost && !localStreamRef.current?.active) {
        let stream;
        try {
          stream = await navigator.mediaDevices.getUserMedia({
            audio: audioDeviceId ? { deviceId: { exact: audioDeviceId }, echoCancellation: true, noiseSuppression: true } : { echoCancellation: true, noiseSuppression: true },
            video: videoDeviceId ? { deviceId: { exact: videoDeviceId }, ...CAMERA_VIDEO } : CAMERA_VIDEO,
          });
        } catch {
          try {
            stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true }, video: false });
            setCameraEnabled(false);
          } catch {
            stream = new MediaStream();
            setCameraEnabled(false);
            setMicEnabled(false);
          }
        }
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
        if (payload.action === "approve-presenter") {
          setApprovedKind(payload.kind || "camera");
          setRequestSent("");
        }
        if (payload.action === "stop-presenter") stopPresenting();
        if (payload.action === "kick") leave();
      });
      channel.on("broadcast", { event: "stage-request" }, ({ payload }) => {
        if (!isHost || !payload?.source) return;
        notifyStageRequest(payload);
        setStageRequests((current) => [
          ...current.filter((item) => item.source !== payload.source),
          payload,
        ]);
      });
      channel.on("broadcast", { event: "presenter-ready" }, ({ payload }) => {
        if (!payload?.source || payload.source === clientId.current) return;
        removePeer(payload.source);
        createPeer(payload.source, false);
      });
      channel.on("broadcast", { event: "presenter-stopped" }, ({ payload }) => {
        const peerId = payload?.source;
        if (!peerId) return;
        removePeer(peerId);
      });
      channel.on("broadcast", { event: "reconnect-request" }, ({ payload }) => {
        if (!isHost || !payload?.source) return;
        removePeer(payload.source);
        createPeer(payload.source, true);
      });
      channel.on("presence", { event: "sync" }, () => {
        const state = channel.presenceState();
        setParticipants(state);
        if (isHost) {
          Object.keys(state).forEach((peerId) => {
            if (peerId !== clientId.current) createPeer(peerId, true);
          });
        }
        const presentIds = new Set(Object.keys(state));
        peersRef.current.forEach((_peer, peerId) => {
          if (!presentIds.has(peerId)) removePeer(peerId);
        });
      });
      channel.subscribe(async (status) => {
        if (status === "SUBSCRIBED") {
          if (isHost && "Notification" in window && Notification.permission === "default") {
            Notification.requestPermission().catch(() => {});
          }
          await channel.track({ name: displayName || "Participant", host: isHost, joinedAt: new Date().toISOString() });
          setConnectionStatus("connected");
        } else if (status === "CHANNEL_ERROR" || status === "TIMED_OUT") {
          setConnectionStatus("reconnecting");
        } else if (status === "CLOSED") {
          if (intentionalLeaveRef.current) return;
          setConnectionStatus("disconnected");
          channelRef.current = null;
          setJoined(false);
          setLiveRoomActivity(false);
        }
      });
      setJoined(true);
      setLiveRoomActivity(true);
      await loadDevices();
    } catch (err) {
      setError(err.message || "Unable to join the WebRTC room.");
    } finally {
      setJoining(false);
    }
  }, [audioDeviceId, createPeer, displayName, handleSignal, isHost, joined, loadDevices, notifyStageRequest, roomName, supabase, videoDeviceId]);

  const leave = useCallback(async () => {
    if (recorderRef.current?.state === "recording" || publishingRecording) {
      setRecordingStatus("Stop the recording and wait for publishing to finish before leaving the room.");
      return;
    }
    intentionalLeaveRef.current = true;
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
    remoteMediaStreamsRef.current.clear();
    setParticipants({});
    setSharingScreen(false);
    setMicEnabled(true);
    setCameraEnabled(true);
    setPresenting(isHost);
    presentingRef.current = isHost;
    setRequestSent("");
    setApprovedKind("");
    setJoined(false);
    setConnectionStatus("ready");
    setLiveRoomActivity(false);
  }, [isHost, publishingRecording, setLiveRoomActivity, supabase]);

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
      if (!window.isSecureContext) throw new Error("Screen sharing requires a secure HTTPS connection.");
      if (!navigator.mediaDevices?.getDisplayMedia) throw new Error("This mobile browser does not provide screen sharing. Use its latest Chrome/Edge version or share your camera instead.");
      let screen;
      try {
        screen = await navigator.mediaDevices.getDisplayMedia({ video: { frameRate: { ideal: 15, max: 24 } }, audio: false });
      } catch (firstError) {
        if (firstError?.name === "NotAllowedError") throw firstError;
        screen = await navigator.mediaDevices.getDisplayMedia({ video: true });
      }
      const track = screen.getVideoTracks()[0];
      if (!track) throw new Error("No window or screen was selected.");
      screenStreamRef.current = screen;
      track.onended = stopScreenShare;
      track.contentHint = "detail";
      await replaceTrack(track);
      peersRef.current.forEach((peer) => {
        const sender = peer.getSenders().find((item) => item.track?.kind === "video");
        void optimizeSender(sender, "screen");
      });
      setSharingScreen(true);
    } catch (err) {
      const message = err?.name === "NotAllowedError"
        ? "Screen sharing was cancelled or blocked. Use Chrome or Edge on HTTPS, select a screen/window, then click the browser Share button."
        : err.message || "Screen sharing was cancelled.";
      setError(message);
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
        ? await navigator.mediaDevices.getDisplayMedia({ video: true, audio: false })
        : await navigator.mediaDevices.getUserMedia({
            audio: audioDeviceId ? { deviceId: { exact: audioDeviceId }, echoCancellation: true, noiseSuppression: true } : { echoCancellation: true, noiseSuppression: true },
            video: videoDeviceId ? { deviceId: { exact: videoDeviceId }, ...CAMERA_VIDEO } : CAMERA_VIDEO,
          });
      localStreamRef.current?.getTracks().forEach((track) => track.stop());
      localStreamRef.current = stream;
      presentingRef.current = true;
      setLocalStream(stream);
      setPresenting(true);
      setRequestSent("");
      setApprovedKind("");
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
    setStageAlert((current) => current?.source === request.source ? null : current);
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

  const saveRecordingLocally = useCallback((recordingFile = lastRecording) => {
    if (!recordingFile?.url) return;
    const anchor = document.createElement("a");
    anchor.href = recordingFile.url;
    anchor.download = recordingFile.name || `KINGSBALFX_${String(roomName || "live-session").replace(/[^a-zA-Z0-9_-]/g, "_")}.webm`;
    anchor.click();
  }, [lastRecording, roomName]);

  const publishRecording = useCallback(async (blob) => {
    if (!supabase || !blob?.size) return;
    const maxRecordingMb = Number(process.env.NEXT_PUBLIC_MAX_RECORDING_MB || 5120);
    const fileSizeMb = blob.size / 1024 / 1024;
    setPublishingRecording(true);
    setRecordingStatus(`Preparing ${formatUploadSize(blob.size)} recording upload. Keep this page open until it reaches 100%.`);
    try {
      if (fileSizeMb > maxRecordingMb) {
        throw new Error(`Recording is ${fileSizeMb.toFixed(1)} MB, above the ${maxRecordingMb} MB cloud limit.`);
      }
      const safeRoom = String(roomName || "live-session").replace(/[^a-zA-Z0-9_-]/g, "_");
      const fileName = `KINGSBALFX_${safeRoom}_${Date.now()}.webm`;
      const bucketMap = {
        premium: process.env.NEXT_PUBLIC_STORAGE_BUCKET_PREMIUM || "premium",
        vip: process.env.NEXT_PUBLIC_STORAGE_BUCKET_VIP || "vip",
        pro: process.env.NEXT_PUBLIC_STORAGE_BUCKET_PRO || "pro",
        lifetime: process.env.NEXT_PUBLIC_STORAGE_BUCKET_LIFETIME || "lifetime",
      };
      const bucket = bucketMap[recordingSegment] || process.env.NEXT_PUBLIC_STORAGE_BUCKET || "public";
      const signedResponse = await fetch("/api/admin/storage/signed-upload", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ bucket, segment: recordingSegment, fileName }),
      });
      const signed = await signedResponse.json();
      if (!signedResponse.ok) throw new Error(signed.error || "Unable to prepare recording upload.");
      const uploadBucket = signed.bucket || bucket;
      const uploadUrl = signed.signedUrl || `${process.env.NEXT_PUBLIC_SUPABASE_URL}/storage/v1/object/upload/sign/${uploadBucket}/${signed.path}?token=${signed.token}`;
      await uploadToSignedUrlWithProgress({
        signedUrl: uploadUrl,
        file: blob,
        cacheControl: "3600",
        onProgress: (progress, loaded, total) => {
          setRecordingStatus(`Uploading recording: ${progress}% (${formatUploadSize(loaded)} of ${formatUploadSize(total)}). Keep this page open.`);
        },
      });
      const contentResponse = await fetch("/api/admin/content-items", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: recordingTitle || `KINGSBALFX Live Session - ${new Date().toLocaleDateString()}`,
          description: "Branded mentorship live-session recording.",
          segment: recordingSegment,
          mediaType: "video",
          storagePath: signed.path,
          publicUrl: signed.publicUrl,
          isPublished: true,
        }),
      });
      const content = await contentResponse.json();
      if (!contentResponse.ok) throw new Error(content.error || "Recording uploaded but could not be published.");
      setRecordingStatus("Recording saved and published to the mentorship library. Manual local copy remains available below.");
    } catch (err) {
      setRecordingStatus(`${storageLimitMessage(err.message) || "Unable to save recording."} Use the manual save button below to keep the full local KINGSBALFX recording.`);
    } finally {
      setPublishingRecording(false);
    }
  }, [recordingSegment, recordingTitle, roomName, supabase]);

  const startRecording = useCallback(async () => {
    if (!isHost) return;
    const presentationStream = screenStreamRef.current || localStreamRef.current;
    if (!presentationStream || typeof MediaRecorder === "undefined") {
      setRecordingStatus("Join the room first. Recording also requires a browser with MediaRecorder support.");
      return;
    }
    try {
      recordingChunksRef.current = [];
      const stream = await createReliableRecordingStream({
        presentationStream,
        screenStream: screenStreamRef.current,
        localStream: localStreamRef.current,
      });
      recordingRenderCleanupRef.current = stream.cleanup;
      if (!stream.mediaStream.getTracks().length) throw new Error("No active screen, camera, or audio track is available to record.");
      const mimeType = getSupportedRecordingMimeType();
      const recorder = new MediaRecorder(stream.mediaStream, {
        ...(mimeType ? { mimeType } : {}),
        videoBitsPerSecond: screenStreamRef.current ? 900000 : 750000,
        audioBitsPerSecond: 96000,
      });
      recorderRef.current = recorder;
      recorder.ondataavailable = (event) => {
        if (event.data?.size) recordingChunksRef.current.push(event.data);
      };
      (stream.sourceTrack || stream.mediaStream.getVideoTracks()[0])?.addEventListener("ended", () => {
        if (recorder.state === "recording") {
          try { recorder.requestData(); } catch {}
          recorder.stop();
        }
      }, { once: true });
      recorder.onstop = async () => {
        window.clearInterval(recordingTimerRef.current);
        recordingTimerRef.current = null;
        recordingRenderCleanupRef.current?.();
        recordingRenderCleanupRef.current = null;
        const rawBlob = new Blob(recordingChunksRef.current, { type: recorder.mimeType || "video/webm" });
        if (!rawBlob.size) {
          recordingChunksRef.current = [];
          recorderRef.current = null;
          setRecording(false);
          setRecordingStatus("The browser returned an empty recording. Keep the room open, start recording again, and make sure the shared screen or camera stays active.");
          return;
        }
        const safeRoom = String(roomName || "live-session").replace(/[^a-zA-Z0-9_-]/g, "_");
        const name = `KINGSBALFX_${safeRoom}_${new Date().toISOString().replace(/[:.]/g, "-")}.webm`;
        recordingChunksRef.current = [];
        recorderRef.current = null;
        setRecording(false);
        if (lastRecordingUrlRef.current) URL.revokeObjectURL(lastRecordingUrlRef.current);
        const url = URL.createObjectURL(rawBlob);
        lastRecordingUrlRef.current = url;
        setLastRecording({ url, name, size: rawBlob.size, watermarked: stream.watermarked !== false });
        setRecordingStatus(stream.watermarked === false
          ? "Recording is ready. Browser did not support live watermark capture, so upload is starting with the raw copy."
          : "Watermarked recording is ready. Upload is starting now; keep this page open.");
        void publishRecording(rawBlob);
      };
      recorder.start(10000);
      setRecording(true);
      setRecordingSeconds(0);
      recordingTimerRef.current = window.setInterval(() => setRecordingSeconds((current) => current + 1), 1000);
      setRecordingStatus("Recording in progress. KINGSBALFX watermark is applied live during recording.");
    } catch (err) {
      setRecordingStatus(err.message || "Unable to start recording.");
    }
  }, [isHost, publishRecording, roomName]);

  const stopRecording = useCallback(() => {
    if (recorderRef.current?.state === "recording") {
      setRecordingStatus("Finalizing recording before publishing...");
      try { recorderRef.current.requestData(); } catch {}
      recorderRef.current.stop();
    }
  }, []);

  useEffect(() => {
    loadDevices().catch(() => {});
    if (autoJoin) join();
    return () => {
      window.clearTimeout(stageAlertTimerRef.current);
      if (originalTitleRef.current) document.title = originalTitleRef.current;
      window.clearInterval(recordingTimerRef.current);
      if (recorderRef.current?.state === "recording") recorderRef.current.stop();
      else recordingRenderCleanupRef.current?.();
      if (lastRecordingUrlRef.current) URL.revokeObjectURL(lastRecordingUrlRef.current);
      leave();
    };
  }, []);

  useEffect(() => {
    if (!joined) return undefined;
    const healthTimer = window.setInterval(async () => {
      window.dispatchEvent(new CustomEvent("kingsbal:live-room-activity", { detail: { active: true } }));
      const state = channelRef.current?.presenceState?.() || {};
      if (isHost) {
        Object.keys(state).forEach((peerId) => {
          if (peerId !== clientId.current && !peersRef.current.has(peerId)) createPeer(peerId, true);
        });
      } else if (Object.keys(remoteStreams).length === 0) {
        setConnectionStatus("reconnecting");
        await channelRef.current?.send({ type: "broadcast", event: "reconnect-request", payload: { source: clientId.current } });
      }
    }, 8000);
    return () => window.clearInterval(healthTimer);
  }, [createPeer, isHost, joined, remoteStreams]);

  useEffect(() => {
    if (connectionStatus !== "disconnected" || joined || joining) return undefined;
    const reconnectTimer = window.setTimeout(() => void join(), 1500);
    return () => window.clearTimeout(reconnectTimer);
  }, [connectionStatus, join, joined, joining]);

  const participantCount = Object.keys(participants).length || (joined ? 1 : 0);

  return (
    <div className="rounded-2xl border border-white/10 bg-gradient-to-b from-slate-900 to-slate-950 p-3 text-white shadow-2xl sm:p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="text-xs uppercase tracking-widest text-emerald-300">WebRTC Mentorship Room</div>
          <div className="font-semibold">{roomTitle || roomName}</div>
          {roomTitle && <div className="text-xs text-gray-400">{roomName}</div>}
          <div className="mt-2 flex flex-wrap gap-2 text-xs">
            <span className={`rounded-full px-2 py-1 ${joined ? "bg-emerald-500/20 text-emerald-200" : "bg-white/10 text-gray-300"}`}>{joined ? "Connected" : "Ready to join"}</span>
            <span className="rounded-full bg-sky-500/15 px-2 py-1 text-sky-200">{connectionStatus}</span>
            <span className="rounded-full bg-white/10 px-2 py-1 text-gray-300">{participantCount} participant{participantCount === 1 ? "" : "s"}</span>
          </div>
        </div>
        {!joined ? (
          <button onClick={join} disabled={joining} className="w-full rounded-xl bg-emerald-600 px-5 py-3 font-semibold shadow-lg disabled:opacity-60 sm:w-auto">{joining ? "Joining..." : "Join room"}</button>
        ) : (
          <div className="grid w-full grid-cols-1 gap-2 rounded-xl bg-black/30 p-2 sm:grid-cols-2 lg:flex lg:w-auto lg:flex-wrap">
            {!isHost && !presenting && !approvedKind && <button onClick={() => requestStage("camera")} disabled={Boolean(requestSent)} className="rounded-lg bg-sky-600 px-3 py-2 text-sm disabled:opacity-60 sm:px-4">{requestSent === "camera" ? "Camera request sent" : "Raise hand for camera"}</button>}
            {!isHost && !presenting && !approvedKind && <button onClick={() => requestStage("screen")} disabled={Boolean(requestSent)} className="rounded-lg bg-violet-600 px-3 py-2 text-sm disabled:opacity-60 sm:px-4">{requestSent === "screen" ? "Screen request sent" : "Request screen share"}</button>}
            {!isHost && !presenting && approvedKind && <button onClick={() => startPresenting(approvedKind)} className="rounded-lg bg-emerald-600 px-3 py-2 text-sm sm:px-4">Start approved {approvedKind === "screen" ? "screen share" : "camera"}</button>}
            {!isHost && presenting && <button onClick={stopPresenting} className="rounded-lg bg-red-600 px-3 py-2 text-sm sm:px-4">Leave stage</button>}
            {(isHost || presenting) && <>
            <button onClick={toggleMic} className={`rounded-lg px-3 py-2 text-sm sm:px-4 ${micEnabled ? "bg-white/10" : "bg-amber-600"}`}>{micEnabled ? "Mute microphone" : "Unmute microphone"}</button>
            <button onClick={toggleCamera} className={`rounded-lg px-3 py-2 text-sm sm:px-4 ${cameraEnabled ? "bg-white/10" : "bg-amber-600"}`}>{cameraEnabled ? "Mute camera" : "Unmute camera"}</button>
            {isHost && <button onClick={sharingScreen ? stopScreenShare : shareScreen} className="rounded-lg bg-indigo-600 px-3 py-2 text-sm sm:px-4">{sharingScreen ? "Stop sharing" : "Share screen"}</button>}
            {isHost && <button onClick={recording ? stopRecording : startRecording} disabled={publishingRecording} className={`rounded-lg px-3 py-2 text-sm disabled:opacity-60 sm:px-4 ${recording ? "bg-red-600" : "bg-fuchsia-600"}`}>{publishingRecording ? "Publishing recording..." : recording ? `Stop recording (${formatDuration(recordingSeconds)})` : "Record session"}</button>}
            </>}
            <button onClick={leave} disabled={recording || publishingRecording} className="rounded-lg bg-red-600 px-3 py-2 text-sm disabled:cursor-not-allowed disabled:opacity-50 sm:px-4">{recording ? "Stop recording before leaving" : publishingRecording ? "Publishing before leaving" : "Leave room"}</button>
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
      <FeedbackMessage
        message={error || recordingStatus}
        type={error || /unable|requires|could not|above|failed|recovery/i.test(recordingStatus) ? "error" : "info"}
      />
      {isHost && joined && stageRequests.length > 0 && (
        <div className="fixed inset-x-3 top-20 z-[120] mx-auto max-w-3xl rounded-2xl border border-sky-300/30 bg-slate-950/95 p-3 text-white shadow-2xl shadow-black/50 backdrop-blur">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <div className="text-xs uppercase tracking-[0.22em] text-sky-200">Stage request pending</div>
              <div className="text-sm font-semibold">
                {(stageAlert || stageRequests[0]).name || "Student"} requests {(stageAlert || stageRequests[0]).kind === "screen" ? "screen sharing" : "camera/microphone"} approval.
              </div>
              <div className="text-xs text-gray-300">This stays visible while you are live or sharing your screen.</div>
            </div>
            <div className="flex flex-wrap gap-2">
              {stageRequests.slice(0, 3).map((request) => (
                <button key={request.source} onClick={() => approvePresenter(request)} className="rounded-lg bg-emerald-600 px-3 py-2 text-sm font-semibold hover:bg-emerald-500">
                  Approve {request.name || "student"}
                </button>
              ))}
              <button
                type="button"
                onClick={() => {
                  setStageAlert(null);
                  window.clearTimeout(stageAlertTimerRef.current);
                  if (originalTitleRef.current) document.title = originalTitleRef.current;
                }}
                className="rounded-lg bg-white/10 px-3 py-2 text-sm hover:bg-white/20"
              >
                Dismiss alert
              </button>
            </div>
          </div>
        </div>
      )}
      {isHost && lastRecording && (
        <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-emerald-300/20 bg-emerald-500/10 p-3 text-sm text-emerald-100">
          <div>
            <div className="font-semibold">{lastRecording.watermarked ? "Watermarked local backup ready" : "Raw local backup ready"}</div>
            <div className="text-xs text-emerald-100/75">{lastRecording.name} ({(lastRecording.size / 1024 / 1024).toFixed(1)} MB). This local backup stays available while cloud upload runs.</div>
          </div>
          <button type="button" onClick={() => saveRecordingLocally()} className="rounded-lg bg-emerald-600 px-4 py-2 font-semibold text-white hover:bg-emerald-500">
            {lastRecording.watermarked ? "Download watermarked backup" : "Download raw backup"}
          </button>
        </div>
      )}
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

function formatDuration(totalSeconds) {
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}

function getSupportedRecordingMimeType() {
  if (typeof MediaRecorder === "undefined") return "";
  return [
    "video/webm;codecs=vp8,opus",
    "video/webm;codecs=vp9,opus",
    "video/webm",
  ].find((type) => MediaRecorder.isTypeSupported(type)) || "";
}

async function createReliableRecordingStream({ presentationStream, screenStream, localStream }) {
  const sourceTrack = presentationStream?.getVideoTracks?.()[0] || localStream?.getVideoTracks?.()[0];
  const audioTracks = [
    ...(screenStream?.getAudioTracks?.() || []),
    ...(localStream?.getAudioTracks?.() || []),
  ].filter((track, index, tracks) => track?.readyState === "live" && tracks.indexOf(track) === index);

  if (!sourceTrack || typeof document === "undefined") {
    const mediaStream = new MediaStream();
    audioTracks.forEach((track) => mediaStream.addTrack(track));
    return { mediaStream, sourceTrack: null, watermarked: false, cleanup: () => {} };
  }

  try {
    sourceTrack.contentHint = screenStream ? "detail" : "motion";
    const sourceStream = new MediaStream([sourceTrack]);
    const video = document.createElement("video");
    video.srcObject = sourceStream;
    video.muted = true;
    video.playsInline = true;
    video.autoplay = true;
    await video.play().catch(() => {});

    const canvas = document.createElement("canvas");
    canvas.width = sourceTrack.getSettings?.().width || video.videoWidth || 1280;
    canvas.height = sourceTrack.getSettings?.().height || video.videoHeight || 720;
    const context = canvas.getContext("2d");
    if (!context || typeof canvas.captureStream !== "function") throw new Error("canvas recording unsupported");

    const logo = new Image();
    logo.src = "/jaguar.png";
    await Promise.race([waitForImage(logo), new Promise((resolve) => window.setTimeout(resolve, 1000))]);

    const output = canvas.captureStream(24);
    audioTracks.forEach((track) => output.addTrack(track));
    let frameId = null;
    const draw = () => {
      const width = video.videoWidth || canvas.width;
      const height = video.videoHeight || canvas.height;
      if (width && height && (canvas.width !== width || canvas.height !== height)) {
        canvas.width = width;
        canvas.height = height;
      }
      context.drawImage(video, 0, 0, canvas.width, canvas.height);
      drawRecordingWatermark(context, logo, canvas.width, canvas.height);
      frameId = window.requestAnimationFrame(draw);
    };
    draw();

    return {
      mediaStream: output,
      sourceTrack,
      watermarked: true,
      cleanup: () => {
        if (frameId) window.cancelAnimationFrame(frameId);
        output.getVideoTracks().forEach((track) => track.stop());
        video.pause();
        video.srcObject = null;
      },
    };
  } catch {
    const mediaStream = new MediaStream();
    mediaStream.addTrack(sourceTrack);
    audioTracks.forEach((track) => mediaStream.addTrack(track));
    return { mediaStream, sourceTrack, watermarked: false, cleanup: () => {} };
  }
}

async function createWatermarkedRecordingBlob(sourceBlob, onProgress = () => {}) {
  if (!sourceBlob?.size || typeof document === "undefined" || typeof MediaRecorder === "undefined") {
    throw new Error("The browser cannot apply the KINGSBALFX watermark to this recording.");
  }

  const sourceUrl = URL.createObjectURL(sourceBlob);
  const video = document.createElement("video");
  video.src = sourceUrl;
  video.playsInline = true;
  video.preload = "auto";
  video.volume = 0.001;
  await waitForMediaEvent(video, "loadedmetadata");

  const sourceDuration = Number.isFinite(video.duration) ? video.duration : 0;
  const width = video.videoWidth || 1280;
  const height = video.videoHeight || 720;
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const context = canvas.getContext("2d");
  if (!context || typeof canvas.captureStream !== "function") {
    URL.revokeObjectURL(sourceUrl);
    throw new Error("This browser cannot prepare the KINGSBALFX branded recording.");
  }

  const logo = new Image();
  logo.src = "/jaguar.png";
  await Promise.race([
    waitForImage(logo),
    new Promise((resolve) => window.setTimeout(resolve, 1500)),
  ]);

  const outputStream = canvas.captureStream(24);
  const sourceStream = video.captureStream?.() || video.mozCaptureStream?.();
  sourceStream?.getAudioTracks?.().forEach((track) => outputStream.addTrack(track));
  const mimeType = getSupportedRecordingMimeType();
  const recorder = new MediaRecorder(outputStream, {
    ...(mimeType ? { mimeType } : {}),
    videoBitsPerSecond: 900000,
    audioBitsPerSecond: 96000,
  });
  const chunks = [];
  let frameId = null;
  let lastProgress = -1;

  recorder.ondataavailable = (event) => {
    if (event.data?.size) chunks.push(event.data);
  };
  const finished = new Promise((resolve, reject) => {
    recorder.onerror = () => reject(new Error("Unable to finish the KINGSBALFX watermarked recording."));
    recorder.onstop = resolve;
  });

  const draw = () => {
    context.drawImage(video, 0, 0, width, height);
    drawRecordingWatermark(context, logo, width, height);
    if (sourceDuration) {
      const progress = Math.min(99, Math.round((video.currentTime / sourceDuration) * 100));
      if (progress !== lastProgress) {
        lastProgress = progress;
        onProgress(progress);
      }
    }
    frameId = window.requestAnimationFrame(draw);
  };

  recorder.start(10000);
  try {
    await video.play();
  } catch {
    video.muted = true;
    await video.play();
  }
  draw();
  await waitForMediaEvent(video, "ended");
  await new Promise((resolve) => window.setTimeout(resolve, 350));
  try { recorder.requestData(); } catch {}
  recorder.stop();
  await finished;
  if (frameId) window.cancelAnimationFrame(frameId);
  outputStream.getTracks().forEach((track) => track.stop());
  video.pause();
  video.src = "";
  URL.revokeObjectURL(sourceUrl);
  onProgress(100);

  const watermarkedBlob = new Blob(chunks, { type: recorder.mimeType || "video/webm" });
  if (!watermarkedBlob.size) throw new Error("The browser returned an empty branded recording.");
  if (sourceDuration > 60) {
    const brandedDuration = await readRecordingDuration(watermarkedBlob);
    if (brandedDuration && brandedDuration + 5 < sourceDuration) {
      throw new Error("The browser shortened the branded copy, so it was not uploaded.");
    }
  }
  return watermarkedBlob;
}

function drawRecordingWatermark(context, logo, width, height) {
  const padding = Math.max(18, Math.round(width * 0.018));
  const logoSize = Math.max(56, Math.round(width * 0.065));
  const boxWidth = Math.max(250, Math.round(width * 0.24));
  const boxHeight = logoSize + padding;
  const x = width - boxWidth - padding;
  const y = padding;
  context.fillStyle = "rgba(0, 0, 0, 0.72)";
  context.fillRect(x, y, boxWidth, boxHeight);
  context.strokeStyle = "rgba(255, 255, 255, 0.28)";
  context.lineWidth = Math.max(1, Math.round(width * 0.0015));
  context.strokeRect(x, y, boxWidth, boxHeight);
  if (logo.complete) context.drawImage(logo, x + padding / 2, y + padding / 2, logoSize, logoSize);
  context.fillStyle = "#ffffff";
  context.font = `800 ${Math.max(22, Math.round(width * 0.025))}px sans-serif`;
  context.fillText("KINGSBALFX", x + logoSize + padding, y + boxHeight * 0.62);

  context.save();
  context.globalAlpha = 0.13;
  context.translate(width / 2, height / 2);
  context.rotate(-Math.PI / 8);
  context.fillStyle = "#ffffff";
  context.font = `800 ${Math.max(44, Math.round(width * 0.055))}px sans-serif`;
  context.textAlign = "center";
  context.fillText("KINGSBALFX", 0, 0);
  context.restore();
}

function waitForMediaEvent(target, event) {
  return new Promise((resolve, reject) => {
    target.addEventListener(event, resolve, { once: true });
    target.addEventListener("error", () => reject(new Error("Unable to process the recording media.")), { once: true });
  });
}

function waitForImage(image) {
  return new Promise((resolve) => {
    if (image.complete) return resolve();
    image.onload = resolve;
    image.onerror = resolve;
  });
}

function readRecordingDuration(blob) {
  return new Promise((resolve) => {
    const url = URL.createObjectURL(blob);
    const video = document.createElement("video");
    video.preload = "metadata";
    video.onloadedmetadata = () => {
      const duration = Number.isFinite(video.duration) ? video.duration : 0;
      URL.revokeObjectURL(url);
      resolve(duration);
    };
    video.onerror = () => {
      URL.revokeObjectURL(url);
      resolve(0);
    };
    video.src = url;
  });
}
