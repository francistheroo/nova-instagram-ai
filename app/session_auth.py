"""Database-backed browser sessions for NOVA's web interface."""
import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone

import psycopg
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

router = APIRouter(prefix="/auth", tags=["authentication"])
COOKIE_NAME = "nova_session"
SESSION_DAYS = 7


def _database_url():
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        raise HTTPException(status_code=503, detail="Sign-in requires the NOVA session database. Configure DATABASE_URL.")
    return "postgresql://" + url[len("postgres://"):] if url.startswith("postgres://") else url


def _connect():
    return psycopg.connect(_database_url(), connect_timeout=5)


def _ensure_schema(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS nova_web_sessions (
            token_hash TEXT PRIMARY KEY,
            username TEXT NOT NULL,
            expires_at TIMESTAMPTZ NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def session_username(token: str | None) -> str | None:
    if not token:
        return None
    try:
        with _connect() as conn:
            _ensure_schema(conn)
            row = conn.execute(
                "SELECT username FROM nova_web_sessions WHERE token_hash=%s AND expires_at > NOW()",
                (_token_hash(token),),
            ).fetchone()
            return row[0] if row else None
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=503, detail="Session service is temporarily unavailable.") from None


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=256)


@router.post("/login")
async def login(body: LoginRequest, response: Response):
    expected_user = os.getenv("NOVA_ADMIN_USERNAME", "").strip()
    expected_password = os.getenv("NOVA_ADMIN_PASSWORD", "")
    if not expected_user or not expected_password:
        raise HTTPException(status_code=503, detail="Admin login is not configured on the server.")
    if not (hmac.compare_digest(body.username, expected_user) and hmac.compare_digest(body.password, expected_password)):
        raise HTTPException(status_code=401, detail="Incorrect username or password.")
    token = secrets.token_urlsafe(32)
    try:
        with _connect() as conn:
            _ensure_schema(conn)
            conn.execute("DELETE FROM nova_web_sessions WHERE expires_at <= NOW()")
            conn.execute(
                "INSERT INTO nova_web_sessions (token_hash, username, expires_at) VALUES (%s, %s, %s)",
                (_token_hash(token), expected_user, datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)),
            )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=503, detail="Could not create a login session. Check the session database.") from None
    response.set_cookie(
        COOKIE_NAME, token, max_age=SESSION_DAYS * 86400, httponly=True,
        secure=os.getenv("NOVA_COOKIE_SECURE", "true").lower() == "true",
        samesite="strict", path="/",
    )
    return {"authenticated": True, "username": expected_user, "expires_in": SESSION_DAYS * 86400}


@router.get("/status")
async def auth_status(request: Request):
    username = session_username(request.cookies.get(COOKIE_NAME))
    return {"authenticated": bool(username), "username": username}


@router.post("/logout")
async def logout(request: Request, response: Response):
    token = request.cookies.get(COOKIE_NAME)
    if token:
        try:
            with _connect() as conn:
                _ensure_schema(conn)
                conn.execute("DELETE FROM nova_web_sessions WHERE token_hash=%s", (_token_hash(token),))
        except Exception:
            raise HTTPException(status_code=503, detail="Could not revoke the session. Please try again.") from None
    response.delete_cookie(COOKIE_NAME, path="/", httponly=True, secure=os.getenv("NOVA_COOKIE_SECURE", "true").lower() == "true", samesite="strict")
    return {"authenticated": False}
