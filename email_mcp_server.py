"""
Email MCP Server — email capabilities for the report generator, exposed as
Model Context Protocol tools.

Tools:
    send_email      Send an email (Gmail API when connected, else local outbox)
    create_draft    Create a draft (optionally mirrored into Gmail drafts)
    send_draft      Send a previously created draft
    list_messages   List sent messages / inbox messages
    get_message     Fetch one message by id (or a draft by id)

Transports:
    python email_mcp_server.py              # stdio (spawned by email_mcp_client)
    python email_mcp_server.py --http 8001  # streamable HTTP for external MCP hosts

User context: tools take an optional `user_id` argument; when omitted they fall
back to the MCP_USER_ID environment variable (set by email_mcp_client) and then
to the single registered user, if exactly one exists.

Gmail sending reuses gmail_service (OAuth2 tokens, auto-refresh). When no Gmail
account is connected, messages are recorded in the local outbox (email_history
with status "local") so the full pipeline remains observable without Google
credentials — the tool result always states which path was taken.
"""

import base64
import json
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Any

# Project root on sys.path so the server works from any cwd / subprocess spawn.
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from mcp.server.mcpserver import MCPServer

import database
import gmail_service

server = MCPServer(
    name="reportforge-email",
    instructions=(
        "Email tools for ReportForge. send_email delivers a message; "
        "create_draft/send_draft manage drafts; list_messages/get_message "
        "read sent mail (local outbox or the connected Gmail account)."
    ),
)


# ---------------------------------------------------------------------------
# Context helpers
# ---------------------------------------------------------------------------

def _resolve_user(user_id: str | None) -> str | None:
    """Pick the acting user: explicit arg > MCP_USER_ID env > sole user."""
    uid = (user_id or "").strip() or (os.getenv("MCP_USER_ID") or "").strip()
    if uid:
        return uid
    conn = database.get_conn()
    rows = conn.execute("SELECT id FROM users LIMIT 2").fetchall()
    if len(rows) == 1:
        return rows[0]["id"]
    return None


def _require_user(user_id: str | None) -> str:
    uid = _resolve_user(user_id)
    if not uid:
        raise ValueError(
            "No user context: pass user_id, or set MCP_USER_ID, "
            "or register exactly one account."
        )
    if database.get_user_by_id(uid) is None:
        raise ValueError(f"Unknown user_id: {uid}")
    return uid


def _ok(**fields: Any) -> str:
    return json.dumps({"ok": True, **fields}, ensure_ascii=False, default=str)


def _err(message: str) -> str:
    return json.dumps({"ok": False, "error": message}, ensure_ascii=False)


def _gmail_connected(user_id: str) -> bool:
    return gmail_service.is_connected(user_id)


def _record_local(user_id: str, to: str, subject: str, body: str,
                  report_name: str | None) -> dict[str, Any]:
    """Fallback delivery: keep the message in the local outbox/history."""
    row = database.record_email(
        user_id, recipient=to, subject=subject, status="local",
        report_name=report_name, message_id=f"local-{uuid.uuid4().hex[:16]}",
    )
    return {"status": "local", "message_id": row["message_id"],
            "note": "Gmail not connected — message stored in the local outbox."}


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@server.tool()
def send_email(to: str, subject: str, body: str,
               user_id: str | None = None, report_name: str | None = None) -> str:
    """Send an email to a recipient.

    Uses the connected Gmail account when available; otherwise the message is
    stored in the local outbox. Returns {ok, status, message_id, note?}.
    """
    try:
        uid = _require_user(user_id)
        if not to or "@" not in to:
            return _err(f"Invalid recipient: {to!r}")
        if not subject:
            subject = "ReportForge message"

        if _gmail_connected(uid):
            try:
                user = database.get_user_by_id(uid)
                message_id = gmail_service.send_report_email(
                    user, to, subject, body, report_name)
                database.record_email(uid, recipient=to, subject=subject,
                                      status="sent", report_name=report_name,
                                      message_id=message_id)
                return _ok(status="sent", message_id=message_id,
                           recipient=to, subject=subject)
            except Exception as e:  # Gmail API failure -> do not lose the mail
                database.record_email(uid, recipient=to, subject=subject,
                                      status="failed", report_name=report_name,
                                      error=str(e))
                return _err(f"Gmail send failed: {e}")

        result = _record_local(uid, to, subject, body, report_name)
        return _ok(recipient=to, subject=subject, **result)
    except Exception as e:
        return _err(str(e))


@server.tool()
def create_draft(to: str, subject: str, body: str,
                 user_id: str | None = None, report_name: str | None = None) -> str:
    """Create an email draft. Returns {ok, draft_id, gmail_draft_id?}."""
    try:
        uid = _require_user(user_id)
        if not to or "@" not in to:
            return _err(f"Invalid recipient: {to!r}")
        if not subject:
            subject = "ReportForge message"

        gmail_draft_id = None
        if _gmail_connected(uid):
            try:
                raw, _ = gmail_service._mime_message(to, subject, body, report_name)
                resp = _gmail_post(uid, "/gmail/v1/users/me/drafts",
                                   {"message": {"raw": raw}})
                if resp:
                    gmail_draft_id = (resp.get("draft") or {}).get("id") or resp.get("id")
            except Exception:
                gmail_draft_id = None  # fall back to a local-only draft

        draft_id = database.create_email_draft(
            uid, recipient=to, subject=subject, body=body,
            report_name=report_name, gmail_draft_id=gmail_draft_id)
        return _ok(draft_id=draft_id, gmail_draft_id=gmail_draft_id,
                   stored_in="gmail+local" if gmail_draft_id else "local")
    except Exception as e:
        return _err(str(e))


@server.tool()
def send_draft(draft_id: str, user_id: str | None = None) -> str:
    """Send a draft created with create_draft. Returns {ok, status, message_id}."""
    try:
        uid = _require_user(user_id)
        draft = database.get_email_draft(draft_id)
        if draft is None or draft["user_id"] != uid:
            return _err(f"Unknown draft: {draft_id}")

        if draft["status"] == "sent":
            return _err(f"Draft {draft_id} was already sent")

        # Gmail-backed draft: hand it to Gmail's drafts/send endpoint.
        if draft["gmail_draft_id"] and _gmail_connected(uid):
            try:
                resp = _gmail_post(uid, "/gmail/v1/users/me/drafts/send",
                                   {"id": draft["gmail_draft_id"]})
                if resp:
                    database.mark_draft_sent(draft_id)
                    database.record_email(uid, recipient=draft["recipient"],
                                          subject=draft["subject"], status="sent",
                                          report_name=draft["report_name"],
                                          message_id=resp.get("id", ""))
                    return _ok(status="sent", message_id=resp.get("id", ""),
                               recipient=draft["recipient"], subject=draft["subject"])
            except Exception as e:
                database.record_email(uid, recipient=draft["recipient"],
                                      subject=draft["subject"], status="failed",
                                      report_name=draft["report_name"], error=str(e))
                return _err(f"Gmail draft send failed: {e}")

        # Local draft: deliver through the normal send path.
        if _gmail_connected(uid):
            try:
                user = database.get_user_by_id(uid)
                message_id = gmail_service.send_report_email(
                    user, draft["recipient"], draft["subject"],
                    draft["body"], draft["report_name"])
                database.mark_draft_sent(draft_id)
                database.record_email(uid, recipient=draft["recipient"],
                                      subject=draft["subject"], status="sent",
                                      report_name=draft["report_name"],
                                      message_id=message_id)
                return _ok(status="sent", message_id=message_id,
                           recipient=draft["recipient"], subject=draft["subject"])
            except Exception as e:
                database.record_email(uid, recipient=draft["recipient"],
                                      subject=draft["subject"], status="failed",
                                      report_name=draft["report_name"], error=str(e))
                return _err(f"Gmail send failed: {e}")

        database.mark_draft_sent(draft_id)
        result = _record_local(uid, draft["recipient"], draft["subject"],
                               draft["body"], draft["report_name"])
        return _ok(recipient=draft["recipient"], subject=draft["subject"], **result)
    except Exception as e:
        return _err(str(e))


@server.tool()
def list_messages(user_id: str | None = None, query: str | None = None,
                  max_results: int = 10) -> str:
    """List recent messages: the connected Gmail inbox when available,
    otherwise sent mail from the local outbox. Returns {ok, messages:[...]}."""
    try:
        uid = _require_user(user_id)
        max_results = max(1, min(int(max_results or 10), 25))

        if _gmail_connected(uid):
            try:
                params = {"maxResults": max_results}
                if query:
                    params["q"] = query
                resp = _gmail_get(uid, "/gmail/v1/users/me/messages", params)
                items = (resp or {}).get("messages", [])
                messages = []
                for entry in items[:max_results]:
                    meta = _gmail_get(
                        uid, f"/gmail/v1/users/me/messages/{entry['id']}",
                        {"format": "metadata",
                         "metadataHeaders": ["Subject", "From", "Date"]}) or {}
                    headers = {
                        h["name"].lower(): h["value"]
                        for h in (meta.get("payload", {}).get("headers") or [])
                    }
                    messages.append({
                        "id": meta.get("id", entry["id"]),
                        "source": "gmail",
                        "subject": headers.get("subject", ""),
                        "from": headers.get("from", ""),
                        "date": headers.get("date", ""),
                        "snippet": meta.get("snippet", ""),
                    })
                return _ok(messages=messages, source="gmail")
            except Exception as e:
                return _err(f"Gmail list failed: {e}")

        conn = database.get_conn()
        rows = conn.execute(
            """
            SELECT message_id, recipient, subject, status, report_name, created_at
            FROM email_history WHERE user_id = ?
            ORDER BY created_at DESC LIMIT ?
            """, (uid, max_results)).fetchall()
        messages = [{
            "id": r["message_id"] or r["message_id"],
            "source": "local",
            "recipient": r["recipient"],
            "subject": r["subject"],
            "status": r["status"],
            "report_name": r["report_name"],
            "date": r["created_at"],
        } for r in rows if r["message_id"]]
        if query:
            q = query.lower()
            messages = [m for m in messages
                        if q in (m.get("subject") or "").lower()
                        or q in (m.get("recipient") or "").lower()]
        return _ok(messages=messages, source="local")
    except Exception as e:
        return _err(str(e))


@server.tool()
def get_message(message_id: str, user_id: str | None = None) -> str:
    """Fetch a message (or a local draft) by id. Returns {ok, message:{...}}."""
    try:
        uid = _require_user(user_id)
        if not message_id:
            return _err("message_id is required")

        # Local drafts keep their full body.
        draft = database.get_email_draft(message_id)
        if draft is not None and draft["user_id"] == uid:
            return _ok(message={
                "id": draft["id"], "source": "draft", "status": draft["status"],
                "recipient": draft["recipient"], "subject": draft["subject"],
                "body": draft["body"], "report_name": draft["report_name"],
                "date": draft["created_at"],
            })

        # Local outbox records.
        conn = database.get_conn()
        row = conn.execute(
            "SELECT * FROM email_history WHERE user_id = ? AND message_id = ?",
            (uid, message_id)).fetchone()
        if row is not None:
            return _ok(message={
                "id": row["message_id"], "source": "local", "status": row["status"],
                "recipient": row["recipient"], "subject": row["subject"],
                "error": row["error"], "report_name": row["report_name"],
                "date": row["created_at"],
                "note": "Body not persisted for sent messages.",
            })

        # Otherwise try the connected Gmail account.
        if _gmail_connected(uid):
            try:
                meta = _gmail_get(
                    uid, f"/gmail/v1/users/me/messages/{message_id}",
                    {"format": "full"}) or {}
                headers = {
                    h["name"].lower(): h["value"]
                    for h in (meta.get("payload", {}).get("headers") or [])
                }
                body_text = _decode_gmail_body(meta.get("payload", {}))
                return _ok(message={
                    "id": meta.get("id", message_id), "source": "gmail",
                    "subject": headers.get("subject", ""),
                    "from": headers.get("from", ""),
                    "to": headers.get("to", ""),
                    "date": headers.get("date", ""),
                    "body": body_text,
                })
            except Exception as e:
                return _err(f"Gmail message fetch failed: {e}")

        return _err(f"Message not found: {message_id}")
    except Exception as e:
        return _err(str(e))


# ---------------------------------------------------------------------------
# Gmail REST helpers (thin wrappers around gmail_service auth)
# ---------------------------------------------------------------------------

def _gmail_api(user_id: str, path: str, params: dict | None = None,
               payload: dict | None = None, method: str = "GET") -> dict | None:
    import requests
    user = database.get_user_by_id(user_id)
    if user is None:
        return None
    token = gmail_service.get_access_token(user)
    url = (f"https://gmail.googleapis.com{path}" if path.startswith("/gmail")
           else f"https://gmail.googleapis.com/gmail/v1/users/me{path}")
    resp = requests.request(
        method, url, params=params, json=payload,
        headers={"Authorization": f"Bearer {token}"},
        timeout=20,
    )
    if resp.status_code not in (200, 201, 204):
        raise RuntimeError(f"Gmail API {method} {path} -> HTTP {resp.status_code}")
    return resp.json() if resp.content else None


def _gmail_get(user_id: str, path: str, params: dict | None = None) -> dict | None:
    return _gmail_api(user_id, path, params=params)


def _gmail_post(user_id: str, path: str, payload: dict) -> dict | None:
    return _gmail_api(user_id, path, payload=payload, method="POST")


def _decode_gmail_body(payload: dict) -> str:
    """Walk a Gmail message payload and decode any text/plain body."""
    parts = payload.get("parts") or []
    for part in parts:
        if part.get("mimeType") == "text/plain":
            data = part.get("body", {}).get("data")
            if data:
                return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
        nested = _decode_gmail_body(part)
        if nested:
            return nested
    data = payload.get("body", {}).get("data")
    if data and payload.get("mimeType") == "text/plain":
        return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
    return ""


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # python email_mcp_server.py [--http [PORT]]
    if "--http" in sys.argv:
        idx = sys.argv.index("--http")
        port = int(sys.argv[idx + 1]) if len(sys.argv) > idx + 1 and sys.argv[idx + 1].isdigit() else 8001
        server.run(transport="streamable-http", host="127.0.0.1", port=port)
    else:
        server.run(transport="stdio")
