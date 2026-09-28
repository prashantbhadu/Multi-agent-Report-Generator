"""
Email MCP client — sync wrappers over a stdio MCP session with
email_mcp_server.py.

The report pipeline (LangGraph, synchronous) and FastAPI endpoints both call
these helpers; each call spawns the MCP server as a subprocess, performs the
JSON-RPC handshake, invokes one tool, and shuts the session down. That keeps
callers free of asyncio and of session bookkeeping.

Usage:
    from email_mcp_client import mcp_send_email
    result = mcp_send_email(to="a@b.c", subject="Hi", body="...",
                            user_id="...")  # -> dict {"ok": True, ...}

Async internals (mcp SDK) are run via asyncio.run() on a worker thread so they
are safe to call from FastAPI threadpool handlers and LangGraph nodes alike.
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
SERVER_SCRIPT = ROOT / "email_mcp_server.py"

TOOL_TIMEOUT = 90  # seconds per tool call (Gmail API included)


# ---------------------------------------------------------------------------
# Async core
# ---------------------------------------------------------------------------

async def _call_tool_async(tool: str, arguments: dict[str, Any],
                           user_id: str | None,
                           timeout: int = TOOL_TIMEOUT) -> dict[str, Any]:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    env = dict(os.environ)
    if user_id:
        env["MCP_USER_ID"] = user_id

    params = StdioServerParameters(
        command=sys.executable,
        args=[str(SERVER_SCRIPT)],
        cwd=str(ROOT),
        env=env,
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await asyncio.wait_for(session.initialize(), timeout=15)
            result = await asyncio.wait_for(
                session.call_tool(tool, arguments or {}), timeout=timeout)
    return _parse_result(result)


def _parse_result(result: Any) -> dict[str, Any]:
    """Turn a CallToolResult into a plain dict (mcp 2.x uses `is_error`)."""
    failed = bool(getattr(result, "is_error", False) or getattr(result, "isError", False))
    if failed:
        text = _content_text(result)
        return {"ok": False, "error": text or "MCP tool returned an error"}
    text = _content_text(result)
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
        return {"ok": True, "result": parsed}
    except (json.JSONDecodeError, TypeError):
        return {"ok": True, "result": text}


def _content_text(result: Any) -> str:
    content = getattr(result, "content", None) or []
    chunks = []
    for block in content:
        text = getattr(block, "text", None)
        if text:
            chunks.append(text)
    return "\n".join(chunks).strip()


# ---------------------------------------------------------------------------
# Sync entry point
# ---------------------------------------------------------------------------

def call_email_tool(tool: str, arguments: dict[str, Any] | None = None,
                    user_id: str | None = None, timeout: int = TOOL_TIMEOUT) -> dict[str, Any]:
    """Invoke one Email MCP tool and return its result dict.

    Never raises for tool-level failures — the MCP server reports errors as
    {"ok": False, "error": ...}. Raises only if the server cannot start.
    """
    if not SERVER_SCRIPT.exists():
        return {"ok": False, "error": f"MCP server not found: {SERVER_SCRIPT}"}

    async def runner() -> dict[str, Any]:
        return await _call_tool_async(tool, arguments or {}, user_id, timeout)

    try:
        # Runs in a worker thread: safe even if the caller already has a loop.
        return asyncio.run(runner())
    except Exception as e:
        return {"ok": False, "error": f"MCP call to '{tool}' failed: {e}"}


# ---------------------------------------------------------------------------
# Typed convenience wrappers for the five tools
# ---------------------------------------------------------------------------

def mcp_send_email(to: str, subject: str, body: str,
                   user_id: str | None = None, report_name: str | None = None) -> dict[str, Any]:
    """send_email tool: deliver an email; returns {ok, status, message_id}."""
    return call_email_tool("send_email", {
        "to": to, "subject": subject, "body": body, "report_name": report_name,
    }, user_id=user_id)


def mcp_create_draft(to: str, subject: str, body: str,
                     user_id: str | None = None,
                     report_name: str | None = None) -> dict[str, Any]:
    """create_draft tool: store a draft; returns {ok, draft_id}."""
    return call_email_tool("create_draft", {
        "to": to, "subject": subject, "body": body, "report_name": report_name,
    }, user_id=user_id)


def mcp_send_draft(draft_id: str, user_id: str | None = None) -> dict[str, Any]:
    """send_draft tool: deliver a stored draft; returns {ok, status}."""
    return call_email_tool("send_draft", {"draft_id": draft_id}, user_id=user_id)


def mcp_list_messages(user_id: str | None = None, query: str | None = None,
                      max_results: int = 10) -> dict[str, Any]:
    """list_messages tool: recent messages (Gmail or local outbox)."""
    return call_email_tool("list_messages", {
        "query": query, "max_results": max_results,
    }, user_id=user_id)


def mcp_get_message(message_id: str, user_id: str | None = None) -> dict[str, Any]:
    """get_message tool: fetch one message/draft by id."""
    return call_email_tool("get_message", {"message_id": message_id}, user_id=user_id)


if __name__ == "__main__":
    # Manual check:  python email_mcp_client.py
    print("list_messages ->", json.dumps(mcp_list_messages(), indent=2)[:800])
