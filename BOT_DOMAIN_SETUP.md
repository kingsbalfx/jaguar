# Bot Domain Setup

Use this when your website is on Vercel and your MT5 bot is on Windows.

## What this fixes

If these URLs return 404:

- `https://bot.kingsbalfx.name.ng/health`
- `https://bot.kingsbalfx.name.ng/status`
- `https://bot.kingsbalfx.name.ng/restart`

then your public bot domain is not pointing to the Windows bot correctly yet.

## Files

- [Caddyfile](c:/Users/kingsbal/Documents/GitHub/jaguar/Caddyfile)

## What to do on the Windows machine

1. Install Caddy for Windows.
2. Copy the repo `Caddyfile` to your Caddy config location.
3. Make sure the Python bot is already running on:
   - `http://127.0.0.1:8000`
4. Start Caddy.

## DNS

Create an `A` record:

- Host: `bot`
- Value: your Windows VPS public IP

## Vercel env

```env
BOT_API_URL=https://bot.kingsbalfx.name.ng
BOT_API_INTERNAL=https://bot.kingsbalfx.name.ng
```

## Test

After DNS and Caddy are live, these must work publicly:

- `https://bot.kingsbalfx.name.ng/health`
- `https://bot.kingsbalfx.name.ng/status`

If they work, the admin monitor and restart button can work too.
