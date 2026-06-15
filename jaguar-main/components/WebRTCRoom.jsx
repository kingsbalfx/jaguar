import { useCallback, useEffect, useRef, useState } from "react";
import { getBrowserSupabaseClient } from "../lib/supabaseClient";
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
  useEffect(() => {
    if (ref.current && ref.current.srcObject !== stream) {
      ref.current.srcObject = stream || null;
      ref.current.play().catch(() => {});
    }
  }, [stream]);
  return (
    <div className="relative aspect-video min-h-[150px] overflow-hidden rounded-xl bg-black/60 sm:min-h-[180px]">
      <video ref={ref} autoPlay playsInline muted={muted} className="h-full w-full object-cover" />
      {!cameraEnabled && <div className="absolute inset-0 grid place-items-center bg-slate-900 text-3xl font-bold">{String(label || "?").slice(0, 1).toUpperCase()}</div>}
      <div className="absolute bottom-2 left-2 rounded bg-black/70 px-2 py-1 text-xs text-white">{label}</div>
      <div className="pointer-events-none absolute right-2 top-2 flex items-center gap-1.5 rounded-lg border border-white/15 bg-black/55 px-2 py-1 text-[10px] font-bold tracking-wider text-white backdrop-blur-sm"><img src="/jaguar.png" alt="" className="h-5 w-5 object-contain" />KINGSBALFX</div>
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
  const [connectionStatus, setConnectionStatus] = useState("ready");

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

  const attachRemoteStream = useCallback((peerId, stream) => {
    setRemoteStreams((current) => ({ ...current, [peerId]: stream }));
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
      peer.ontrack = (event) => attachRemoteStream(peerId, event.streams[0]);
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
    [attachRemoteStream, isHost, removePeer, sendSignal],
  );

  const handleSignal = useCallback(
    async ({ payload }) => {
      if (!payload || payload.target !== clientId.current || payload.source === clientId.current) return;
      let peer = peersRef.current.get(payload.source);
      if (payload.type === "offer" && peer && peer.signalingState !== "stable") {
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
        setStageRequests((current) => [
          ...current.filter((item) => item.source !== payload.source),
          payload,
        ]);
      });
      channel.on("broadcast", { event: "presenter-ready" }, ({ payload }) => {
        if (!payload?.source || payload.source === clientId.current) return;
        if (!peersRef.current.has(payload.source)) createPeer(payload.source, false);
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
  }, [audioDeviceId, createPeer, displayName, handleSignal, isHost, joined, loadDevices, roomName, supabase, videoDeviceId]);

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

  const publishRecording = useCallback(async (blob) => {
    if (!supabase || !blob?.size) return;
    const maxRecordingMb = Number(process.env.NEXT_PUBLIC_MAX_RECORDING_MB || 200);
    const fileSizeMb = blob.size / 1024 / 1024;
    setPublishingRecording(true);
    setRecordingStatus("Saving branded session recording...");
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
      const { error: uploadError } = await supabase.storage.from(bucket).uploadToSignedUrl(signed.path, signed.token, blob, {
        cacheControl: "3600",
        contentType: blob.type || "video/webm",
        upsert: false,
      });
      if (uploadError) throw uploadError;
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
      setRecordingStatus("Recording saved and published to the mentorship library.");
    } catch (err) {
      const recoveryUrl = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = recoveryUrl;
      anchor.download = `KINGSBALFX_${String(roomName || "live-session").replace(/[^a-zA-Z0-9_-]/g, "_")}_recovery.webm`;
      anchor.click();
      window.setTimeout(() => URL.revokeObjectURL(recoveryUrl), 1000);
      setRecordingStatus(`${err.message || "Unable to save recording."} A KINGSBALFX recovery copy was downloaded to this device.`);
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
      const stream = await createBrandedRecordingStream(presentationStream);
      recordingRenderCleanupRef.current = stream.cleanup;
      const audioTracks = [
        ...(screenStreamRef.current?.getAudioTracks() || []),
        ...(localStreamRef.current?.getAudioTracks() || []),
      ];
      [...new Set(audioTracks)].forEach((track) => stream.mediaStream.addTrack(track));
      const mimeType = MediaRecorder.isTypeSupported("video/webm;codecs=vp9,opus") ? "video/webm;codecs=vp9,opus" : "video/webm";
      const recorder = new MediaRecorder(stream.mediaStream, { mimeType, videoBitsPerSecond: 1800000 });
      recorderRef.current = recorder;
      recorder.ondataavailable = (event) => {
        if (event.data?.size) recordingChunksRef.current.push(event.data);
      };
      recorder.onstop = () => {
        window.clearInterval(recordingTimerRef.current);
        recordingTimerRef.current = null;
        recordingRenderCleanupRef.current?.();
        recordingRenderCleanupRef.current = null;
        const blob = new Blob(recordingChunksRef.current, { type: recorder.mimeType || "video/webm" });
        recordingChunksRef.current = [];
        recorderRef.current = null;
        setRecording(false);
        void publishRecording(blob);
      };
      recorder.start(1000);
      setRecording(true);
      setRecordingSeconds(0);
      recordingTimerRef.current = window.setInterval(() => setRecordingSeconds((current) => current + 1), 1000);
      setRecordingStatus("Recording in progress. The current host camera or shared screen is being captured.");
    } catch (err) {
      setRecordingStatus(err.message || "Unable to start recording.");
    }
  }, [isHost, publishRecording]);

  const stopRecording = useCallback(() => {
    if (recorderRef.current?.state === "recording") {
      setRecordingStatus("Finalizing recording before publishing...");
      recorderRef.current.stop();
    }
  }, []);

  useEffect(() => {
    loadDevices().catch(() => {});
    if (autoJoin) join();
    return () => {
      window.clearInterval(recordingTimerRef.current);
      if (recorderRef.current?.state === "recording") recorderRef.current.stop();
      else recordingRenderCleanupRef.current?.();
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
            <button onClick={toggleCamera} className={`rounded-lg px-3 py-2 text-sm sm:px-4 ${cameraEnabled ? "bg-white/10" : "bg-amber-600"}`}>{cameraEnabled ? "Turn camera off" : "Turn camera on"}</button>
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

async function createBrandedRecordingStream(sourceStream) {
  const videoTrack = sourceStream.getVideoTracks()[0];
  if (!videoTrack || typeof document === "undefined") {
    return { mediaStream: new MediaStream(sourceStream.getVideoTracks()), cleanup: () => {} };
  }

  const settings = videoTrack.getSettings();
  const width = settings.width || 1280;
  const height = settings.height || 720;
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const context = canvas.getContext("2d");
  if (!context || typeof canvas.captureStream !== "function") {
    return { mediaStream: new MediaStream(sourceStream.getVideoTracks()), cleanup: () => {} };
  }
  const video = document.createElement("video");
  video.srcObject = new MediaStream([videoTrack]);
  video.muted = true;
  video.playsInline = true;
  await video.play();

  const logo = new Image();
  logo.src = "/jaguar.png";
  await new Promise((resolve) => {
    logo.onload = resolve;
    logo.onerror = resolve;
  });

  let frameId = null;
  const draw = () => {
    context.drawImage(video, 0, 0, width, height);
    const padding = Math.max(14, Math.round(width * 0.015));
    const logoSize = Math.max(44, Math.round(width * 0.055));
    const boxWidth = Math.max(190, Math.round(width * 0.2));
    const boxHeight = logoSize + padding;
    const x = width - boxWidth - padding;
    const y = padding;
    context.fillStyle = "rgba(0, 0, 0, 0.58)";
    context.fillRect(x, y, boxWidth, boxHeight);
    if (logo.complete) context.drawImage(logo, x + padding / 2, y + padding / 2, logoSize, logoSize);
    context.fillStyle = "#ffffff";
    context.font = `700 ${Math.max(18, Math.round(width * 0.022))}px sans-serif`;
    context.fillText("KINGSBALFX", x + logoSize + padding, y + boxHeight * 0.62);
    frameId = window.requestAnimationFrame(draw);
  };
  draw();

  const mediaStream = canvas.captureStream(24);
  return {
    mediaStream,
    cleanup: () => {
      if (frameId) window.cancelAnimationFrame(frameId);
      mediaStream.getTracks().forEach((track) => track.stop());
      video.pause();
      video.srcObject = null;
    },
  };
}
