# KINGSBALFX Self-Hosted SFU Live Room

This setup keeps the live classroom fully embedded in the KINGSBALFX app. It does not use YouTube, Agora, or an external embedded player.

## What This Adds

- Admin publishes camera/screen once to your own SFU server.
- The SFU distributes that stream to 100-200+ connected viewers.
- Users stay inside the KINGSBALFX dashboard.
- Users can request camera/microphone or screen sharing.
- Admin approves requests before users can publish.
- Chat remains handled by the existing in-app mentorship chat.

## Required Infrastructure

Vercel can host the Next.js app, but it cannot reliably host the long-running WebRTC media server. Run the SFU on a VPS.

Minimum VPS for 200 viewers:

- 4 vCPU
- 8 GB RAM
- 1 Gbps network recommended
- Ubuntu 22.04 or newer

Open firewall ports:

- TCP `4443` for SFU WebSocket signaling
- UDP `40000-49999` for WebRTC media
- TCP `40000-49999` optional fallback

## SQL

Run this migration in Supabase SQL editor:

```sql
-- file: sql/2026-06-21_kingsbal_sfu_live_mode.sql
```

It ensures `live_sessions.media_type` supports:

- `kingsbal_sfu`
- `webrtc`

It also converts old external live modes like `youtube`, `iframe`, and `broadcast` to `kingsbal_sfu`.

## App Environment Variables

In Vercel, add:

```env
NEXT_PUBLIC_KINGSBAL_SFU_URL=wss://YOUR_SFU_DOMAIN/sfu
```

For local testing:

```env
NEXT_PUBLIC_KINGSBAL_SFU_URL=ws://localhost:4443/sfu
```

## SFU Server Environment Variables

On the VPS, create `.env.production` in the deployed `jaguar-main` folder:

```env
NODE_ENV=production
KINGSBAL_SFU_PORT=4443
KINGSBAL_SFU_LISTEN_IP=0.0.0.0
KINGSBAL_SFU_ANNOUNCED_IP=YOUR_PUBLIC_VPS_IP
KINGSBAL_SFU_RTC_MIN_PORT=40000
KINGSBAL_SFU_RTC_MAX_PORT=49999
KINGSBAL_SFU_MAX_PEERS_PER_ROOM=260
KINGSBAL_SFU_WORKERS=2
```

If the SFU is behind a reverse proxy with TLS, keep `KINGSBAL_SFU_PORT=4443` internally and proxy `wss://YOUR_SFU_DOMAIN/sfu` to it.

## Run Locally

```bash
npm install
npm run sfu
```

In another terminal:

```bash
npm run dev
```

Open the admin mentorship dashboard, set `Delivery mode` to `KINGSBALFX SFU room`, save the room, and open the live room.

## Run On VPS With PM2

```bash
npm install
npm install -g pm2
pm2 start sfu-server.js --name kingsbalfx-sfu
pm2 save
pm2 startup
```

Health check:

```bash
curl http://localhost:4443/health
```

## Nginx Reverse Proxy Example

```nginx
server {
  server_name sfu.yourdomain.com;

  location /sfu {
    proxy_pass http://127.0.0.1:4443/sfu;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_read_timeout 86400;
  }

  location /health {
    proxy_pass http://127.0.0.1:4443/health;
  }
}
```

Use Certbot or your host provider to enable HTTPS so browsers can connect with `wss://`.

## Admin Flow

1. Go to Admin Dashboard → Mentorship.
2. Select the allowed classes.
3. Set delivery mode to `KINGSBALFX SFU room`.
4. Save the room.
5. Open live room.
6. Click `Share screen` or `Camera`.
7. Users join from their dashboard and receive the stream.
8. If a user requests to speak or share screen, approve from the permission panel.

## Capacity Notes

The SFU removes the browser mesh bottleneck. Actual maximum capacity still depends on VPS CPU and outbound bandwidth.

For 200 viewers, keep the admin stream around:

- 720p
- 15-24 FPS
- 1.0-1.5 Mbps video bitrate

If you want 500+ viewers later, run multiple SFU instances behind a proper load balancer and split rooms across instances.
