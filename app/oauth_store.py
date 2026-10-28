"""PostgreSQL persistence for OAuth state and encrypted Instagram tokens.

Call initialize_schema() during deployment/migration, not on every request.
OAuth state is consumed with a single DELETE ... RETURNING operation, making
it one-time across multiple app instances when backed by PostgreSQL.
"""
import os
from datetime import datetime, timezone
from typing import Optional

import psycopg
from psycopg.rows import dict_row

from app.oauth_security import encrypt_access_token, decrypt_access_token, OAuthSecurityError


class OAuthStoreError(RuntimeError):
    """Raised when persistent OAuth storage is not configured."""


def _database_url() -> str:
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        raise OAuthStoreError("DATABASE_URL is not configured.")
    # Some providers still supply the legacy scheme.
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    return url


def _connect():
    return psycopg.connect(_database_url(), row_factory=dict_row, connect_timeout=10)


def initialize_schema() -> None:
    """Create the minimal OAuth tables if they do not exist."""
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS nova_oauth_states (
                nonce TEXT PRIMARY KEY,
                expires_at TIMESTAMPTZ NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS nova_instagram_tokens (
                instagram_user_id TEXT PRIMARY KEY,
                encrypted_access_token TEXT NOT NULL,
                expires_at TIMESTAMPTZ,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS nova_oauth_states_expiry_idx ON nova_oauth_states (expires_at)"
        )


def save_oauth_state(nonce: str, *, expires_at: datetime) -> None:
    """Persist the state nonce before redirecting the user to Meta."""
    if not nonce or expires_at.tzinfo is None:
        raise OAuthStoreError("A nonce and timezone-aware expiry are required.")
    with _connect() as conn:
        conn.execute(
            "INSERT INTO nova_oauth_states (nonce, expires_at) VALUES (%s, %s)",
            (nonce, expires_at.astimezone(timezone.utc)),
        )


def consume_oauth_state(nonce: str, *, now: Optional[datetime] = None) -> bool:
    """Atomically consume an unexpired nonce; returns False for replay/expiry."""
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise OAuthStoreError("now must be timezone-aware.")
    with _connect() as conn:
        row = conn.execute(
            """
            DELETE FROM nova_oauth_states
            WHERE nonce = %s AND expires_at > %s
            RETURNING nonce
            """,
            (nonce, current.astimezone(timezone.utc)),
        ).fetchone()
        # Expired rows are not usable; opportunistically remove this nonce.
        if row is None:
            conn.execute("DELETE FROM nova_oauth_states WHERE nonce = %s", (nonce,))
            return False
        return True


def save_instagram_token(
    instagram_user_id: str,
    access_token: str,
    *,
    expires_at: Optional[datetime],
) -> None:
    """Store only the encrypted token; keep encryption key outside the database."""
    if not instagram_user_id.strip():
        raise OAuthStoreError("Instagram user ID is required.")
    if expires_at is not None and expires_at.tzinfo is None:
        raise OAuthStoreError("Token expiry must be timezone-aware.")
    encrypted = encrypt_access_token(access_token)
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO nova_instagram_tokens
                (instagram_user_id, encrypted_access_token, expires_at, updated_at)
            VALUES (%s, %s, %s, NOW())
            ON CONFLICT (instagram_user_id) DO UPDATE SET
                encrypted_access_token = EXCLUDED.encrypted_access_token,
                expires_at = EXCLUDED.expires_at,
                updated_at = NOW()
            """,
            (
                instagram_user_id,
                encrypted,
                expires_at.astimezone(timezone.utc) if expires_at else None,
            ),
        )


def load_instagram_token(instagram_user_id: str) -> Optional[dict]:
    """Return the token only to trusted server code; never serialize it to clients."""
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT encrypted_access_token, expires_at, updated_at
            FROM nova_instagram_tokens
            WHERE instagram_user_id = %s
            """,
            (instagram_user_id,),
        ).fetchone()
    if row is None:
        return None
    try:
        token = decrypt_access_token(row["encrypted_access_token"])
    except OAuthSecurityError:
        raise
    return {
        "access_token": token,
        "expires_at": row["expires_at"],
        "updated_at": row["updated_at"],
    }


def delete_instagram_token(instagram_user_id: str) -> bool:
    """Remove a connected account's stored credential."""
    with _connect() as conn:
        row = conn.execute(
            "DELETE FROM nova_instagram_tokens WHERE instagram_user_id = %s RETURNING instagram_user_id",
            (instagram_user_id,),
        ).fetchone()
    return row is not None
