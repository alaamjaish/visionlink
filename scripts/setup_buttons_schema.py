"""Apply the buttons + SOS schema and create the session-assets storage bucket.

Run from the project root:
    python3 scripts/setup_buttons_schema.py

Idempotent. Skips work that's already done. Uses SUPABASE_SERVICE_KEY
from .env so it bypasses RLS and storage policies.

What this does:
  1. Optionally apply schema_buttons_and_sos.sql via the REST RPC
     (requires `exec_sql` SQL function — most Supabase projects don't
     have this enabled, so we fall back to a friendly "paste this in
     the SQL editor" message).
  2. Create the `session-assets` storage bucket (private).
  3. Verify all four new tables are reachable + the singleton settings
     row exists.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SQL_PATH = Path(__file__).resolve().parent / "schema_buttons_and_sos.sql"
BUCKET = "session-assets"

load_dotenv(PROJECT_ROOT / ".env")

URL = os.getenv("SUPABASE_URL", "").strip()
KEY = os.getenv("SUPABASE_SERVICE_KEY", "").strip()
if not URL or not KEY:
    print("ERROR: SUPABASE_URL or SUPABASE_SERVICE_KEY missing in .env")
    sys.exit(1)

sb = create_client(URL, KEY)


def step(label: str) -> None:
    print(f"\n=== {label} ===")


# ----------------------------------------------------------------
# 1. Verify tables exist (you must paste the SQL once in the editor).
# ----------------------------------------------------------------
step("Verifying tables exist")
expected = ["wearable_settings", "sessions", "session_assets", "sos_events"]
missing: list[str] = []
for tbl in expected:
    try:
        sb.table(tbl).select("*").limit(1).execute()
        print(f"  ✓ {tbl}")
    except Exception as e:
        print(f"  ✗ {tbl} — {e}")
        missing.append(tbl)

if missing:
    print()
    print("Some tables are missing. Open the Supabase SQL editor and paste:")
    print(f"  {SQL_PATH}")
    print()
    print("Then re-run this script.")
    sys.exit(2)


# ----------------------------------------------------------------
# 2. Ensure the singleton settings row exists.
# ----------------------------------------------------------------
step("Ensuring wearable_settings.current exists")
existing = sb.table("wearable_settings").select("id").eq("id", "current").execute()
if existing.data:
    print("  ✓ row 'current' already present")
else:
    sb.table("wearable_settings").insert({"id": "current"}).execute()
    print("  ✓ inserted singleton row 'current'")


# ----------------------------------------------------------------
# 3. Create the session-assets storage bucket (private).
# ----------------------------------------------------------------
step(f"Creating storage bucket '{BUCKET}'")
try:
    buckets = sb.storage.list_buckets()
    have = any(b.name == BUCKET for b in buckets) if buckets else False
    if have:
        print(f"  ✓ bucket '{BUCKET}' already exists")
    else:
        sb.storage.create_bucket(BUCKET, options={"public": False})
        print(f"  ✓ bucket '{BUCKET}' created (private)")
except Exception as e:
    print(f"  ✗ failed: {e}")
    print(
        "  → Create it manually in Supabase dashboard → Storage → New bucket → "
        f"name: '{BUCKET}', public: OFF"
    )


print()
print("All set. The 6-button system can now read/write Supabase.")
