"""Shared account authentication and global AI master switch."""
import base64
import hmac
import os

import psycopg
from fastapi import Header, HTTPException, Request

from app.session_auth import COOKIE_NAME, session_username


def require_user(request: Request, authorization: str | None = Header(default=None)):
    expected_user = os.getenv("NOVA_ADMIN_USERNAME", "").strip()
    expected_password = os.getenv("NOVA_ADMIN_PASSWORD", "")
    if not expected_user or not expected_password:
        raise HTTPException(status_code=503, detail="Admin login is not configured on the server.")

    # Browser sessions are revocable server-side. If a cookie is present but
    # invalid/expired, do not silently fall back to cached Basic credentials.
    session_token = request.cookies.get(COOKIE_NAME)
    if session_token:
        username = session_username(session_token)
        if username and hmac.compare_digest(username, expected_user):
            return True
        raise HTTPException(status_code=401, detail="Your NOVA session has expired. Please sign in again.")

    # Retain Basic auth for existing machine/API clients during migration.
    try:
        scheme, encoded = (authorization or "").split(" ", 1)
        username, password = base64.b64decode(encoded, validate=True).decode("utf-8").split(":", 1)
    except Exception:
        raise HTTPException(status_code=401, detail="Admin sign-in required.") from None
    if scheme.lower() != "basic" or not (
        hmac.compare_digest(username, expected_user)
        and hmac.compare_digest(password, expected_password)
    ):
        raise HTTPException(status_code=401, detail="Invalid admin credentials.")
    return True


def master_enabled() -> bool:
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        return False
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    try:
        with psycopg.connect(url, connect_timeout=3) as conn:
            row = conn.execute(
                "SELECT setting_value FROM nova_admin_settings WHERE setting_key='master_enabled'"
            ).fetchone()
        return bool(row and row[0] is True)
    except Exception:
        return False


def require_master_enabled():
    if not master_enabled():
        raise HTTPException(status_code=503, detail="NOVA AI master switch is OFF. An admin must turn it ON.")
    return True
