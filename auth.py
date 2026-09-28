"""
Authentication: signup, login, JWT issuance/verification.

- Passwords hashed with pbkdf2_hmac (stdlib, no extra dependency).
- JWTs signed with HS256 using JWT_SECRET from .env.
- `require_user` is the FastAPI dependency protecting endpoints.
"""

import hashlib
import hmac
import os
import secrets
import sqlite3
import time
from typing import Any

import jwt  # PyJWT
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from database import get_user_by_email, get_user_by_id

load_dotenv()

JWT_SECRET = os.getenv(
    "JWT_SECRET",
    "dev-only-insecure-secret-set-JWT_SECRET-in-your-env-file",
)
JWT_ALGORITHM = "HS256"
TOKEN_TTL_SECONDS = 7 * 24 * 3600  # 7 days


# ---------------------------------------------------------------------------
# Password hashing (pbkdf2_hmac)
# ---------------------------------------------------------------------------

def hash_password(password: str) -> str:
    """Return 'pbkdf2_sha256$iterations$salt$hash' for storage."""
    iterations = 200_000
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), iterations)
    return f"pbkdf2_sha256${iterations}${salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Constant-time password check against a stored hash."""
    try:
        scheme, iterations, salt, digest = stored.split("$")
        if scheme != "pbkdf2_sha256":
            return False
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(iterations))
        return hmac.compare_digest(candidate.hex(), digest)
    except (ValueError, TypeError):
        return False


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------

def create_access_token(user_id: str, email: str) -> str:
    """Issue a signed JWT for a user."""
    payload = {
        "sub": user_id,
        "email": email,
        "iat": int(time.time()),
        "exp": int(time.time()) + TOKEN_TTL_SECONDS,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT; raises jwt exceptions on failure."""
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------

_bearer = HTTPBearer(auto_error=False)


def require_user(request: Request,
                 credentials: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> sqlite3.Row:
    """
    Resolve the current user from the Authorization header.

    Raises 401 unless a valid Bearer token for an existing user is present.
    """
    if credentials is None or not credentials.credentials:
        raise HTTPException(status_code=401, detail="Authentication required. Please log in.")
    try:
        payload = decode_token(credentials.credentials)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expired. Please log in again.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid session token. Please log in again.")

    user = get_user_by_id(payload["sub"])
    if user is None:
        raise HTTPException(status_code=401, detail="Account no longer exists. Please log in again.")
    return user
