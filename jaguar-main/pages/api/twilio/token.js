// pages/api/twilio/token.js
import Twilio from "twilio";

export default async function handler(req, res) {
  if (req.method !== "POST") {
    return res.status(405).json({ error: "Method not allowed" });
  }

  const { TWILIO_ACCOUNT_SID, TWILIO_API_KEY_SID, TWILIO_API_KEY_SECRET } = process.env;

  if (!TWILIO_ACCOUNT_SID || !TWILIO_API_KEY_SID || !TWILIO_API_KEY_SECRET) {
    return res.status(500).json({ error: "Twilio env vars not configured" });
  }

  try {
    // generate a random identity (in production, use authenticated user id)
    const identity = `user-${Math.random().toString(36).substring(2, 9)}`;

    // create token
    const AccessToken = Twilio.jwt.AccessToken;
    const VideoGrant = AccessToken.VideoGrant;

    const token = new AccessToken(
      TWILIO_ACCOUNT_SID,
      TWILIO_API_KEY_SID,
      TWILIO_API_KEY_SECRET,
      { ttl: 3600 }
    );

    token.identity = identity;

    const requestedRoom = (req.body?.roomName || "").toString().trim();
    const roomName = requestedRoom || "global-room";
    const videoGrant = new VideoGrant({ room: roomName });
    token.addGrant(videoGrant);

    const jwt = token.toJwt();

    res.status(200).json({ token: jwt, roomName });
  } catch (err) {
    console.error("Twilio token error:", err);
    res.status(500).json({ error: "Could not create Twilio token" });
  }
}
