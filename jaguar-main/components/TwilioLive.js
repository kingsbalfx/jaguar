import { useEffect, useRef, useState } from "react";
import Video from "twilio-video";

export default function TwilioLive({ roomName, identity }) {
  const ref = useRef(null);
  const [status, setStatus] = useState("disconnected");
  useEffect(() => {
    let roomObj;
    async function init() {
      setStatus("connecting");
      const resp = await fetch("/api/twilio/token", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ identity, room: roomName }),
      });
      const data = await resp.json();
      if (!data.token) {
        setStatus("error");
        return;
      }
      try {
        roomObj = await Video.connect(data.token, { name: roomName });
        setStatus("connected");
        const container = ref.current;
        // attach existing participants
        roomObj.participants.forEach((participant) => {
          participant.tracks.forEach((publication) => {
            if (publication.track)
              container.appendChild(publication.track.attach());
          });
          participant.on("trackSubscribed", (track) =>
            container.appendChild(track.attach()),
          );
        });
        // attach local tracks
        const localTracks = await Video.createLocalTracks();
        localTracks.forEach((track) => container.appendChild(track.attach()));
        roomObj.on("participantConnected", (participant) => {
          participant.on("trackSubscribed", (track) =>
            container.appendChild(track.attach()),
          );
        });
      } catch (err) {
        console.error("Twilio connect error", err);
        setStatus("error");
      }
    }
    init();
    return () => {
      if (roomObj) roomObj.disconnect();
    };
  }, [roomName, identity]);
  return (
    <div className="card p-4">
      <div className="mb-2">Twilio Live — status: {status}</div>
      <div ref={ref} className="twilio-container grid grid-cols-1 gap-2"></div>
    </div>
  );
}
