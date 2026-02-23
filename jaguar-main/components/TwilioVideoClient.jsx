// components/TwilioVideoClient.jsx
import React, { useEffect, useRef, useState } from "react";

/**
 * Minimal Twilio Video client component.
 * Requires an API endpoint at /api/twilio/token that returns { token, roomName }.
 *
 * Server: pages/api/twilio/token.js (provided below)
 */
export default function TwilioVideoClient({
  roomName = "global-room",
  audioOnly = false,
  allowScreenShare = false,
}) {
  const [status, setStatus] = useState("idle");
  const [isSharing, setIsSharing] = useState(false);
  const localRef = useRef(null);
  const screenRef = useRef(null);
  const remoteRef = useRef(null);
  const roomRef = useRef(null);
  const screenTrackRef = useRef(null);

  useEffect(() => {
    let mounted = true;
    async function init() {
      setStatus("requesting-token");
      try {
        const res = await fetch("/api/twilio/token", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ roomName }),
        });
        if (!res.ok) {
          setStatus("token-failed");
          return;
        }
        const { token, roomName } = await res.json();

        // load twilio-video at runtime
        const TwilioVideo = await import("twilio-video");
        if (!mounted) return;

        const room = await TwilioVideo.connect(token, {
          name: roomName,
          audio: true,
          video: audioOnly ? false : { width: 640 },
        });
        roomRef.current = room;
        setStatus("connected");

        // attach local tracks
        const localTracks = Array.from(room.localParticipant.tracks.values());
        localTracks.forEach((publication) => {
          const track = publication.track;
          if (track && localRef.current) {
            const el = track.attach();
            localRef.current.appendChild(el);
          }
        });

        // handle remote participants
        function attachParticipant(participant) {
          const container = document.createElement("div");
          container.id = participant.sid;
          remoteRef.current.appendChild(container);

          participant.tracks.forEach((pub) => {
            if (pub.isSubscribed) {
              const el = pub.track.attach();
              container.appendChild(el);
            }
          });

          participant.on("trackSubscribed", (track) => {
            const el = track.attach();
            container.appendChild(el);
          });
        }

        room.participants.forEach(attachParticipant);
        room.on("participantConnected", attachParticipant);

        room.on("participantDisconnected", (p) => {
          const el = document.getElementById(p.sid);
          if (el && el.parentNode) el.remove();
        });

        room.on("disconnected", () => {
          setStatus("disconnected");
        });
      } catch (err) {
        console.error("Twilio init error:", err);
        setStatus("error");
      }
    }

    init();
    return () => {
      mounted = false;
      const r = roomRef.current;
      if (r) {
        r.disconnect();
      }
      if (screenTrackRef.current) {
        try {
          screenTrackRef.current.stop();
        } catch {}
        screenTrackRef.current = null;
      }
    };
  }, []);

  const startScreenShare = async () => {
    if (audioOnly) return;
    if (!roomRef.current) return;
    try {
      const stream = await navigator.mediaDevices.getDisplayMedia({
        video: true,
        audio: false,
      });
      const TwilioVideo = await import("twilio-video");
      const [videoTrack] = stream.getVideoTracks();
      if (!videoTrack) return;

      const screenTrack = new TwilioVideo.LocalVideoTrack(videoTrack, {
        name: "screen",
      });
      screenTrackRef.current = screenTrack;
      roomRef.current.localParticipant.publishTrack(screenTrack);
      setIsSharing(true);

      if (screenRef.current) {
        screenRef.current.innerHTML = "";
        const el = screenTrack.attach();
        screenRef.current.appendChild(el);
      }

      videoTrack.onended = () => {
        stopScreenShare();
      };
    } catch (err) {
      console.error("Screen share error:", err);
    }
  };

  const stopScreenShare = () => {
    const room = roomRef.current;
    const screenTrack = screenTrackRef.current;
    if (room && screenTrack) {
      try {
        room.localParticipant.unpublishTrack(screenTrack);
      } catch {}
      try {
        screenTrack.stop();
      } catch {}
    }
    screenTrackRef.current = null;
    setIsSharing(false);
    if (screenRef.current) screenRef.current.innerHTML = "";
  };

  return (
    <div>
      <div className="mb-2">Status: {status}</div>
      {!audioOnly && allowScreenShare && (
        <div className="mb-3">
          {!isSharing ? (
            <button
              type="button"
              onClick={startScreenShare}
              className="px-3 py-2 rounded bg-emerald-600 text-white"
            >
              Start Screen Share
            </button>
          ) : (
            <button
              type="button"
              onClick={stopScreenShare}
              className="px-3 py-2 rounded bg-red-600 text-white"
            >
              Stop Screen Share
            </button>
          )}
        </div>
      )}
      <div className="grid md:grid-cols-2 gap-4">
        <div>
          <div className="font-medium mb-1">Your Camera</div>
          <div ref={localRef} className="bg-black/60 p-2 rounded min-h-[160px]" />
        </div>
        <div>
          <div className="font-medium mb-1">Remote Participants</div>
          <div ref={remoteRef} className="bg-black/60 p-2 rounded min-h-[160px]" />
        </div>
      </div>
      {!audioOnly && allowScreenShare && (
        <div className="mt-4">
          <div className="font-medium mb-1">Screen Share</div>
          <div ref={screenRef} className="bg-black/60 p-2 rounded min-h-[160px]" />
        </div>
      )}
    </div>
  );
}
