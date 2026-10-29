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


def _account_key_from_bundle(token_bundle: dict[str, Any]) -> str:
    """Validate a token bundle and derive its stable account key."""
    if not isinstance(token_bundle, dict):
        raise CanvaStoreError("A Canva token bundle must be an object.")
    access_token = token_bundle.get("access_token")
    if not isinstance(access_token, str) or not access_token.strip():
        raise CanvaStoreError("A non-empty Canva access token is required.")

    user_id = token_bundle.get("user_id")
    if user_id is None:
        return "default"
    if isinstance(user_id, bool) or not isinstance(user_id, (str, int)):
        raise CanvaStoreError("The Canva account ID is malformed.")
    account_key = str(user_id).strip()
    if not account_key:
        raise CanvaStoreError("The Canva account ID must not be empty.")
    return account_key


def save_canva_tokens(token_bundle: dict[str, Any], *, expires_at: datetime | None) -> None:
    """Encrypt and atomically upsert one account's Canva token bundle."""
    account_key = _account_key_from_bundle(token_bundle)
    if expires_at is not None and (
        not isinstance(expires_at, datetime)
        or expires_at.tzinfo is None
        or expires_at.utcoffset() is None
    ):
        raise CanvaStoreError("Token expiry must be timezone-aware.")

    try:
        serialized = json.dumps(token_bundle, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError):
        raise CanvaStoreError("Canva token bundle is not valid JSON data.") from None
    encrypted = encrypt_access_token(serialized)
    with _connect() as conn:
        conn.execute("""
            INSERT INTO nova_canva_tokens (account_key, encrypted_token_bundle, expires_at, updated_at)
            VALUES (%s, %s, %s, NOW())
            ON CONFLICT (account_key) DO UPDATE SET
                encrypted_token_bundle = EXCLUDED.encrypted_token_bundle,
                expires_at = EXCLUDED.expires_at,
                updated_at = NOW()
        """, (account_key, encrypted, expires_at.astimezone(timezone.utc) if expires_at else None))


def _decode_canva_token_row(row: dict[str, Any]) -> dict[str, Any]:
    """Decrypt a row and verify the encrypted bundle belongs to its database key."""
    account_key = row.get("account_key")
    encrypted = row.get("encrypted_token_bundle")
    if not isinstance(account_key, str) or not account_key.strip() or not isinstance(encrypted, str) or not encrypted:
        raise CanvaStoreError("Stored Canva token record is malformed.")
    try:
        bundle = json.loads(decrypt_access_token(encrypted))
    except (OAuthSecurityError, ValueError, TypeError, UnicodeError):
        raise CanvaStoreError("Stored Canva token bundle cannot be decrypted or parsed.") from None
    if not isinstance(bundle, dict):
        raise CanvaStoreError("Stored Canva token bundle is malformed.")

    try:
        bundle_account_key = _account_key_from_bundle(bundle)
    except CanvaStoreError:
        raise CanvaStoreError("Stored Canva token bundle is malformed.") from None
    if bundle_account_key != account_key:
        raise CanvaStoreError("Stored Canva token bundle does not match its account key.")

    # The separate database column is authoritative for expiry metadata.
    bundle["expires_at"] = row.get("expires_at")
    return bundle


def load_canva_tokens(account_key: str) -> dict[str, Any] | None:
    """Load one explicitly selected Canva account; never fall back to another account."""
    if not isinstance(account_key, str) or not account_key.strip():
        raise CanvaStoreError("A non-empty Canva account key is required.")
    with _connect() as conn:
        row = conn.execute("""
            SELECT account_key, encrypted_token_bundle, expires_at
            FROM nova_canva_tokens
            WHERE account_key = %s
        """, (account_key.strip(),)).fetchone()
    if row is None:
        return None
    return _decode_canva_token_row(row)


def load_latest_canva_tokens() -> dict[str, Any] | None:
    """Load the configured account, or the sole connected account for legacy setups.

    If multiple accounts exist, CANVA_ACCOUNT_KEY must explicitly select one. This
    avoids silently making API calls with whichever account was updated last.
    """
    configured_key = os.getenv("CANVA_ACCOUNT_KEY", "").strip()
    if configured_key:
        return load_canva_tokens(configured_key)

    with _connect() as conn:
        rows = conn.execute("""
            SELECT account_key, encrypted_token_bundle, expires_at
            FROM nova_canva_tokens ORDER BY updated_at DESC LIMIT 2
        """).fetchall()
    if not rows:
        return None
    if len(rows) > 1:
        raise CanvaStoreError("Multiple Canva accounts are connected. Set CANVA_ACCOUNT_KEY to the intended account key.")
    return _decode_canva_token_row(rows[0])


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
