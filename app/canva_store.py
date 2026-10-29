"""Encrypted persistent storage for Canva Connect OAuth credentials."""
import json
from contextlib import contextmanager
import os
from datetime import datetime, timezone
from typing import Any

import psycopg
from psycopg.rows import dict_row

from app.oauth_security import encrypt_access_token, decrypt_access_token, OAuthSecurityError


class CanvaStoreError(RuntimeError):
    """Raised when Canva OAuth storage is unavailable."""


def _connect():
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        raise CanvaStoreError("DATABASE_URL is not configured.")
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    return psycopg.connect(url, row_factory=dict_row, connect_timeout=10)


def initialize_canva_schema() -> None:
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS nova_canva_tokens (
                account_key TEXT PRIMARY KEY,
                encrypted_token_bundle TEXT NOT NULL,
                expires_at TIMESTAMPTZ,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)


def save_canva_tokens(token_bundle: dict[str, Any], *, expires_at: datetime | None) -> None:
    if not isinstance(token_bundle, dict) or not token_bundle.get("access_token"):
        raise CanvaStoreError("A Canva access token is required.")
    if expires_at is not None and expires_at.tzinfo is None:
        raise CanvaStoreError("Token expiry must be timezone-aware.")
    encrypted = encrypt_access_token(json.dumps(token_bundle, separators=(",", ":")))
    account_key = str(token_bundle.get("user_id") or "default")
    with _connect() as conn:
        conn.execute("""
            INSERT INTO nova_canva_tokens (account_key, encrypted_token_bundle, expires_at, updated_at)
            VALUES (%s, %s, %s, NOW())
            ON CONFLICT (account_key) DO UPDATE SET
                encrypted_token_bundle = EXCLUDED.encrypted_token_bundle,
                expires_at = EXCLUDED.expires_at,
                updated_at = NOW()
        """, (account_key, encrypted, expires_at.astimezone(timezone.utc) if expires_at else None))


def load_latest_canva_tokens() -> dict[str, Any] | None:
    with _connect() as conn:
        row = conn.execute("""
            SELECT encrypted_token_bundle, expires_at
            FROM nova_canva_tokens ORDER BY updated_at DESC LIMIT 1
        """).fetchone()
    if row is None:
        return None
    try:
        bundle = json.loads(decrypt_access_token(row["encrypted_token_bundle"]))
    except (OAuthSecurityError, ValueError, TypeError):
        raise CanvaStoreError("Stored Canva token bundle cannot be decrypted.") from None
    bundle["expires_at"] = row["expires_at"]
    return bundle


# Session-level PostgreSQL advisory lock. This constant is stable across app
# instances and does not require a schema migration or lock table.
CANVA_REFRESH_ADVISORY_LOCK_KEY = 5642813379518752342


class CanvaRefreshInProgress(CanvaStoreError):
    """Raised when another worker is already rotating the Canva token."""


@contextmanager
def canva_refresh_lock():
    """Exclusively guard a refresh across processes using the shared PostgreSQL DB.

    The session-level lock survives commit while held, and closing this dedicated
    connection releases it even if the provider request raises or the worker exits.
    """
    try:
        conn = _connect()
    except psycopg.Error:
        raise CanvaStoreError("Canva refresh lock storage is unavailable.") from None

    acquired = False
    try:
        row = conn.execute(
            "SELECT pg_try_advisory_lock(%s) AS acquired",
            (CANVA_REFRESH_ADVISORY_LOCK_KEY,),
        ).fetchone()
        conn.commit()
        acquired = bool(row and row["acquired"])
        if not acquired:
            raise CanvaRefreshInProgress("A Canva token refresh is already in progress.")
        yield
    except psycopg.Error:
        raise CanvaStoreError("Canva refresh lock storage is unavailable.") from None
    finally:
        try:
            if acquired:
                try:
                    conn.execute(
                        "SELECT pg_advisory_unlock(%s)",
                        (CANVA_REFRESH_ADVISORY_LOCK_KEY,),
                    )
                    conn.commit()
                except psycopg.Error:
                    # Closing the dedicated session still releases the session lock.
                    pass
        finally:
            conn.close()
