"""Quick sanity check: connect to Supabase and read the components table."""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_KEY")

if not url or not key:
    print("Missing SUPABASE_URL or SUPABASE_SERVICE_KEY in .env")
    sys.exit(1)

sb = create_client(url, key)

count_resp = sb.table("components").select("*", count="exact").limit(0).execute()
print(f"Total rows in components: {count_resp.count}")

rows = sb.table("components").select("name, part_code, torque_spec").limit(3).execute()
print("\nFirst 3 rows:")
for r in rows.data:
    print(f"  - {r['part_code']:14s} | {r['name']:28s} | {r['torque_spec']}")

print("\nFuzzy lookup test: 'pump'")
hits = sb.table("components").select("name, part_code").ilike("name", "%pump%").execute()
for r in hits.data:
    print(f"  - {r['part_code']:14s} | {r['name']}")
