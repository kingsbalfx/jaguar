// server.js
import { createServer } from "http";
import next from "next";
import { parse } from "url";
import { WebSocketServer } from "ws";

const dev = process.env.NODE_ENV !== "production";
const app = next({ dev });
const handle = app.getRequestHandler();

app.prepare().then(() => {
  const server = createServer((req, res) => {
    const parsedUrl = parse(req.url, true);
    handle(req, res, parsedUrl);
  });

  // Create WebSocket server — noServer mode
  const wss = new WebSocketServer({ noServer: true });

  // On WS connection, you decide how to forward messages
  wss.on("connection", (ws, req) => {
    console.log("WebSocket client connected");

    ws.on("message", (msg) => {
      // Broadcast to all clients
      wss.clients.forEach((client) => {
        if (client.readyState === client.OPEN) {
          client.send(msg);
        }
      });
    });

    ws.on("close", () => {
      console.log("WebSocket client disconnected");
    });
  });

  server.on("upgrade", (req, socket, head) => {
    const { pathname } = parse(req.url || "");
    // route WebSocket path
    if (pathname === "/ws/live-pen") {
      wss.handleUpgrade(req, socket, head, (ws) => {
        wss.emit("connection", ws, req);
      });
    } else {
      socket.destroy();
    }
  });

  const PORT = process.env.PORT || 3000;
  server.listen(PORT, (err) => {
    if (err) throw err;
    console.log(`> Ready on http://localhost:${PORT}`);
    console.log(`> WebSocket listening at ws://localhost:${PORT}/ws/live-pen`);
  });
});
