-- ============================================================
-- Migration: add sos_provider column to wearable_settings
-- Run once in the Supabase SQL editor.
-- ============================================================

alter table wearable_settings
  add column if not exists sos_provider text not null default 'gemini';

-- Backfill the singleton row in case it's nulled
update wearable_settings
   set sos_provider = coalesce(sos_provider, 'gemini')
 where id = 'current';

-- (No realtime publication change needed — wearable_settings is already in it.)
