"""Seed managers + report_templates directly from Python (bypass SQL editor).

Idempotent: re-running this just upserts. Edits made in the dashboard for
non-seed rows are preserved.

Usage:
    cd ~/Desktop/visionlink
    python3 scripts/seed_email_data.py
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from supabase import create_client

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_KEY")
if not url or not key:
    print("missing SUPABASE_URL or SUPABASE_SERVICE_KEY in .env")
    sys.exit(1)

sb = create_client(url, key)


# ---------- Managers ----------

MANAGERS = [
    {"name": "Sarah Chen",     "email": "sarah.chen@acmefactory.example.com",
     "role": "CEO",                       "notes": "Top-line summaries only."},
    {"name": "Marcus Henke",   "email": "marcus.henke@acmefactory.example.com",
     "role": "Operations Director",       "notes": "COO. Wants daily ops with all incidents."},
    {"name": "Priya Acharya",  "email": "priya.acharya@acmefactory.example.com",
     "role": "Plant Supervisor",          "notes": "First escalation for incidents."},
    {"name": "Tom Reyes",      "email": "tom.reyes@acmefactory.example.com",
     "role": "Maintenance Supervisor",    "notes": "Owns maintenance + parts scheduling."},
    {"name": "Linda Park",     "email": "linda.park@acmefactory.example.com",
     "role": "Safety Officer",            "notes": "EHS — every safety incident immediately."},
    {"name": "James Vasquez",  "email": "james.vasquez@acmefactory.example.com",
     "role": "Quality Assurance Manager", "notes": "Audit + quality reports."},
    {"name": "Emily Tanaka",   "email": "emily.tanaka@acmefactory.example.com",
     "role": "Procurement Manager",       "notes": "Parts + supplier coordination."},
    {"name": "Daniel Lin",     "email": "daniel.lin@acmefactory.example.com",
     "role": "Accountant",                "notes": "Finance & cost reconciliation."},
]


# ---------- Report Templates ----------

TEMPLATES = [
    {
        "name": "Daily Operations Report",
        "category": "ops_report",
        "subject": "Daily Operations Report — {{date}}",
        "description": "Comprehensive shift summary for COO / Plant Supervisor.",
        "body_html": """<div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:640px;color:#1f2a3a;line-height:1.6;">
<p>Hello <b>{{recipient_name}}</b>,</p>
<p>This is the daily operations summary from <b>{{worker_name}}</b>, generated at {{datetime}}.</p>

<h2 style="color:#0f1724;border-bottom:2px solid #4ea8ff;padding-bottom:6px;margin-top:24px;">Executive Summary</h2>
<p>Production continues on schedule. The items below need attention before end of shift.</p>

<h3 style="color:#d94852;margin-top:20px;">Open Incidents</h3>
{{recent_incidents}}

<h3 style="color:#c98a17;margin-top:20px;">Pending Tasks</h3>
{{recent_tasks}}

<h3 style="color:#28a374;margin-top:20px;">Outstanding Parts Requests</h3>
{{recent_parts}}

<h3 style="margin-top:20px;">Worker note</h3>
<blockquote style="border-left:3px solid #4ea8ff;padding:8px 16px;color:#333;background:#f5faff;margin:0;">{{custom_message}}</blockquote>

<hr style="border:none;border-top:1px solid #ddd;margin-top:32px;">
<p style="color:#888;font-size:12px;">Sent automatically by VisionLink, the wearable factory assistant for {{worker_name}}. Generated {{datetime}}.</p>
</div>""",
    },
    {
        "name": "Executive Briefing",
        "category": "ops_report",
        "subject": "Executive Briefing — {{date}}",
        "description": "Top-line briefing for CEO and senior leadership.",
        "body_html": """<div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:640px;color:#1f2a3a;line-height:1.6;">
<p>Dear {{recipient_name}},</p>
<p>Brief operations update from the floor team, prepared by <b>{{worker_name}}</b>.</p>

<div style="background:#f5faff;border-left:4px solid #4ea8ff;padding:12px 16px;margin:18px 0;">
  <b style="color:#0f1724;">At a glance:</b> active incidents and outstanding requests are listed below for your awareness. No action required unless you wish to escalate.
</div>

<h3 style="color:#0f1724;margin-top:20px;">Incidents under management</h3>
{{recent_incidents}}

<h3 style="color:#0f1724;margin-top:20px;">Operational backlog</h3>
{{recent_tasks}}

<p style="margin-top:24px;"><b>Note from the floor:</b><br>{{custom_message}}</p>

<hr style="border:none;border-top:1px solid #ddd;margin-top:32px;">
<p style="color:#888;font-size:12px;">VisionLink Operations · {{datetime}}</p>
</div>""",
    },
    {
        "name": "Incident Report",
        "category": "incident",
        "subject": "Incident Report from {{worker_name}} — {{date}}",
        "description": "Safety / supervisor escalation. Tone is more urgent.",
        "body_html": """<div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:640px;color:#1f2a3a;line-height:1.6;">
<p>Hi <b>{{recipient_name}}</b>,</p>
<p>Reporting the following incidents from the production floor. <b>{{worker_name}}</b> is the source. Reviewer action requested.</p>

<div style="background:#fdf2f2;border-left:4px solid #d94852;padding:12px 16px;margin:18px 0;color:#5a1a20;">
  <b>Recipient:</b> {{recipient_name}} · {{recipient_role}}<br>
  <b>Reported by:</b> {{worker_name}}<br>
  <b>Reported at:</b> {{datetime}}
</div>

<h3 style="color:#d94852;margin-top:20px;">Active Incidents</h3>
{{recent_incidents}}

<h3 style="margin-top:20px;">Worker context</h3>
<blockquote style="border-left:3px solid #d94852;padding:8px 16px;color:#333;background:#fdf2f2;margin:0;">{{custom_message}}</blockquote>

<p style="margin-top:24px;color:#5a1a20;"><b>Recommended next step:</b> review each open incident, acknowledge in the ops dashboard, and assign resolution owner if needed.</p>

<hr style="border:none;border-top:1px solid #ddd;margin-top:32px;">
<p style="color:#888;font-size:12px;">VisionLink incident escalation · {{datetime}}</p>
</div>""",
    },
    {
        "name": "Maintenance Backlog Report",
        "category": "task",
        "subject": "Maintenance Backlog — {{date}}",
        "description": "Pending tasks + parts. Goes to maintenance supervisor.",
        "body_html": """<div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:640px;color:#1f2a3a;line-height:1.6;">
<p>Hi <b>{{recipient_name}}</b>,</p>
<p>Pending maintenance status from <b>{{worker_name}}</b>, captured live from the floor.</p>

<h3 style="color:#c98a17;margin-top:20px;">Pending Tasks</h3>
{{recent_tasks}}

<h3 style="color:#28a374;margin-top:20px;">Awaiting Parts</h3>
{{recent_parts}}

<p style="margin-top:24px;"><b>Worker note:</b><br>{{custom_message}}</p>

<p style="margin-top:18px;color:#444;">Please reassign or reprioritise as needed in the dashboard. The wearable will reflect changes within the same shift.</p>

<hr style="border:none;border-top:1px solid #ddd;margin-top:32px;">
<p style="color:#888;font-size:12px;">VisionLink maintenance scheduler · {{datetime}}</p>
</div>""",
    },
    {
        "name": "Parts Procurement Summary",
        "category": "task",
        "subject": "Parts Procurement Summary — {{date}}",
        "description": "Goes to Procurement Manager.",
        "body_html": """<div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:640px;color:#1f2a3a;line-height:1.6;">
<p>Hi <b>{{recipient_name}}</b>,</p>
<p>Outstanding parts requests submitted by <b>{{worker_name}}</b> on the production floor.</p>

<h3 style="color:#28a374;margin-top:20px;">Open Requests</h3>
{{recent_parts}}

<p style="margin-top:18px;"><b>Worker context:</b><br>{{custom_message}}</p>

<p style="margin-top:18px;color:#444;">Please review urgency tiers and approve or escalate. Critical items are highlighted in the dashboard.</p>

<hr style="border:none;border-top:1px solid #ddd;margin-top:32px;">
<p style="color:#888;font-size:12px;">VisionLink procurement summary · {{datetime}}</p>
</div>""",
    },
    {
        "name": "Quick Note",
        "category": "ad_hoc",
        "subject": "Quick note from {{worker_name}}",
        "description": "Ad-hoc voice note. Pure custom_message — no live injection.",
        "body_html": """<div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:640px;color:#1f2a3a;line-height:1.6;">
<p>Hi <b>{{recipient_name}}</b>,</p>
<p><b>{{worker_name}}</b> sent the following note from the factory floor at {{datetime}}:</p>

<blockquote style="border-left:3px solid #4ea8ff;padding:12px 18px;color:#222;background:#f5faff;margin:18px 0;font-size:15px;">{{custom_message}}</blockquote>

<p style="color:#444;">No live operations data is included in this note — it is verbatim from the worker.</p>

<hr style="border:none;border-top:1px solid #ddd;margin-top:32px;">
<p style="color:#888;font-size:12px;">VisionLink ad-hoc note · {{datetime}}</p>
</div>""",
    },
]


def upsert_managers():
    print(f"\n[managers] upserting {len(MANAGERS)} rows...")
    for m in MANAGERS:
        existing = sb.table("managers").select("id").eq("email", m["email"]).execute()
        if existing.data:
            sb.table("managers").update(m).eq("email", m["email"]).execute()
            print(f"  ↻ {m['role']:30s} {m['name']:18s} ({m['email']})")
        else:
            sb.table("managers").insert(m).execute()
            print(f"  + {m['role']:30s} {m['name']:18s} ({m['email']})")
    # clean placeholders
    sb.table("managers").delete().in_("email", [
        "demo-ceo@example.com",
        "demo-accountant@example.com",
        "demo-supervisor@example.com",
        "demo-qa@example.com",
    ]).execute()


def upsert_templates():
    print(f"\n[report_templates] upserting {len(TEMPLATES)} rows...")
    for t in TEMPLATES:
        existing = sb.table("report_templates").select("id").eq("name", t["name"]).execute()
        if existing.data:
            sb.table("report_templates").update(t).eq("name", t["name"]).execute()
            print(f"  ↻ {t['category']:12s} {t['name']}")
        else:
            sb.table("report_templates").insert(t).execute()
            print(f"  + {t['category']:12s} {t['name']}")


def main():
    upsert_managers()
    upsert_templates()
    print("\nDone. Refresh the ops dashboard — managers + templates should be visible.")


if __name__ == "__main__":
    main()
