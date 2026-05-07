-- ============================================================
-- Fix: ops dashboard sees zero rows on the new tables
--
-- Symptom: WearableSettingsPanel stays "Loading...", SOS panel says
-- "No SOS events yet" even when rows exist. Service-key reads work
-- fine, anon-key reads return 0 rows.
--
-- Root cause: when we created wearable_settings, sessions,
-- session_assets, and sos_events via the SQL editor (instead of the
-- Supabase Table Editor UI), the implicit GRANT to the anon and
-- authenticated roles was not auto-applied. Disabling RLS alone is
-- not enough — Postgres still needs explicit GRANTs for the anon
-- role to actually SELECT rows.
--
-- Run this once in the Supabase SQL editor.
-- ============================================================

-- Re-disable RLS in case the original disable was lost on rebuild
alter table public.wearable_settings disable row level security;
alter table public.sessions          disable row level security;
alter table public.session_assets    disable row level security;
alter table public.sos_events        disable row level security;

-- Explicit grants — anon (browser) AND authenticated need full CRUD for the demo
grant select, insert, update, delete on public.wearable_settings to anon, authenticated;
grant select, insert, update, delete on public.sessions          to anon, authenticated;
grant select, insert, update, delete on public.session_assets    to anon, authenticated;
grant select, insert, update, delete on public.sos_events        to anon, authenticated;

-- Make sure realtime publication includes them (idempotent — silently skips if already added)
do $$
begin alter publication supabase_realtime add table public.wearable_settings; exception when duplicate_object then end;
end $$;
do $$
begin alter publication supabase_realtime add table public.sessions; exception when duplicate_object then end;
end $$;
do $$
begin alter publication supabase_realtime add table public.session_assets; exception when duplicate_object then end;
end $$;
do $$
begin alter publication supabase_realtime add table public.sos_events; exception when duplicate_object then end;
end $$;

-- Verify — these should all return > 0 if there's data, no error
select 'wearable_settings' as tbl, count(*) from public.wearable_settings
union all
select 'sessions',                count(*) from public.sessions
union all
select 'session_assets',          count(*) from public.session_assets
union all
select 'sos_events',              count(*) from public.sos_events;
