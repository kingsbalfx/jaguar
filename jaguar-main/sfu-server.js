import dotenv from "dotenv";
dotenv.config({ path: process.env.NODE_ENV === "production" ? ".env.production" : ".env.local" });

import http from "http";
import { WebSocketServer } from "ws";
import * as mediasoup from "mediasoup";

const PORT = Number(process.env.KINGSBAL_SFU_PORT || 4443);
const ANNOUNCED_IP = process.env.KINGSBAL_SFU_ANNOUNCED_IP || process.env.PUBLIC_IP || undefined;
const LISTEN_IP = process.env.KINGSBAL_SFU_LISTEN_IP || "0.0.0.0";
const RTC_MIN_PORT = Number(process.env.KINGSBAL_SFU_RTC_MIN_PORT || 40000);
const RTC_MAX_PORT = Number(process.env.KINGSBAL_SFU_RTC_MAX_PORT || 49999);
const MAX_WORKERS = Math.max(1, Number(process.env.KINGSBAL_SFU_WORKERS || 1));
const MAX_PEERS_PER_ROOM = Number(process.env.KINGSBAL_SFU_MAX_PEERS_PER_ROOM || 260);

const mediaCodecs = [
  {
    kind: "audio",
    mimeType: "audio/opus",
    clockRate: 48000,
    channels: 2,
  },
  {
    kind: "video",
    mimeType: "video/VP8",
    clockRate: 90000,
    parameters: { "x-google-start-bitrate": 900 },
  },
  {
    kind: "video",
    mimeType: "video/H264",
    clockRate: 90000,
    parameters: {
      "packetization-mode": 1,
      "profile-level-id": "42e01f",
      "level-asymmetry-allowed": 1,
    },
  },
];

const workers = [];
const rooms = new Map();
let workerCursor = 0;

function send(ws, message) {
  if (ws.readyState === ws.OPEN) ws.send(JSON.stringify(message));
}

function reply(ws, id, data) {
  send(ws, { id, ok: true, data });
}

function fail(ws, id, error) {
  send(ws, { id, ok: false, error: error?.message || String(error || "SFU request failed") });
}

function broadcast(room, message, exceptPeerId = "") {
  for (const peer of room.peers.values()) {
    if (peer.id !== exceptPeerId) send(peer.ws, message);
  }
}

function nextWorker() {
  const worker = workers[workerCursor % workers.length];
  workerCursor += 1;
  return worker;
}

async function getRoom(roomId) {
  if (rooms.has(roomId)) return rooms.get(roomId);
  const worker = nextWorker();
  const router = await worker.createRouter({ mediaCodecs });
  const room = {
    id: roomId,
    router,
    peers: new Map(),
    createdAt: Date.now(),
  };
  rooms.set(roomId, room);
  return room;
}

async function createWebRtcTransport(router) {
  const transport = await router.createWebRtcTransport({
    listenIps: [{ ip: LISTEN_IP, announcedIp: ANNOUNCED_IP }],
    enableUdp: true,
    enableTcp: true,
    preferUdp: true,
    initialAvailableOutgoingBitrate: 1_200_000,
    appData: { branded: "KINGSBALFX" },
  });
  await transport.setMaxIncomingBitrate(1_500_000).catch(() => {});
  return transport;
}

function publicProducer(producer, owner) {
  return {
    id: producer.id,
    peerId: owner.id,
    displayName: owner.displayName,
    kind: producer.kind,
    appData: producer.appData || {},
  };
}

function listRoomProducers(room, requesterId) {
  const producers = [];
  for (const peer of room.peers.values()) {
    if (peer.id === requesterId) continue;
    for (const producer of peer.producers.values()) {
      producers.push(publicProducer(producer, peer));
    }
  }
  return producers;
}

async function handlePeerMessage(peer, raw) {
  let message;
  try {
    message = JSON.parse(raw);
  } catch {
    return;
  }

  const { id, action, data = {} } = message;
  try {
    if (action === "join") {
      const roomId = String(data.roomId || "").trim();
      if (!roomId) throw new Error("roomId is required");
      const room = await getRoom(roomId);
      if (room.peers.size >= MAX_PEERS_PER_ROOM) throw new Error("This live room is full.");

      peer.room = room;
      peer.displayName = data.displayName || "Subscriber";
      peer.isHost = Boolean(data.isHost);
      room.peers.set(peer.id, peer);
      reply(peer.ws, id, {
        peerId: peer.id,
        routerRtpCapabilities: room.router.rtpCapabilities,
        producers: listRoomProducers(room, peer.id),
        peerCount: room.peers.size,
      });
      broadcast(room, {
        event: "peerJoined",
        data: { peerId: peer.id, displayName: peer.displayName, isHost: peer.isHost, peerCount: room.peers.size },
      }, peer.id);
      return;
    }

    if (!peer.room) throw new Error("Join a room first");
    const { room } = peer;

    if (action === "createWebRtcTransport") {
      const transport = await createWebRtcTransport(room.router);
      peer.transports.set(transport.id, transport);
      transport.on("dtlsstatechange", (state) => {
        if (state === "closed") transport.close();
      });
      transport.on("close", () => peer.transports.delete(transport.id));
      reply(peer.ws, id, {
        id: transport.id,
        iceParameters: transport.iceParameters,
        iceCandidates: transport.iceCandidates,
        dtlsParameters: transport.dtlsParameters,
      });
      return;
    }

    if (action === "connectTransport") {
      const transport = peer.transports.get(data.transportId);
      if (!transport) throw new Error("Transport not found");
      await transport.connect({ dtlsParameters: data.dtlsParameters });
      reply(peer.ws, id, { connected: true });
      return;
    }

    if (action === "produce") {
      if (!peer.isHost && !peer.approved.has(data.appData?.source || data.kind || "stage")) {
        throw new Error("Admin approval is required before publishing media.");
      }
      const transport = peer.transports.get(data.transportId);
      if (!transport) throw new Error("Send transport not found");
      const producer = await transport.produce({
        kind: data.kind,
        rtpParameters: data.rtpParameters,
        appData: {
          ...(data.appData || {}),
          displayName: peer.isHost ? "Admin" : peer.displayName,
          peerId: peer.id,
        },
      });
      peer.producers.set(producer.id, producer);
      producer.on("transportclose", () => peer.producers.delete(producer.id));
      producer.on("close", () => {
        peer.producers.delete(producer.id);
        broadcast(room, { event: "producerClosed", data: { producerId: producer.id } }, peer.id);
      });
      reply(peer.ws, id, { id: producer.id });
      broadcast(room, { event: "newProducer", data: publicProducer(producer, peer) }, peer.id);
      return;
    }

    if (action === "consume") {
      const producerId = data.producerId;
      if (!room.router.canConsume({ producerId, rtpCapabilities: data.rtpCapabilities })) {
        throw new Error("Cannot consume this media stream");
      }
      const transport = peer.transports.get(data.transportId);
      if (!transport) throw new Error("Receive transport not found");
      const owner = [...room.peers.values()].find((item) => item.producers.has(producerId));
      const producer = owner?.producers.get(producerId);
      if (!producer) throw new Error("Producer not found");
      const consumer = await transport.consume({
        producerId,
        rtpCapabilities: data.rtpCapabilities,
        paused: false,
      });
      peer.consumers.set(consumer.id, consumer);
      consumer.on("transportclose", () => peer.consumers.delete(consumer.id));
      consumer.on("producerclose", () => {
        peer.consumers.delete(consumer.id);
        send(peer.ws, { event: "producerClosed", data: { producerId } });
      });
      reply(peer.ws, id, {
        id: consumer.id,
        producerId,
        kind: consumer.kind,
        rtpParameters: consumer.rtpParameters,
        producerAppData: producer.appData || {},
      });
      return;
    }

    if (action === "closeProducer") {
      const producer = peer.producers.get(data.producerId);
      if (producer) producer.close();
      reply(peer.ws, id, { closed: true });
      return;
    }

    if (action === "requestStage") {
      broadcast(room, {
        event: "stageRequest",
        data: {
          peerId: peer.id,
          displayName: peer.displayName,
          kind: data.kind || "camera",
          at: Date.now(),
        },
      }, peer.id);
      reply(peer.ws, id, { requested: true });
      return;
    }

    if (action === "approveStage") {
      if (!peer.isHost) throw new Error("Only the host can approve stage requests.");
      const target = room.peers.get(data.targetPeerId);
      if (!target) throw new Error("Participant is no longer connected.");
      const kind = data.kind || "camera";
      target.approved.add(kind);
      send(target.ws, { event: "stageApproved", data: { kind } });
      reply(peer.ws, id, { approved: true });
      return;
    }

    if (action === "listProducers") {
      reply(peer.ws, id, { producers: listRoomProducers(room, peer.id), peerCount: room.peers.size });
      return;
    }

    throw new Error(`Unknown SFU action: ${action}`);
  } catch (error) {
    fail(peer.ws, id, error);
  }
}

function cleanupPeer(peer) {
  for (const consumer of peer.consumers.values()) consumer.close();
  for (const producer of peer.producers.values()) producer.close();
  for (const transport of peer.transports.values()) transport.close();
  if (peer.room) {
    const { room } = peer;
    room.peers.delete(peer.id);
    broadcast(room, { event: "peerLeft", data: { peerId: peer.id, peerCount: room.peers.size } });
    if (room.peers.size === 0) {
      room.router.close();
      rooms.delete(room.id);
    }
  }
}

async function start() {
  for (let index = 0; index < MAX_WORKERS; index += 1) {
    const worker = await mediasoup.createWorker({
      rtcMinPort: RTC_MIN_PORT,
      rtcMaxPort: RTC_MAX_PORT,
      logLevel: process.env.KINGSBAL_SFU_LOG_LEVEL || "warn",
    });
    worker.on("died", () => {
      console.error("mediasoup worker died; exiting so the process manager restarts it");
      process.exit(1);
    });
    workers.push(worker);
  }

  const server = http.createServer((req, res) => {
    const { pathname } = new URL(req.url || "/", "http://localhost");
    if (pathname === "/health") {
      res.setHeader("Content-Type", "application/json");
      res.end(JSON.stringify({ status: "ok", rooms: rooms.size, ts: Date.now() }));
      return;
    }
    res.statusCode = 404;
    res.end("not found");
  });

  const wss = new WebSocketServer({ noServer: true });
  wss.on("connection", (ws) => {
    const peer = {
      id: crypto.randomUUID(),
      ws,
      room: null,
      displayName: "Subscriber",
      isHost: false,
      approved: new Set(),
      transports: new Map(),
      producers: new Map(),
      consumers: new Map(),
    };
    ws.on("message", (raw) => void handlePeerMessage(peer, raw));
    ws.on("close", () => cleanupPeer(peer));
    ws.on("error", () => cleanupPeer(peer));
  });

  server.on("upgrade", (req, socket, head) => {
    const { pathname } = new URL(req.url || "/", "http://localhost");
    if (pathname !== "/sfu") {
      socket.destroy();
      return;
    }
    wss.handleUpgrade(req, socket, head, (ws) => wss.emit("connection", ws, req));
  });

  server.listen(PORT, () => {
    console.log(`KINGSBALFX SFU listening on :${PORT}/sfu`);
    console.log(`RTC ports ${RTC_MIN_PORT}-${RTC_MAX_PORT}; announced IP: ${ANNOUNCED_IP || "auto/local"}`);
  });
}

start().catch((error) => {
  console.error(error);
  process.exit(1);
});
