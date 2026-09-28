"""
Gmail OAuth2 integration: connect a Gmail account, send report emails.

Implements the OAuth2 authorization-code flow directly against Google's
endpoints (no extra SDK dependency):

1. Frontend opens  GET /api/gmail/authorize  ->  302 to Google's consent screen.
2. Google redirects back to  GET /api/gmail/callback?code=...
   The backend exchanges the code, stores tokens per-user, and redirects the
   browser back to the frontend with ?gmail=connected.
3. Sending uses the stored (auto-refreshed) access token against
   https://gmail.googleapis.com/gmail/v1/users/me/messages/send (non-upload
   endpoint, accepts JSON).
Setup: create OAuth client credentials at https://console.cloud.google.com
(APs & Services -> Credentials), enable the Gmail API, and add to .env:

    GOOGLE_CLIENT_ID=...
    GOOGLE_CLIENT_SECRET=...
    GMAIL_REDIRECT_URI=http://localhost:8000/api/gmail/callback
"""

import base64
import os
import secrets
import sqlite3
import time
from urllib.parse import urlencode

import requests
from dotenv import load_dotenv
from fastapi import HTTPException

from database import get_gmail_token, upsert_gmail_token

load_dotenv()

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GMAIL_SEND_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"

GMAIL_SCOPES = [
    "https://mail.google.com/",          # send-only practical scope for SMTP-equivalent send
    "https://www.googleapis.com/auth/userinfo.email",
    "openid",
]

OAUTH_STATE_TTL = 600  # seconds


def _credentials() -> tuple[str, str, str]:
    """Load and sanity-check Google OAuth credentials from .env."""
    client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
    redirect_uri = os.getenv(
        "GMAIL_REDIRECT_URI", "http://localhost:8000/api/gmail/callback"
    ).strip()
    if not client_id or not client_secret:
        raise HTTPException(
            status_code=500,
            detail="Gmail is not configured: set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env",
        )
    return client_id, client_secret, redirect_uri


# ---------------------------------------------------------------------------
# In-memory OAuth state (CSRF protection + user binding for the consent flow)
# ---------------------------------------------------------------------------

_oauth_states: dict[str, tuple[str, float]] = {}  # state -> (user_id, issued_at)


def _new_state(user_id: str) -> str:
    _prune_states()
    state = secrets.token_urlsafe(32)
    _oauth_states[state] = (user_id, time.time())
    return state


def _pop_state(state: str | None) -> str | None:
    """One-time consume of a state value; returns the bound user_id or None."""
    if not state:
        return None
    entry = _oauth_states.pop(state, None)
    if entry is None:
        return None
    user_id, issued = entry
    if (time.time() - issued) > OAUTH_STATE_TTL:
        return None
    return user_id


def _prune_states() -> None:
    now = time.time()
    expired = [
        s for s, (_uid, issued_at) in _oauth_states.items()
        if now - issued_at > OAUTH_STATE_TTL
    ]
    for s in expired:
        _oauth_states.pop(s, None)


def build_authorize_url(user_id: str) -> str:
    """Google consent-screen URL with offline access for refresh tokens."""
    client_id, _, redirect_uri = _credentials()
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(GMAIL_SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": _new_state(user_id),
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


def exchange_code(code: str) -> dict:
    """Exchange the OAuth code for access/refresh tokens + id_token claims."""
    client_id, client_secret, redirect_uri = _credentials()
    resp = requests.post(GOOGLE_TOKEN_URL, data={
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }, timeout=15)
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"Gmail token exchange failed: {resp.text[:200]}")
    return resp.json()


def _decode_id_token_email(id_token: str) -> str | None:
    """Extract `email` claim from Google's id_token (signature already verified
    by token exchange over TLS; we only read the claim)."""
    try:
        import json
        payload_b64 = id_token.split(".")[1]
        payload_b64 += "=" * (-len(payload_b64) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload_b64))
        return claims.get("email")
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Token persistence + refresh
# ---------------------------------------------------------------------------

def store_connection(user_id: str, token_response: dict) -> str:
    """Persist tokens from an OAuth token response; returns the gmail address."""
    access = token_response.get("access_token", "")
    refresh = token_response.get("refresh_token")  # present thanks to access_type=offline
    expires_in = int(token_response.get("expires_in", 3600))
    scope = token_response.get("scope", "")
    email = _decode_id_token_email(token_response.get("id_token", "")) or ""

    upsert_gmail_token(
        user_id,
        access_token=access,
        refresh_token=refresh,
        token_expires=time.time() + expires_in - 60,  # refresh 1 min early
        scope=scope,
        connected_at=time.time(),
        **({"email": email} if email else {}),
    )
    return email


def _refresh_access_token(refresh_token: str) -> dict:
    client_id, client_secret, _ = _credentials()
    resp = requests.post(GOOGLE_TOKEN_URL, data={
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }, timeout=15)
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"Gmail token refresh failed: {resp.text[:200]}")
    return resp.json()


def get_access_token(user: sqlite3.Row) -> str:
    """Return a valid access token for the user, refreshing if needed."""
    row = get_gmail_token(user["id"])
    if row is None or not row["refresh_token"]:
        raise HTTPException(status_code=400, detail="Gmail is not connected. Connect it in Settings first.")
    if row["access_token"] and time.time() < row["token_expires"]:
        return row["access_token"]
    refreshed = _refresh_access_token(row["refresh_token"])
    upsert_gmail_token(
        user["id"],
        access_token=refreshed.get("access_token", ""),
        token_expires=time.time() + int(refreshed.get("expires_in", 3600)) - 60,
    )
    return refreshed.get("access_token", "")


def is_connected(user_id: str) -> bool:
    """True if the user has a stored refresh token."""
    row = get_gmail_token(user_id)
    return bool(row and row["refresh_token"])


# ---------------------------------------------------------------------------
# Sending
# ---------------------------------------------------------------------------

def _mime_message(to: str, subject: str, body_markdown: str, report_name: str | None) -> tuple[str, str]:
    """Build a simple RFC 2822 message; returns (raw_b64, subject)."""
    boundary = "reportforge-alt-boundary"
    text = (
        f"Your report is attached below as plain text.\n\n"
        f"Report: {report_name or 'generated report'}\n\n"
        f"{'=' * 60}\n\n{body_markdown}"
    )
    html = (
        "<html><body style=\"font-family: -apple-system, Segoe UI, sans-serif; "
        "max-width: 760px; margin: 0 auto;\">"
        f"<p>Your report <b>{report_name or 'generated report'}</b> is below.</p>"
        f"<pre style=\"white-space: pre-wrap; background: #f6f7f9; padding: 16px; "
        f"border-radius: 8px;\">{body_markdown}</pre></body></html>"
    )
    msg = (
        f"To: {to}\r\n"
        f"Subject: {subject}\r\n"
        f"MIME-Version: 1.0\r\n"
        f"Content-Type: multipart/alternative; boundary=\"{boundary}\"\r\n\r\n"
        f"--{boundary}\r\n"
        f"Content-Type: text/plain; charset=\"UTF-8\"\r\n\r\n"
        f"{text}\r\n\r\n"
        f"--{boundary}\r\n"
        f"Content-Type: text/html; charset=\"UTF-8\"\r\n\r\n"
        f"{html}\r\n\r\n"
        f"--{boundary}--"
    )
    return base64.urlsafe_b64encode(msg.encode("utf-8")).decode("ascii"), subject


def send_report_email(user: sqlite3.Row, recipient: str, subject: str,
                      body_markdown: str, report_name: str | None = None) -> str:
    """
    Send an email via the Gmail API and return the provider message id.
    Raises HTTPException on failure.
    """
    access = get_access_token(user)
    raw_b64, _ = _mime_message(to=recipient, subject=subject,
                               body_markdown=body_markdown, report_name=report_name)
    resp = requests.post(
        GMAIL_SEND_URL,
        headers={"Authorization": f"Bearer {access}",
                 "Content-Type": "application/json"},
        json={"raw": raw_b64},
        timeout=30,
    )
    if resp.status_code != 200:
        raise HTTPException(status_code=502,
                            detail=f"Gmail send failed: {resp.text[:200]}")
    return resp.json().get("id", "")
