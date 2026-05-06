"""Tool implementations for Gemini Live function calling.

Each handler is async, takes a dict of args from the model, and returns a
JSON-serializable dict that gets sent back to Gemini as the tool result.

Add a new tool by:
  1. Writing an async `handle_*` function
  2. Adding its declaration to TOOL_DECLS
  3. Registering it in TOOL_HANDLERS

Worker identity comes from .env (WORKER_ID, WORKER_NAME). For the demo
both default to a single worker so the tool calls land on consistent rows.
"""
from __future__ import annotations

import asyncio
import os
import smtplib
from datetime import datetime, timezone
from email.mime.text import MIMEText
from email.utils import formataddr
from typing import Any

from google.genai import types as genai_types
from supabase import Client, create_client

try:
    import resend as _resend_lib  # type: ignore
except ImportError:
    _resend_lib = None  # type: ignore


# ---------- Worker identity (override in .env) ----------
WORKER_ID = os.getenv("WORKER_ID", "demo_worker_001")
WORKER_NAME = os.getenv("WORKER_NAME", "Alaa")

# ---------- Email config — READ LAZILY ----------
# These MUST be read at call-time, not module-import-time, because
# `dashboard.server` calls load_dotenv AFTER importing this module.
def _email_config() -> dict[str, str]:
    return {
        "RESEND_API_KEY": os.getenv("RESEND_API_KEY", "").strip(),
        "RESEND_FROM":    os.getenv("RESEND_FROM_EMAIL",
                                    "VisionLink <onboarding@resend.dev>").strip(),
        "SMTP_EMAIL":     os.getenv("SMTP_EMAIL", "").strip(),
        "SMTP_APP_PASSWORD": os.getenv("SMTP_APP_PASSWORD", "").strip(),
        "SMTP_FROM_NAME": os.getenv("SMTP_FROM_NAME", "VisionLink").strip(),
    }


_sb: Client | None = None


def _get_sb() -> Client:
    global _sb
    if _sb is None:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_KEY")
        if not url or not key:
            raise RuntimeError(
                "SUPABASE_URL or SUPABASE_SERVICE_KEY missing in .env"
            )
        _sb = create_client(url, key)
    return _sb


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ============================================================
# Tool 1: lookup_component  (read-only)
# ============================================================

COMPONENT_COLS = (
    "name, part_code, description, "
    "torque_spec, maintenance_interval, safety_notes"
)


async def handle_lookup_component(args: dict[str, Any]) -> dict[str, Any]:
    """Search the components table by part_code (exact) then name (fuzzy)."""
    q = (args.get("query") or "").strip()
    if not q:
        return {"rows": []}

    sb = _get_sb()

    def _query() -> list[dict[str, Any]]:
        r = (sb.table("components")
               .select(COMPONENT_COLS)
               .ilike("part_code", q)
               .limit(3)
               .execute())
        if r.data:
            return r.data
        r = (sb.table("components")
               .select(COMPONENT_COLS)
               .ilike("name", f"%{q}%")
               .limit(3)
               .execute())
        return r.data or []

    rows = await asyncio.to_thread(_query)
    return {"rows": rows}


# ============================================================
# Tool 2: log_incident  (write)
# ============================================================

VALID_INCIDENT_CATEGORIES = {"safety", "equipment", "leak", "damage", "other"}
VALID_INCIDENT_SEVERITIES = {"low", "medium", "high", "critical"}


async def handle_log_incident(args: dict[str, Any]) -> dict[str, Any]:
    """Insert a row into the incidents table."""
    description = (args.get("description") or "").strip()
    if not description:
        return {"error": "description is required"}

    category = (args.get("category") or "other").lower()
    if category not in VALID_INCIDENT_CATEGORIES:
        category = "other"

    severity = (args.get("severity") or "medium").lower()
    if severity not in VALID_INCIDENT_SEVERITIES:
        severity = "medium"

    location = (args.get("location") or "").strip() or None

    sb = _get_sb()

    def _insert():
        return sb.table("incidents").insert({
            "worker_id": WORKER_ID,
            "worker_name": WORKER_NAME,
            "category": category,
            "severity": severity,
            "location": location,
            "description": description,
            "status": "open",
        }).execute()

    r = await asyncio.to_thread(_insert)
    if not r.data:
        return {"error": "insert failed — no row returned"}

    return {
        "ok": True,
        "incident_id": r.data[0]["id"],
        "category": category,
        "severity": severity,
        "location": location,
        "status": "logged",
        "worker_name": WORKER_NAME,
    }


# ============================================================
# Tool 3: mark_task_complete  (write)
# ============================================================

async def handle_mark_task_complete(args: dict[str, Any]) -> dict[str, Any]:
    """Find a pending task by title fragment and mark it complete.

    Returns ambiguous=True if multiple tasks match — Gemini should ask
    the worker to clarify rather than guessing.
    """
    task_query = (args.get("task_query") or "").strip()
    if not task_query:
        return {"error": "task_query is required"}

    sb = _get_sb()

    def _find_and_complete():
        r = (sb.table("worker_tasks")
               .select("id, title, priority, due_date")
               .eq("worker_id", WORKER_ID)
               .neq("status", "complete")
               .ilike("title", f"%{task_query}%")
               .limit(5)
               .execute())
        rows = r.data or []
        if len(rows) == 0:
            return {"matched": [], "completed": None}
        if len(rows) > 1:
            return {
                "matched": rows,
                "ambiguous": True,
                "completed": None,
            }
        task_id = rows[0]["id"]
        title = rows[0]["title"]
        sb.table("worker_tasks").update({
            "status": "complete",
            "completed_at": _now_iso(),
        }).eq("id", task_id).execute()
        return {"matched": rows, "completed": title}

    return await asyncio.to_thread(_find_and_complete)


# ============================================================
# Tool 4: get_my_assignments  (read-only)
# ============================================================

async def handle_get_my_assignments(args: dict[str, Any]) -> dict[str, Any]:
    """List the worker's tasks. Pending only by default."""
    include_complete = bool(args.get("include_complete", False))

    sb = _get_sb()

    def _query():
        q = (sb.table("worker_tasks")
               .select("id, title, description, priority, "
                       "due_date, status, component_part_code")
               .eq("worker_id", WORKER_ID))
        if not include_complete:
            q = q.neq("status", "complete")
        return q.order("priority", desc=True).order("due_date").execute()

    r = await asyncio.to_thread(_query)
    rows = r.data or []
    return {
        "worker_name": WORKER_NAME,
        "count": len(rows),
        "tasks": rows,
    }


# ============================================================
# Tool 5: request_part  (write)
# ============================================================

VALID_URGENCIES = {"normal", "urgent", "critical"}


async def handle_request_part(args: dict[str, Any]) -> dict[str, Any]:
    """Submit a parts order. Tries to auto-match against components table."""
    part_query = (args.get("part_query") or "").strip()
    if not part_query:
        return {"error": "part_query is required"}

    quantity = int(args.get("quantity", 1) or 1)
    if quantity < 1:
        quantity = 1

    urgency = (args.get("urgency") or "normal").lower()
    if urgency not in VALID_URGENCIES:
        urgency = "normal"

    reason = (args.get("reason") or "").strip() or None

    sb = _get_sb()

    def _do():
        match = (sb.table("components")
                   .select("name, part_code")
                   .ilike("name", f"%{part_query}%")
                   .limit(1)
                   .execute())
        matched_part_code = match.data[0]["part_code"] if match.data else None
        matched_name = match.data[0]["name"] if match.data else None

        ins = sb.table("part_requests").insert({
            "worker_id": WORKER_ID,
            "worker_name": WORKER_NAME,
            "part_query": part_query,
            "matched_part_code": matched_part_code,
            "quantity": quantity,
            "urgency": urgency,
            "reason": reason,
            "status": "submitted",
        }).execute()
        return {
            "request_id": ins.data[0]["id"] if ins.data else None,
            "matched_part_code": matched_part_code,
            "matched_part_name": matched_name,
        }

    result = await asyncio.to_thread(_do)
    return {
        "ok": True,
        **result,
        "quantity": quantity,
        "urgency": urgency,
        "status": "submitted",
    }


# ============================================================
# Tool declarations  (the schema Gemini sees)
# ============================================================

TOOL_DECLS: list[dict[str, Any]] = [
    {
        "name": "lookup_component",
        "description": (
            "Search the factory components database by name or part code. "
            "Use this for ANY question about a part, torque spec, "
            "maintenance interval, or safety note. Returns up to 3 rows "
            "with name, part_code, description, torque_spec, "
            "maintenance_interval, and safety_notes."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Component name (e.g. 'pump A3') or part code "
                        "(e.g. 'PMP-A3-IMP')."
                    ),
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "log_incident",
        "description": (
            "Log a safety issue, equipment problem, leak, or damage to "
            "the factory incident log. Call this whenever the worker "
            "reports something wrong on the floor — even if minor."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "description": {
                    "type": "string",
                    "description": (
                        "Plain-language description of the problem, "
                        "verbatim or close to what the worker said."
                    ),
                },
                "category": {
                    "type": "string",
                    "description": (
                        "One of: safety, equipment, leak, damage, other. "
                        "Defaults to 'other' if unclear."
                    ),
                },
                "severity": {
                    "type": "string",
                    "description": (
                        "One of: low, medium, high, critical. Match the "
                        "tone of the worker — 'critical' for things they "
                        "describe as urgent, dangerous, or stop-the-line."
                    ),
                },
                "location": {
                    "type": "string",
                    "description": (
                        "Where the issue is, if mentioned (e.g. "
                        "'conveyor 4', 'valve B7', 'pump A3 area')."
                    ),
                },
            },
            "required": ["description"],
        },
    },
    {
        "name": "mark_task_complete",
        "description": (
            "Mark one of the worker's pending tasks as complete. Provide "
            "a fragment of the task title — the system fuzzy-matches. If "
            "multiple tasks match, the response will list them and "
            "ambiguous=true; in that case ask the worker to be more specific."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "task_query": {
                    "type": "string",
                    "description": (
                        "Part of the task title to match (e.g. "
                        "'pump A3 inspection' or 'bearing service')."
                    ),
                },
            },
            "required": ["task_query"],
        },
    },
    {
        "name": "get_my_assignments",
        "description": (
            "Get the worker's task list, ordered by priority (high "
            "first) then due date. Returns pending tasks by default. "
            "Use when the worker asks 'what's on my list', 'what do I "
            "have to do', 'am I done for today', etc."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "include_complete": {
                    "type": "boolean",
                    "description": (
                        "Set true to include already-completed tasks in "
                        "the response. Default false."
                    ),
                },
            },
            "required": [],
        },
    },
    {
        "name": "request_part",
        "description": (
            "Submit a parts request. The system auto-matches the request "
            "against the components database to find a known part_code "
            "when possible. Use when the worker says they need a "
            "replacement, spare, or new part."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "part_query": {
                    "type": "string",
                    "description": (
                        "What the worker is asking for (e.g. "
                        "'replacement gasket for valve B7' or "
                        "'hydraulic filter')."
                    ),
                },
                "quantity": {
                    "type": "integer",
                    "description": "How many. Defaults to 1.",
                },
                "urgency": {
                    "type": "string",
                    "description": (
                        "One of: normal, urgent, critical. Match the "
                        "worker's words."
                    ),
                },
                "reason": {
                    "type": "string",
                    "description": (
                        "Why the part is needed (optional, e.g. "
                        "'old one is leaking', 'preventive maintenance')."
                    ),
                },
            },
            "required": ["part_query"],
        },
    },
]


TOOL_HANDLERS = {
    "lookup_component":   handle_lookup_component,
    "log_incident":       handle_log_incident,
    "mark_task_complete": handle_mark_task_complete,
    "get_my_assignments": handle_get_my_assignments,
    "request_part":       handle_request_part,
    # send_report registered below after its handler is defined
}


# ============================================================
# Tool 6: send_report  (write — sends an email)
# ============================================================

def _render_template(html: str, vars: dict[str, Any]) -> str:
    out = html
    for k, v in vars.items():
        out = out.replace("{{" + k + "}}", str(v) if v is not None else "")
    return out


def _bullet_list(items: list[str]) -> str:
    if not items:
        return "<p><i>None right now.</i></p>"
    return "<ul>" + "".join(f"<li>{i}</li>" for i in items) + "</ul>"


async def _fetch_live_context(sb: Client) -> dict[str, str]:
    """Pull live incidents/tasks/parts to inject into report templates."""
    def _fetch():
        inc = (sb.table("incidents")
                 .select("description,severity,location,status,reported_at")
                 .neq("status", "resolved")
                 .order("reported_at", desc=True)
                 .limit(5)
                 .execute())
        tsk = (sb.table("worker_tasks")
                 .select("title,priority,due_date,status")
                 .eq("worker_id", WORKER_ID)
                 .neq("status", "complete")
                 .order("priority", desc=True)
                 .limit(5)
                 .execute())
        prt = (sb.table("part_requests")
                 .select("part_query,quantity,urgency,status")
                 .neq("status", "delivered")
                 .order("requested_at", desc=True)
                 .limit(5)
                 .execute())
        return {
            "incidents": inc.data or [],
            "tasks": tsk.data or [],
            "parts": prt.data or [],
        }

    data = await asyncio.to_thread(_fetch)
    inc_html = _bullet_list([
        f"<b>{(i.get('severity') or 'medium').upper()}</b> · "
        f"{i.get('location') or 'unspecified location'} · "
        f"{i.get('description') or ''}"
        for i in data["incidents"]
    ])
    tsk_html = _bullet_list([
        f"<b>{(t.get('priority') or 'normal').upper()}</b> · {t.get('title') or ''} "
        f"(due {t.get('due_date') or '—'}, status: {t.get('status') or '—'})"
        for t in data["tasks"]
    ])
    prt_html = _bullet_list([
        f"<b>{(p.get('urgency') or 'normal').upper()}</b> · "
        f"{p.get('quantity') or 1}× {p.get('part_query') or ''} "
        f"(status: {p.get('status') or '—'})"
        for p in data["parts"]
    ])
    return {
        "recent_incidents": inc_html,
        "recent_tasks": tsk_html,
        "recent_parts": prt_html,
    }


def _send_via_gmail(to_email: str, subject: str, body_html: str) -> None:
    cfg = _email_config()
    msg = MIMEText(body_html, "html", "utf-8")
    msg["From"] = formataddr((cfg["SMTP_FROM_NAME"], cfg["SMTP_EMAIL"]))
    msg["To"] = to_email
    msg["Subject"] = subject
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as s:
        s.login(cfg["SMTP_EMAIL"], cfg["SMTP_APP_PASSWORD"])
        s.send_message(msg)


def _send_via_resend(to_email: str, subject: str, body_html: str) -> None:
    if _resend_lib is None:
        raise RuntimeError("resend package not installed")
    cfg = _email_config()
    _resend_lib.api_key = cfg["RESEND_API_KEY"]  # type: ignore
    _resend_lib.Emails.send({  # type: ignore
        "from": cfg["RESEND_FROM"],
        "to": to_email,
        "subject": subject,
        "html": body_html,
    })


async def handle_send_report(args: dict[str, Any]) -> dict[str, Any]:
    """Look up a manager + a report template, fill it with live data, send."""
    recipient_role = (args.get("recipient_role") or "").strip()
    recipient_name = (args.get("recipient_name") or "").strip()
    recipient_email_arg = (args.get("recipient_email") or "").strip()
    template_query = (args.get("report_name") or args.get("template") or "").strip()
    custom_message = (args.get("custom_message") or "").strip()

    if not template_query:
        return {"error": "report_name is required"}
    if not (recipient_role or recipient_name or recipient_email_arg):
        return {
            "error": "recipient_role, recipient_name, or recipient_email is required"
        }

    sb = _get_sb()

    def _find_recipient():
        if recipient_email_arg:
            return {
                "name": recipient_email_arg.split("@")[0],
                "email": recipient_email_arg,
                "role": "(direct)",
            }
        if recipient_role:
            r = (sb.table("managers")
                   .select("name,email,role")
                   .ilike("role", recipient_role)
                   .limit(1)
                   .execute())
            if r.data:
                return r.data[0]
        if recipient_name:
            r = (sb.table("managers")
                   .select("name,email,role")
                   .ilike("name", f"%{recipient_name}%")
                   .limit(1)
                   .execute())
            if r.data:
                return r.data[0]
        if recipient_role:
            r = (sb.table("managers")
                   .select("name,email,role")
                   .ilike("name", f"%{recipient_role}%")
                   .limit(1)
                   .execute())
            if r.data:
                return r.data[0]
        return None

    recipient = await asyncio.to_thread(_find_recipient)
    if not recipient:
        return {
            "error": (
                f"no manager found matching role='{recipient_role}' "
                f"or name='{recipient_name}'"
            ),
        }

    def _find_template():
        r = (sb.table("report_templates")
               .select("name,category,subject,body_html")
               .ilike("name", f"%{template_query}%")
               .limit(1)
               .execute())
        if r.data:
            return r.data[0]
        r = (sb.table("report_templates")
               .select("name,category,subject,body_html")
               .ilike("category", template_query)
               .limit(1)
               .execute())
        return r.data[0] if r.data else None

    tmpl = await asyncio.to_thread(_find_template)
    if not tmpl:
        return {"error": f"no report template matched '{template_query}'"}

    now = datetime.now()
    vars_dict: dict[str, str] = {
        "date":           now.strftime("%B %d, %Y"),
        "datetime":       now.strftime("%Y-%m-%d %H:%M"),
        "worker_name":    WORKER_NAME,
        "recipient_name": recipient.get("name") or "",
        "recipient_role": recipient.get("role") or "",
        "custom_message": custom_message or "(no additional note from the worker)",
    }

    needs_context = any(
        token in tmpl["body_html"]
        for token in ("{{recent_incidents}}", "{{recent_tasks}}", "{{recent_parts}}")
    )
    if needs_context:
        vars_dict.update(await _fetch_live_context(sb))

    subject = _render_template(tmpl["subject"], vars_dict)
    body = _render_template(tmpl["body_html"], vars_dict)

    cfg = _email_config()
    provider: str | None = None
    error_msg: str | None = None
    try:
        if cfg["RESEND_API_KEY"] and _resend_lib is not None:
            await asyncio.to_thread(_send_via_resend, recipient["email"], subject, body)
            provider = "resend"
        elif cfg["SMTP_EMAIL"] and cfg["SMTP_APP_PASSWORD"]:
            await asyncio.to_thread(_send_via_gmail, recipient["email"], subject, body)
            provider = "gmail_smtp"
        else:
            return {
                "error": (
                    "no email provider configured — set RESEND_API_KEY "
                    "OR SMTP_EMAIL+SMTP_APP_PASSWORD in .env then restart"
                ),
            }
    except Exception as e:
        error_msg = str(e)

    def _log_sent():
        sb.table("sent_reports").insert({
            "worker_id":       WORKER_ID,
            "worker_name":     WORKER_NAME,
            "recipient_name":  recipient.get("name"),
            "recipient_email": recipient.get("email"),
            "recipient_role":  recipient.get("role"),
            "template_name":   tmpl["name"],
            "subject":         subject,
            "body_html":       body,
            "custom_message":  custom_message or None,
            "status":          "failed" if error_msg else "sent",
            "error":           error_msg,
            "provider":        provider,
        }).execute()

    try:
        await asyncio.to_thread(_log_sent)
    except Exception as e:
        print(f"[send_report] sent_reports log insert failed: {e}", flush=True)

    if error_msg:
        return {
            "error":     f"send failed: {error_msg}",
            "to":        recipient.get("email"),
            "recipient": recipient.get("name"),
        }

    return {
        "ok":        True,
        "to":        recipient.get("email"),
        "recipient": recipient.get("name"),
        "role":      recipient.get("role"),
        "template":  tmpl["name"],
        "subject":   subject,
        "provider":  provider,
    }


TOOL_HANDLERS["send_report"] = handle_send_report

TOOL_DECLS.append({
    "name": "send_report",
    "description": (
        "Send a pre-written report email to a manager. The system finds "
        "the recipient by ROLE (e.g. 'CEO', 'supervisor', 'accountant') "
        "or by name, and the template by its name (e.g. 'daily operations "
        "report', 'incident report', 'quick note'). Live data — current "
        "incidents, tasks, parts requests — is automatically injected "
        "into reports that use those placeholders. The worker may also "
        "provide a custom_message that gets appended to the report."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "recipient_role": {
                "type": "string",
                "description": (
                    "The recipient's role (e.g. 'CEO', 'supervisor', "
                    "'accountant', 'QA manager'). Preferred over name."
                ),
            },
            "recipient_name": {
                "type": "string",
                "description": "Recipient's name, if no role is given.",
            },
            "recipient_email": {
                "type": "string",
                "description": (
                    "Direct email address. Use only if the worker dictates "
                    "an email explicitly."
                ),
            },
            "report_name": {
                "type": "string",
                "description": (
                    "Name (or category) of the report template, e.g. "
                    "'daily operations report', 'incident report', "
                    "'task status update', 'quick note'."
                ),
            },
            "custom_message": {
                "type": "string",
                "description": (
                    "Any additional note the worker wants in the report. "
                    "Verbatim from what they said."
                ),
            },
        },
        "required": ["report_name"],
    },
})


# ============================================================
# Schema conversion + Tool builder for LiveConnectConfig
# ============================================================

_TYPE_MAP = {
    "string": "STRING",
    "integer": "INTEGER",
    "number": "NUMBER",
    "boolean": "BOOLEAN",
    "array": "ARRAY",
    "object": "OBJECT",
}


def _schema_from_dict(d: dict[str, Any]) -> genai_types.Schema:
    """Convert an OpenAPI-ish dict into a typed genai Schema (uppercase enums)."""
    kwargs: dict[str, Any] = {}
    if "type" in d:
        kwargs["type"] = _TYPE_MAP.get(d["type"].lower(), d["type"].upper())
    if "description" in d:
        kwargs["description"] = d["description"]
    if "properties" in d:
        kwargs["properties"] = {
            k: _schema_from_dict(v) for k, v in d["properties"].items()
        }
    if "required" in d:
        kwargs["required"] = list(d["required"])
    if "items" in d:
        kwargs["items"] = _schema_from_dict(d["items"])
    return genai_types.Schema(**kwargs)


def build_tools() -> list[genai_types.Tool]:
    """Build the typed Tool list to plug into LiveConnectConfig(tools=...)."""
    decls = []
    for t in TOOL_DECLS:
        decls.append(genai_types.FunctionDeclaration(
            name=t["name"],
            description=t["description"],
            parameters=_schema_from_dict(t["parameters"]),
        ))
    return [genai_types.Tool(function_declarations=decls)]
