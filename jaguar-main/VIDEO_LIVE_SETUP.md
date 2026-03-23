# Video Live Setup

This project now supports these live session modes from `/admin/mentorship`:

- `twilio_video`
- `twilio_screen`
- `twilio_audio`
- `youtube`
- `videosdk`
- `embed`

## Which One To Choose

`Twilio`
- Interactive rooms.
- Best for participant control, mute states, and host moderation.

`YouTube`
- Simple public livestream embed.

`VideoSDK`
- Paste a VideoSDK embed/player URL into the media URL field.

`Embed`
- Paste any trusted iframe/player URL from another platform.

## Admin Steps

1. Open `/admin/mentorship`.
2. Choose the `Media Type`.
3. If using Twilio, enter the room name.
4. If using YouTube, VideoSDK, or Embed, paste the player URL into `Media URL`.
5. Save the live session.

The homepage and live session panel will automatically render the right player.

## Example URLs

YouTube:

```text
https://www.youtube.com/watch?v=YOUR_VIDEO_ID
```

VideoSDK:

```text
https://app.videosdk.live/meeting/...
```

Custom embed:

```text
https://player.example.com/embed/...
```

## Twilio Errors

If the preview still shows a Twilio status error, the player now shows the backend error detail too. Check:

- Vercel Twilio env vars
- `/api/twilio/token`
- camera and microphone permissions in the browser

Only use trusted embed URLs in admin.
