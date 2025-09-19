// components/TwilioVideoClient.jsx
import React, { useEffect, useRef, useState } from "react";

/**
 * Minimal Twilio Video client component.
 * Requires an API endpoint at /api/twilio/token that returns { token, roomName }.
 *
 * Server: pages/api/twilio/token.js (provided below)
 */
export default function TwilioVideoClient() {
  const [status, setStatus] = useState("idle");
  const localRef = useRef(null);
  const remoteRef = useRef(null);
  const roomRef = useRef(null);

  useEffect(() => {
    let mounted = true;
    async function init() {
      setStatus("requesting-token");
      try {
        const res = await fetch("/api/twilio/token", { method: "POST" });
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
          video: { width: 640 },
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
    };
  }, []);

  return (
    <div>
      <div className="mb-2">Status: {status}</div>
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
    </div>
  );
}
