// pages/live-pen.js
import { useEffect, useRef } from "react";

export default function LivePen() {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas.getContext("2d");

    // Determine ws protocol
    const protocol = window.location.protocol === "https:" ? "wss" : "ws";
    const wsUrl = `${protocol}://${window.location.host}/ws/live-pen`;
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log("WebSocket connected to live pen");
    };

    ws.onmessage = (evt) => {
      try {
        const msg = JSON.parse(evt.data);
        if (msg.type === "pen") {
          drawPoint(ctx, msg.x, msg.y);
        }
        // if msg.type === "audio" → handle audio playback
      } catch (err) {
        console.error("WS message parse error:", err, evt.data);
      }
    };

    ws.onclose = () => {
      console.warn("WebSocket closed");
    };

    return () => {
      ws.close();
    };
  }, []);

  const drawPoint = (ctx, x, y) => {
    ctx.fillStyle = "lime";
    ctx.beginPath();
    ctx.arc(x, y, 2, 0, 2 * Math.PI);
    ctx.fill();
  };

  return (
    <div className="min-h-screen bg-black flex items-center justify-center">
      <canvas
        ref={canvasRef}
        width={800}
        height={600}
        className="border border-gray-700 bg-gray-900"
      />
    </div>
  );
}
