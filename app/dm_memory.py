"""Short-lived Instagram DM conversation memory.

Each message is retained for at most 12 hours from insertion. The API is
server-key protected and stores data in PostgreSQL; expired rows are removed
on writes and excluded from reads. This module does not itself subscribe to
Meta webhooks or fetch DMs.
"""
import os
from datetime import datetime, timedelta, timezone
from typing import Literal

import psycopg
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from psycopg.rows import dict_row

router = APIRouter()
MEMORY_TTL = timedelta(hours=12)
MEMORY_TTL_HOURS = 12
MAX_MESSAGES_PER_CONVERSATION = 30


def _connect():
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError("DATABASE_URL is not configured.")
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    return psycopg.connect(url, row_factory=dict_row, connect_timeout=10)


def _require_nova_key(x_nova_api_key: str | None = Header(default=None, alias="X-NOVA-API-Key")):
    expected = os.getenv("NOVA_API_KEY", "")
    if not expected or not x_nova_api_key or x_nova_api_key != expected:
        raise HTTPException(status_code=401, detail="A valid X-NOVA-API-Key is required.")


def store_dm_message(recipient_id: str, role: str, message: str) -> datetime:
    """Internal helper for trusted webhook ingestion; returns the expiry time."""
    if role not in ("user", "assistant"):
        raise ValueError("role must be user or assistant")
    if not recipient_id or len(recipient_id) > 128 or not all(ch.isalnum() or ch in "_.:-" for ch in recipient_id):
        raise ValueError("invalid recipient ID")
    if not message or len(message) > 4000:
        raise ValueError("message must contain 1–4000 characters")
    now = datetime.now(timezone.utc)
    with _connect() as conn:
        conn.execute("DELETE FROM nova_instagram_dm_memory WHERE expires_at <= %s", (now,))
        conn.execute(
            """INSERT INTO nova_instagram_dm_memory
               (recipient_id, role, message, created_at, expires_at)
               VALUES (%s, %s, %s, %s, %s)""",
            (recipient_id, role, message, now, now + MEMORY_TTL),
        )
    return now + MEMORY_TTL


class DMMemoryMessage(BaseModel):
    recipient_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.:-]+$")
    role: Literal["user", "assistant"]
    message: str = Field(min_length=1, max_length=4000)


@router.post("/instagram/dm-memory/messages", dependencies=[Depends(_require_nova_key)])
def remember_dm_message(body: DMMemoryMessage):
    """Store one conversation turn with a strict 12-hour expiry."""
    now = datetime.now(timezone.utc)
    try:
        with _connect() as conn:
            conn.execute("DELETE FROM nova_instagram_dm_memory WHERE expires_at <= %s", (now,))
            conn.execute(
                """
                INSERT INTO nova_instagram_dm_memory
                    (recipient_id, role, message, created_at, expires_at)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (body.recipient_id, body.role, body.message, now, now + MEMORY_TTL),
            )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except psycopg.Error:
        raise HTTPException(status_code=503, detail="DM memory storage is unavailable. Check PostgreSQL setup.")
    return {
        "stored": True,
        "expires_at": (now + MEMORY_TTL).isoformat(),
        "ttl_hours": MEMORY_TTL_HOURS,
        "message_sent_to_instagram": False,
    }


@router.get("/instagram/dm-memory/{recipient_id}", dependencies=[Depends(_require_nova_key)])
def get_dm_memory(recipient_id: str):
    """Return recent context only; expired messages are never included."""
    if not recipient_id or len(recipient_id) > 128 or not all(c.isalnum() or c in "_.:-" for c in recipient_id):
        raise HTTPException(status_code=422, detail="Invalid Instagram-scoped recipient ID.")
    now = datetime.now(timezone.utc)
    try:
        with _connect() as conn:
            conn.execute("DELETE FROM nova_instagram_dm_memory WHERE expires_at <= %s", (now,))
            rows = conn.execute(
                """
                SELECT role, message, created_at, expires_at
                FROM nova_instagram_dm_memory
                WHERE recipient_id = %s AND expires_at > %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (recipient_id, now, MAX_MESSAGES_PER_CONVERSATION),
            ).fetchall()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except psycopg.Error:
        raise HTTPException(status_code=503, detail="DM memory storage is unavailable. Check PostgreSQL setup.")
    rows = list(reversed(rows))
    return {
        "recipient_id": recipient_id,
        "messages": [
            {"role": row["role"], "message": row["message"],
             "created_at": row["created_at"].isoformat(),
             "expires_at": row["expires_at"].isoformat()}
            for row in rows
        ],
        "ttl_hours": MEMORY_TTL_HOURS,
        "automatic_dm_ingestion_enabled": False,
    }


@router.delete("/instagram/dm-memory/{recipient_id}", dependencies=[Depends(_require_nova_key)])
def clear_dm_memory(recipient_id: str):
    """Explicitly clear a conversation's stored context."""
    if not recipient_id or len(recipient_id) > 128 or not all(c.isalnum() or c in "_.:-" for c in recipient_id):
        raise HTTPException(status_code=422, detail="Invalid Instagram-scoped recipient ID.")
    try:
        with _connect() as conn:
            result = conn.execute(
                "DELETE FROM nova_instagram_dm_memory WHERE recipient_id = %s",
                (recipient_id,),
            )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except psycopg.Error:
        raise HTTPException(status_code=503, detail="DM memory storage is unavailable. Check PostgreSQL setup.")
    return {"cleared": True, "deleted_messages": result.rowcount}


def initialize_schema() -> None:
    """Create the memory table and expiry index as part of deployment migration."""
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS nova_instagram_dm_memory (
                id BIGSERIAL PRIMARY KEY,
                recipient_id TEXT NOT NULL,
                role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
                message TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL,
                expires_at TIMESTAMPTZ NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS nova_instagram_dm_memory_expiry_idx ON nova_instagram_dm_memory (expires_at)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS nova_instagram_dm_memory_recipient_idx ON nova_instagram_dm_memory (recipient_id, created_at)"
        )
