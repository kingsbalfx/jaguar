import { useCallback, useEffect, useRef, useState } from "react";
import { Device } from "mediasoup-client";
import FeedbackMessage from "./FeedbackMessage";
import WebRTCRoom from "./WebRTCRoom";

function sfuUrl() {
  const configured = process.env.NEXT_PUBLIC_KINGSBAL_SFU_URL;
  if (configured) return configured;
  if (typeof window === "undefined") return "";
  if (["localhost", "127.0.0.1"].includes(window.location.hostname)) return "ws://localhost:4443/sfu";
  return "";
}

function hasConfiguredSfu() {
  if (process.env.NEXT_PUBLIC_KINGSBAL_SFU_URL) return true;
  if (typeof window === "undefined") return false;
  if (["localhost", "127.0.0.1"].includes(window.location.hostname)) return true;
  return false;
}

function VideoTile({ stream, label, muted = false }) {
  const videoRef = useRef(null);
  const [zoom, setZoom] = useState(1);
  const [fit, setFit] = useState("contain");

  useEffect(() => {
    if (!videoRef.current || videoRef.current.srcObject === stream) return;
    videoRef.current.srcObject = stream || null;
    videoRef.current.play().catch(() => {});
  }, [stream]);

  return (
    <div className="group relative aspect-video overflow-hidden rounded-2xl border border-white/10 bg-black">
      <video
        ref={videoRef}
        autoPlay
        playsInline
        muted={muted}
        className={`h-full w-full ${fit === "cover" ? "object-cover" : "object-contain"}`}
        style={{ transform: `scale(${zoom})`, transformOrigin: "center center" }}
      />
      <div className="absolute bottom-2 left-2 rounded bg-black/75 px-2 py-1 text-xs font-semibold text-white">{label}</div>
      <div className="pointer-events-none absolute right-3 top-3 flex items-center gap-2 rounded-xl border border-white/25 bg-black/75 px-3 py-2 text-xs font-black tracking-wider text-white shadow-2xl shadow-black/50 backdrop-blur-sm">
        <img src="/jaguar.png" alt="" className="h-8 w-8 object-contain" />KINGSBALFX
      </div>
      <div className="pointer-events-none absolute inset-0 grid place-items-center opacity-10">
        <div className="-rotate-12 text-4xl font-black tracking-[0.25em] text-white sm:text-6xl">KINGSBALFX</div>
      </div>
      <div className="absolute bottom-2 right-2 flex flex-wrap justify-end gap-1 rounded-xl border border-white/10 bg-black/70 p-1 text-xs text-white opacity-100 backdrop-blur sm:opacity-0 sm:transition sm:group-hover:opacity-100">
        <button type="button" onClick={() => setZoom((value) => Math.max(1, Number((value - 0.25).toFixed(2))))} className="rounded bg-white/10 px-2 py-1">-</button>
        <span className="rounded bg-white/10 px-2 py-1">{Math.round(zoom * 100)}%</span>
        <button type="button" onClick={() => setZoom((value) => Math.min(4, Number((value + 0.25).toFixed(2))))} className="rounded bg-white/10 px-2 py-1">+</button>
        <button type="button" onClick={() => setFit((value) => value === "cover" ? "contain" : "cover")} className="rounded bg-white/10 px-2 py-1">{fit === "cover" ? "Fit" : "Fill"}</button>
      </div>
    </div>
  );
}

export default function SFURoom({ roomName, roomTitle = "", displayName = "Subscriber", isHost = false, recordingTitle = "", recordingSegment = "all" }) {
  const socketRef = useRef(null);
  const requestsRef = useRef(new Map());
  const deviceRef = useRef(null);
  const sendTransportRef = useRef(null);
  const recvTransportRef = useRef(null);
  const localStreamRef = useRef(null);
  const localProducersRef = useRef(new Map());
  const consumedProducersRef = useRef(new Set());
  const originalTitleRef = useRef("");
  const stageAlertTimerRef = useRef(null);
  const [joined, setJoined] = useState(false);
  const [joining, setJoining] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState("ready");
  const [error, setError] = useState("");
  const [peerCount, setPeerCount] = useState(0);
  const [localStream, setLocalStream] = useState(null);
  const [remoteStreams, setRemoteStreams] = useState({});
  const [stageRequests, setStageRequests] = useState([]);
  const [stageAlert, setStageAlert] = useState(null);
  const [approvedKinds, setApprovedKinds] = useState(new Set());
  const [requestStatus, setRequestStatus] = useState("");
  const [micEnabled, setMicEnabled] = useState(true);
  const [cameraEnabled, setCameraEnabled] = useState(true);

  const sfuConfigured = hasConfiguredSfu();

  const rpc = useCallback((action, data = {}) => new Promise((resolve, reject) => {
    const socket = socketRef.current;
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      reject(new Error("SFU is not connected."));
      return;
    }
    const id = crypto.randomUUID();
    requestsRef.current.set(id, { resolve, reject });
    socket.send(JSON.stringify({ id, action, data }));
    window.setTimeout(() => {
      if (!requestsRef.current.has(id)) return;
      requestsRef.current.delete(id);
      reject(new Error("SFU request timed out."));
    }, 15000);
  }), []);

  const consumeProducer = useCallback(async (producer) => {
    if (!producer?.id || consumedProducersRef.current.has(producer.id)) return;
    const device = deviceRef.current;
    const recvTransport = recvTransportRef.current;
    if (!device || !recvTransport) return;
    consumedProducersRef.current.add(producer.id);
    try {
      const params = await rpc("consume", {
        transportId: recvTransport.id,
        producerId: producer.id,
        rtpCapabilities: device.rtpCapabilities,
      });
      const consumer = await recvTransport.consume(params);
      const stream = new MediaStream([consumer.track]);
      const label = params.producerAppData?.displayName || producer.displayName || "Participant";
      const source = params.producerAppData?.source || producer.appData?.source || params.kind;
      setRemoteStreams((current) => ({
        ...current,
        [producer.id]: { stream, label: source === "screen" ? `${label} screen` : label },
      }));
    } catch (err) {
      consumedProducersRef.current.delete(producer.id);
      setError(err.message || "Unable to receive a live stream.");
    }
  }, [rpc]);

  const createTransport = useCallback(async (direction) => {
    const params = await rpc("createWebRtcTransport", { direction });
    const device = deviceRef.current;
    const transport = direction === "send"
      ? device.createSendTransport(params)
      : device.createRecvTransport(params);
    transport.on("connect", ({ dtlsParameters }, callback, errback) => {
      rpc("connectTransport", { transportId: transport.id, dtlsParameters }).then(callback).catch(errback);
    });
    if (direction === "send") {
      transport.on("produce", ({ kind, rtpParameters, appData }, callback, errback) => {
        rpc("produce", { transportId: transport.id, kind, rtpParameters, appData }).then(({ id }) => callback({ id })).catch(errback);
      });
    }
    return transport;
  }, [rpc]);

  const publishTracks = useCallback(async (stream, source) => {
    if (!sendTransportRef.current) sendTransportRef.current = await createTransport("send");
    for (const track of stream.getTracks()) {
      const producer = await sendTransportRef.current.produce({
        track,
        appData: { source, displayName: isHost ? "Admin" : displayName },
        encodings: track.kind === "video" ? [{ maxBitrate: source === "screen" ? 1_400_000 : 850_000 }] : undefined,
      });
      localProducersRef.current.set(producer.id, producer);
      track.onended = () => {
        producer.close();
        rpc("closeProducer", { producerId: producer.id }).catch(() => {});
        localProducersRef.current.delete(producer.id);
      };
    }
  }, [createTransport, displayName, isHost, rpc]);

  const publishCamera = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: true,
        video: { width: { ideal: 960, max: 1280 }, height: { ideal: 540, max: 720 }, frameRate: { ideal: 24, max: 30 } },
      });
      localStreamRef.current = stream;
      setLocalStream(stream);
      setMicEnabled(true);
      setCameraEnabled(true);
      await publishTracks(stream, "camera");
    } catch (err) {
      setError(err.message || "Unable to publish camera.");
    }
  }, [publishTracks]);

  const shareScreen = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getDisplayMedia({ video: true, audio: true });
      localStreamRef.current = stream;
      setLocalStream(stream);
      setCameraEnabled(true);
      await publishTracks(stream, "screen");
    } catch (err) {
      setError(err.message || "Unable to share screen.");
    }
  }, [publishTracks]);

  const toggleMic = useCallback(() => {
    setMicEnabled((current) => {
      const next = !current;
      localStreamRef.current?.getAudioTracks().forEach((track) => {
        track.enabled = next;
      });
      return next;
    });
  }, []);

  const toggleCamera = useCallback(() => {
    setCameraEnabled((current) => {
      const next = !current;
      localStreamRef.current?.getVideoTracks().forEach((track) => {
        track.enabled = next;
      });
      return next;
    });
  }, []);

  const join = useCallback(async () => {
    if (joined || joining) return;
    setJoining(true);
    setError("");
    setConnectionStatus("connecting");
    try {
      const url = sfuUrl();
      if (!url) throw new Error("NEXT_PUBLIC_KINGSBAL_SFU_URL is not configured.");
      const socket = new WebSocket(url);
      socketRef.current = socket;
      await new Promise((resolve, reject) => {
        socket.onopen = resolve;
        socket.onerror = () => reject(new Error("Unable to connect to the KINGSBALFX SFU server."));
      });

      socket.onmessage = (event) => {
        const message = JSON.parse(event.data);
        if (message.id && requestsRef.current.has(message.id)) {
          const pending = requestsRef.current.get(message.id);
          requestsRef.current.delete(message.id);
          message.ok ? pending.resolve(message.data) : pending.reject(new Error(message.error));
          return;
        }
        if (message.event === "newProducer") void consumeProducer(message.data);
        if (message.event === "producerClosed") {
          consumedProducersRef.current.delete(message.data?.producerId);
          setRemoteStreams((current) => {
            const next = { ...current };
            delete next[message.data?.producerId];
            return next;
          });
        }
        if (message.event === "peerJoined" || message.event === "peerLeft") setPeerCount(message.data?.peerCount || 0);
        if (message.event === "stageRequest" && isHost) {
          setStageAlert(message.data);
          if (typeof document !== "undefined") {
            originalTitleRef.current = originalTitleRef.current || document.title;
            document.title = `REQUEST: ${message.data?.displayName || "Student"} needs approval`;
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
                body: `${message.data?.displayName || "A student"} requests ${message.data?.kind === "screen" ? "screen sharing" : "camera/microphone"} approval.`,
                icon: "/jaguar.png",
              });
            }
          } catch {}
          setStageRequests((current) => [message.data, ...current.filter((item) => item.peerId !== message.data.peerId || item.kind !== message.data.kind)].slice(0, 30));
        }
        if (message.event === "stageApproved") {
          setApprovedKinds((current) => new Set([...current, message.data?.kind]));
          setRequestStatus(`Admin approved ${message.data?.kind === "screen" ? "screen sharing" : "camera/microphone"}.`);
        }
      };
      socket.onclose = () => {
        setConnectionStatus("disconnected");
        setJoined(false);
      };

      const joinData = await rpc("join", { roomId: roomName, displayName: isHost ? "Admin" : displayName, isHost });
      const device = new Device();
      await device.load({ routerRtpCapabilities: joinData.routerRtpCapabilities });
      deviceRef.current = device;
      recvTransportRef.current = await createTransport("recv");
      setPeerCount(joinData.peerCount || 1);
      setJoined(true);
      setConnectionStatus("connected");
      for (const producer of joinData.producers || []) void consumeProducer(producer);
    } catch (err) {
      setError(err.message || "Unable to join KINGSBALFX SFU room.");
      socketRef.current?.close();
    } finally {
      setJoining(false);
    }
  }, [consumeProducer, createTransport, displayName, isHost, joined, joining, roomName, rpc]);

  const requestStage = async (kind) => {
    setRequestStatus("");
    try {
      await rpc("requestStage", { kind });
      setRequestStatus("Request sent to Admin. Wait for approval.");
    } catch (err) {
      setRequestStatus(err.message || "Unable to send request.");
    }
  };

  const approveStage = async (request) => {
    try {
      await rpc("approveStage", { targetPeerId: request.peerId, kind: request.kind });
      setStageRequests((current) => current.filter((item) => item !== request));
      setStageAlert(null);
    } catch (err) {
      setError(err.message || "Unable to approve request.");
    }
  };

  const leave = useCallback(() => {
    for (const producer of localProducersRef.current.values()) producer.close();
    localProducersRef.current.clear();
    localStreamRef.current?.getTracks().forEach((track) => track.stop());
    localStreamRef.current = null;
    setLocalStream(null);
    recvTransportRef.current?.close();
    sendTransportRef.current?.close();
    recvTransportRef.current = null;
    sendTransportRef.current = null;
    socketRef.current?.close();
    socketRef.current = null;
    consumedProducersRef.current.clear();
    setRemoteStreams({});
    setJoined(false);
    setConnectionStatus("ready");
  }, []);

  useEffect(() => () => {
    window.clearTimeout(stageAlertTimerRef.current);
    if (originalTitleRef.current && typeof document !== "undefined") document.title = originalTitleRef.current;
    leave();
  }, [leave]);

  const canPublish = isHost || approvedKinds.has("camera") || approvedKinds.has("screen");

  if (!sfuConfigured) {
    return (
      <div className="space-y-3">
        <div className="rounded-2xl border border-amber-300/30 bg-amber-500/10 p-3 text-sm text-amber-100">
          SFU server URL is not configured yet, so this room is using the emergency in-app WebRTC fallback. Supabase cannot host SFU media routing; use this fallback for tonight until a VPS is available.
        </div>
        <WebRTCRoom
          roomName={roomName}
          roomTitle={roomTitle}
          displayName={displayName}
          isHost={isHost}
          recordingTitle={recordingTitle || roomTitle}
          recordingSegment={recordingSegment}
        />
      </div>
    );
  }

  return (
    <div className="rounded-3xl border border-emerald-400/20 bg-slate-950/90 p-4 text-white shadow-2xl shadow-black/40">
      <div className="flex flex-col gap-3 border-b border-white/10 pb-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="text-xs uppercase tracking-widest text-emerald-300">KINGSBALFX SFU Live Room</div>
          <div className="text-lg font-semibold">{roomTitle || roomName}</div>
          <div className="text-xs text-gray-400">{connectionStatus} · {peerCount} connected</div>
        </div>
        <div className="flex flex-wrap gap-2">
          {!joined ? (
            <button type="button" onClick={join} disabled={joining} className="rounded-xl bg-emerald-600 px-4 py-2 text-sm font-semibold disabled:opacity-60">{joining ? "Joining..." : "Join SFU room"}</button>
          ) : (
            <button type="button" onClick={leave} className="rounded-xl bg-red-600 px-4 py-2 text-sm font-semibold">Leave</button>
          )}
          {joined && canPublish && <button type="button" onClick={publishCamera} className="rounded-xl bg-white/10 px-4 py-2 text-sm font-semibold">Camera</button>}
          {joined && canPublish && <button type="button" onClick={shareScreen} className="rounded-xl bg-indigo-600 px-4 py-2 text-sm font-semibold">Share screen</button>}
          {joined && localStream && <button type="button" onClick={toggleMic} className={`rounded-xl px-4 py-2 text-sm font-semibold ${micEnabled ? "bg-white/10" : "bg-amber-600"}`}>{micEnabled ? "Mute mic" : "Unmute mic"}</button>}
          {joined && localStream && <button type="button" onClick={toggleCamera} className={`rounded-xl px-4 py-2 text-sm font-semibold ${cameraEnabled ? "bg-white/10" : "bg-amber-600"}`}>{cameraEnabled ? "Mute video" : "Unmute video"}</button>}
          {joined && !isHost && <button type="button" onClick={() => requestStage("camera")} className="rounded-xl bg-white/10 px-4 py-2 text-sm font-semibold">Request to speak</button>}
          {joined && !isHost && <button type="button" onClick={() => requestStage("screen")} className="rounded-xl bg-white/10 px-4 py-2 text-sm font-semibold">Request screen</button>}
        </div>
      </div>

      {error && <div className="mt-3"><FeedbackMessage message={error} type="error" /></div>}
      {requestStatus && <div className="mt-3"><FeedbackMessage message={requestStatus} type={/approved/i.test(requestStatus) ? "success" : "info"} /></div>}

      {isHost && stageRequests.length > 0 && (
        <div className="fixed inset-x-3 top-20 z-[120] mx-auto max-w-3xl rounded-2xl border border-sky-300/30 bg-slate-950/95 p-3 text-white shadow-2xl shadow-black/50 backdrop-blur">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <div className="text-xs uppercase tracking-[0.22em] text-sky-200">Permission request pending</div>
              <div className="text-sm font-semibold">
                {(stageAlert || stageRequests[0])?.displayName || "Subscriber"} requests {(stageAlert || stageRequests[0])?.kind === "screen" ? "screen sharing" : "camera/microphone"} approval.
              </div>
              <div className="text-xs text-gray-300">This stays visible while you are live or sharing your screen inside the browser.</div>
            </div>
            <div className="flex flex-wrap gap-2">
              {stageRequests.slice(0, 3).map((request) => (
                <button key={`${request.peerId}-${request.kind}`} type="button" onClick={() => approveStage(request)} className="rounded-lg bg-emerald-600 px-3 py-2 text-sm font-semibold">
                  Approve {request.displayName || "student"}
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

      <div className="mt-4 grid gap-4 xl:grid-cols-2">
        {localStream && <VideoTile stream={localStream} label={isHost ? "Admin preview" : "My preview"} muted />}
        {Object.entries(remoteStreams).map(([id, item]) => <VideoTile key={id} stream={item.stream} label={item.label} />)}
        {!localStream && Object.keys(remoteStreams).length === 0 && (
          <div className="rounded-2xl border border-white/10 bg-black/30 p-6 text-sm text-gray-300">
            Join the SFU room. Admin should start camera or share screen once; viewers receive the stream without overloading the admin browser.
          </div>
        )}
      </div>
    </div>
  );
}
