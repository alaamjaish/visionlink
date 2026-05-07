-- ============================================================
-- Migration: enable live SOS frame display in the ops dashboard
--
-- Adds last_frame_path to sos_events so the SOS panel can show the
-- most recent camera frame as a big live image while panic mode is
-- active. The wearable updates this column on every snap upload.
--
-- Run this once in the Supabase SQL editor.
-- ============================================================

alter table public.sos_events
  add column if not exists last_frame_path text;

-- Make sure the storage bucket is public so the browser can fetch
-- frames without signed URLs (already done from Python, but harmless
-- to re-assert here).
update storage.buckets
   set public = true
 where name = 'session-assets';

-- Verify
select id, frames_sent, last_frame_path
  from public.sos_events
 order by triggered_at desc
 limit 5;
