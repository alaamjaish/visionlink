-- ============================================================
-- VisionLink — schema for the 6-button system + SOS panic mode
-- Apply via Supabase SQL editor (one-shot — uses IF NOT EXISTS).
-- ============================================================

-- ------------------------------------------------------------
-- 1. wearable_settings  (singleton — what the buttons should do)
--    The ops dashboard "Wearable Settings" panel edits this row.
--    The voice command center reads it on every button press.
-- ------------------------------------------------------------
create table if not exists wearable_settings (
  id text primary key default 'current',
  -- Per-button provider choice ('gemini' | 'openai')
  -- Defaults to Gemini — cheaper, well-tested. Flip to 'openai' from the
  -- ops dashboard's Wearable Settings panel for gpt-realtime-2 demos.
  b4_provider     text not null default 'gemini',
  b5_provider     text not null default 'gemini',
  -- B5 (vision): how the agent sees
  --   'snap_on_press'  — single image per button press during session
  --   'gemini_video'   — continuous 1 fps video stream (Gemini-only)
  --   'auto_snap_4s'   — auto-capture every 4 seconds (any provider)
  b5_vision_mode  text not null default 'snap_on_press',
  -- B6 SOS panic mode tunables
  -- 10 s default = ~60 frames over the 10-min cap, ~$0.30 worst case
  sos_photo_interval_s int not null default 10,
  sos_max_duration_s   int not null default 600,   -- 10 minutes hard cap
  sos_alert_recipient_role text not null default 'safety officer',
  -- Brain that runs the SOS conversation. Defaults to Gemini (cheap,
  -- fast, matches the rest of the wearable). Flip to 'openai' for
  -- gpt-realtime-2 calm-emergency demo runs.
  sos_provider text not null default 'gemini',
  -- Worker identity (defaults from .env, override here for demo)
  worker_id   text not null default 'demo_worker_001',
  worker_name text not null default 'Alaa',
  updated_at  timestamptz not null default now()
);

-- Seed the singleton row (idempotent — only inserts if missing)
insert into wearable_settings (id) values ('current')
on conflict (id) do nothing;


-- ------------------------------------------------------------
-- 2. sessions  (B1: documentation sessions)
-- ------------------------------------------------------------
create table if not exists sessions (
  id          uuid primary key default gen_random_uuid(),
  worker_id   text not null,
  worker_name text,
  label       text,
  started_at  timestamptz not null default now(),
  ended_at    timestamptz,
  status      text not null default 'open'   -- 'open' | 'closed'
);
create index if not exists sessions_worker_idx on sessions (worker_id, started_at desc);
create index if not exists sessions_status_idx on sessions (status);


-- ------------------------------------------------------------
-- 3. session_assets  (B2 photos/videos, B3 voice notes)
-- ------------------------------------------------------------
create table if not exists session_assets (
  id            uuid primary key default gen_random_uuid(),
  session_id    uuid references sessions(id) on delete cascade,
  worker_id     text not null,
  kind          text not null,    -- 'photo' | 'video' | 'voice_note'
  storage_path  text not null,    -- supabase storage path (bucket 'session-assets')
  captured_at   timestamptz not null default now(),
  duration_s    numeric,
  notes         text
);
create index if not exists session_assets_session_idx on session_assets (session_id, captured_at desc);
create index if not exists session_assets_kind_idx on session_assets (kind);


-- ------------------------------------------------------------
-- 4. sos_events  (B6 panic mode log + remote shutoff signal)
--    Each row = one SOS session. The ops dashboard sets
--    `resolved=true` to remotely tell the wearable to stop.
-- ------------------------------------------------------------
create table if not exists sos_events (
  id              uuid primary key default gen_random_uuid(),
  worker_id       text not null,
  worker_name     text,
  triggered_at    timestamptz not null default now(),
  resolved_at     timestamptz,
  resolved_by     text,                          -- supervisor name or 'auto_timeout'
  resolved        boolean not null default false,-- ops dashboard flips to true to shut off
  reason          text,                          -- supervisor's note when resolving
  live_transcript text default '',               -- streaming text from the agent's STT
  frames_sent     int not null default 0,
  email_sent      boolean not null default false,
  notes           text
);
create index if not exists sos_events_open_idx on sos_events (resolved, triggered_at desc);
create index if not exists sos_events_worker_idx on sos_events (worker_id, triggered_at desc);


-- ------------------------------------------------------------
-- 5. Add all new tables to the realtime publication so the ops
--    dashboard can stream INSERT/UPDATE/DELETE to the browser.
-- ------------------------------------------------------------
do $$
begin
  -- wearable_settings: ops UI uses realtime to reflect saves instantly
  begin alter publication supabase_realtime add table wearable_settings; exception when duplicate_object then end;
  begin alter publication supabase_realtime add table sessions;          exception when duplicate_object then end;
  begin alter publication supabase_realtime add table session_assets;    exception when duplicate_object then end;
  begin alter publication supabase_realtime add table sos_events;        exception when duplicate_object then end;
end $$;


-- ------------------------------------------------------------
-- 6. RLS — disabled for demo (matches the rest of the project).
--    Production deployment should re-enable with proper policies.
-- ------------------------------------------------------------
alter table wearable_settings disable row level security;
alter table sessions          disable row level security;
alter table session_assets    disable row level security;
alter table sos_events        disable row level security;


-- ------------------------------------------------------------
-- 7. Storage bucket for session assets (photos, videos, voice notes,
--    SOS frames). Apply this in the Supabase dashboard if not via SQL:
--      Bucket name: session-assets
--      Public:      false  (use signed URLs from the ops dashboard)
-- ------------------------------------------------------------
-- The Supabase JS client will resolve storage paths under this bucket.
-- We don't auto-create it via SQL because storage.buckets DDL is
-- behind storage.create_bucket() which needs service-role context.
-- See scripts/seed_storage_bucket.py for the Python equivalent.
