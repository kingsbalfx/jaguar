-- Add missing columns for live session media settings
-- Run in Supabase SQL editor

ALTER TABLE IF EXISTS live_sessions
  ADD COLUMN IF NOT EXISTS media_type text DEFAULT 'twilio_video',
  ADD COLUMN IF NOT EXISTS media_url text,
  ADD COLUMN IF NOT EXISTS room_name text DEFAULT 'global-room',
  ADD COLUMN IF NOT EXISTS segment text DEFAULT 'all',
  ADD COLUMN IF NOT EXISTS audio_only boolean DEFAULT false,
  ADD COLUMN IF NOT EXISTS updated_at timestamptz DEFAULT now();

-- Optional: backfill defaults for existing rows
UPDATE live_sessions
SET
  media_type = COALESCE(media_type, 'twilio_video'),
  room_name = COALESCE(room_name, 'global-room'),
  segment = COALESCE(segment, 'all'),
  audio_only = COALESCE(audio_only, false),
  updated_at = COALESCE(updated_at, now())
WHERE active = true;
