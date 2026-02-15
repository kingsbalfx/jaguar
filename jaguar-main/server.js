// server.js
import dotenv from "dotenv";
// Load environment file based on NODE_ENV
const envFile = process.env.NODE_ENV === "production" ? ".env.production" : ".env.local";
dotenv.config({ path: envFile });

import { createServer } from "http";
import next from "next";
import { parse } from "url";
import { WebSocketServer } from "ws";
import crypto from "crypto";
// Import Supabase AFTER dotenv config loads
import { getSupabaseClient } from "./lib/supabaseClient.js";
import { verifySignature, handlePaystackEvent } from "./lib/paystack.js";

const dev = process.env.NODE_ENV !== "production";
const app = next({ dev });
const handle = app.getRequestHandler();

app.prepare().then(() => {
  const server = createServer(async (req, res) => {
    const parsedUrl = parse(req.url, true);

    // Health endpoint for orchestration / load balancers
    if (req.method === "GET" && parsedUrl.pathname === "/health") {
      res.statusCode = 200;
      res.setHeader("Content-Type", "application/json");
      res.end(JSON.stringify({ status: "ok", ts: Date.now() }));
      return;
    }

    // NOTE: Trade webhook removed per configuration — bot should write directly to Supabase.
    // The /api/trades incoming webhook handler was intentionally removed to rely on
    // Supabase as the single source of truth for signals and logs. Retain Paystack
    // webhook handling below for payment processing.

    // Paystack webhook receiver: verifies signature and saves event to Supabase
    if (req.method === "POST" && parsedUrl.pathname === "/api/paystack-webhook") {
      let body = "";
      req.on("data", (chunk) => (body += chunk));
      req.on("end", async () => {
        const sig = req.headers["x-paystack-signature"] || req.headers["x-paystack-signature".toLowerCase()];
        const secret = process.env.PAYSTACK_WEBHOOK_SECRET || process.env.PAYSTACK_SECRET;
        if (secret) {
          if (!verifySignature(body, sig, secret)) {
            res.statusCode = 401;
            res.end("Invalid signature");
            return;
          }
        }

        try {
          const eventJson = JSON.parse(body);
          await handlePaystackEvent(body, eventJson);
          res.statusCode = 200;
          res.end("ok");
        } catch (e) {
          res.statusCode = 400;
          res.end("invalid json");
        }
      });
      return;
    }

    // Admin route to fetch recent payments (requires ADMIN_API_KEY header)
    if (req.method === "GET" && parsedUrl.pathname === "/api/admin/payments") {
      const adminSecret = req.headers["x-admin-secret"] || req.headers["x-admin-secret".toLowerCase()];
      if (!adminSecret || adminSecret !== process.env.ADMIN_API_KEY) {
        res.statusCode = 401;
        res.end("unauthorized");
        return;
      }

      try {
        const supabase = getSupabaseClient({ server: true });
        const { data, error } = await supabase.from("payments").select("*").order("received_at", { ascending: false }).limit(200);
        if (error) {
          res.statusCode = 500;
          res.end("error fetching payments");
          return;
        }
        res.setHeader("Content-Type", "application/json");
        res.statusCode = 200;
        res.end(JSON.stringify({ payments: data }));
      } catch (e) {
        res.statusCode = 500;
        res.end("server error");
      }
      return;
    }

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
    const base =
      process.env.NEXT_PUBLIC_SITE_URL ||
      (process.env.NEXT_PUBLIC_VERCEL_URL ? `https://${process.env.NEXT_PUBLIC_VERCEL_URL}` : "https://kingsbalfx.name.ng");
    console.log(`> Ready on ${base}`);
    console.log(`> WebSocket listening at ${base.replace(/^http/, "ws")}/ws/live-pen`);
  });
});
