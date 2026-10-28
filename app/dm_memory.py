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
import httpx
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from psycopg.rows import dict_row

from app.personality import NOVA_SYSTEM_PROMPT

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


def store_dm_message(recipient_id: str, role: str, message: str, message_id: str | None = None) -> datetime | None:
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
        if message_id is not None:
            result = conn.execute(
                """INSERT INTO nova_instagram_dm_memory
                   (recipient_id, role, message, created_at, expires_at, message_id)
                   VALUES (%s, %s, %s, %s, %s, %s)
                   ON CONFLICT (message_id) WHERE message_id IS NOT NULL DO NOTHING
                   RETURNING id""",
                (recipient_id, role, message, now, now + MEMORY_TTL, message_id),
            )
            if result.fetchone() is None:
                return None
        else:
            conn.execute(
                """INSERT INTO nova_instagram_dm_memory
                   (recipient_id, role, message, created_at, expires_at)
                   VALUES (%s, %s, %s, %s, %s)""",
                (recipient_id, role, message, now, now + MEMORY_TTL),
            )
    return now + MEMORY_TTL


async def generate_dm_reply(recipient_id: str, current_message: str) -> str:
    """Generate a reply using unexpired stored history; caller decides whether to send."""
    now = datetime.now(timezone.utc)
    with _connect() as conn:
        conn.execute("DELETE FROM nova_instagram_dm_memory WHERE expires_at <= %s", (now,))
        rows = conn.execute(
            """SELECT role, message FROM nova_instagram_dm_memory
               WHERE recipient_id = %s AND expires_at > %s
               ORDER BY created_at DESC LIMIT %s""",
            (recipient_id, now, MAX_MESSAGES_PER_CONVERSATION),
        ).fetchall()
    base_url = os.getenv("AI_BASE_URL", "").rstrip("/")
    api_key = os.getenv("AI_API_KEY", "")
    model = os.getenv("AI_MODEL", "")
    if not (base_url and api_key and model):
        raise RuntimeError("AI text provider is not configured.")
    history = list(reversed(rows))
    messages = [{"role": "system", "content": NOVA_SYSTEM_PROMPT}]
    for row in history:
        messages.append({"role": row["role"], "content": row["message"]})
    if not history or history[-1]["role"] != "user" or history[-1]["message"] != current_message:
        messages.append({"role": "user", "content": current_message})
    async with httpx.AsyncClient(timeout=45.0) as client:
        response = await client.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"model": model, "messages": messages, "temperature": 0.8},
        )
    if response.is_error:
        raise RuntimeError("AI provider rejected the reply request.")
    return response.json()["choices"][0]["message"]["content"]


class DMReplyPreviewRequest(BaseModel):
    recipient_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.:-]+$")
    message: str = Field(min_length=1, max_length=4000)
    language_hint: str | None = Field(default=None, max_length=30)


@router.post("/instagram/dm-memory/preview-reply", dependencies=[Depends(_require_nova_key)])
async def preview_dm_reply(body: DMReplyPreviewRequest):
    """Generate a review-only reply draft using the last 12 hours of stored context."""
    now = datetime.now(timezone.utc)
    try:
        with _connect() as conn:
            conn.execute("DELETE FROM nova_instagram_dm_memory WHERE expires_at <= %s", (now,))
            rows = conn.execute(
                """SELECT role, message FROM nova_instagram_dm_memory
                   WHERE recipient_id = %s AND expires_at > %s
                   ORDER BY created_at DESC LIMIT %s""",
                (body.recipient_id, now, MAX_MESSAGES_PER_CONVERSATION),
            ).fetchall()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except psycopg.Error:
        raise HTTPException(status_code=503, detail="DM memory storage is unavailable. Check PostgreSQL setup.")

    base_url = os.getenv("AI_BASE_URL", "").rstrip("/")
    api_key = os.getenv("AI_API_KEY", "")
    model = os.getenv("AI_MODEL", "")
    if not (base_url and api_key and model):
        raise HTTPException(status_code=503, detail="AI provider is not configured.")
    history = list(reversed(rows))
    messages = [{"role": "system", "content": NOVA_SYSTEM_PROMPT}]
    for row in history:
        messages.append({"role": row["role"], "content": row["message"]})
    # Add the current message only if webhook ingestion hasn't already stored it.
    if not history or history[-1]["role"] != "user" or history[-1]["message"] != body.message:
        messages.append({"role": "user", "content": body.message})
    if body.language_hint:
        messages.append({"role": "system", "content": f"Language preference hint: {body.language_hint}"})

    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post(
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={"model": model, "messages": messages, "temperature": 0.8},
            )
        if response.is_error:
            raise HTTPException(status_code=502, detail="AI provider request failed.")
        data = response.json()
        reply = data["choices"][0]["message"]["content"]
    except HTTPException:
        raise
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError):
        raise HTTPException(status_code=502, detail="Could not generate a reply draft from the AI provider.")
    return {
        "reply": reply,
        "draft_only": True,
        "sent_to_instagram": False,
        "context_messages_used": len(history),
        "memory_ttl_hours": MEMORY_TTL_HOURS,
        "review_required": True,
    }


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



DM_EVENT_LEASE = timedelta(minutes=2)


def claim_dm_event(message_id: str) -> bool:
    """Atomically claim a webhook message for reply processing.

    A fresh event can be claimed once. Retryable events and abandoned processing
    leases can be reclaimed; already-sent events cannot.
    """
    if not message_id or len(message_id) > 512:
        raise ValueError("invalid Meta message ID")
    now = datetime.now(timezone.utc)
    lease_until = now + DM_EVENT_LEASE
    with _connect() as conn:
        result = conn.execute(
            """
            INSERT INTO nova_instagram_dm_events
                (message_id, status, lease_until, updated_at)
            VALUES (%s, 'processing', %s, %s)
            ON CONFLICT (message_id) DO UPDATE
                SET status = 'processing', lease_until = EXCLUDED.lease_until,
                    updated_at = EXCLUDED.updated_at
                WHERE nova_instagram_dm_events.status = 'retryable'
                   OR (nova_instagram_dm_events.status = 'processing'
                       AND nova_instagram_dm_events.lease_until <= %s)
            RETURNING message_id
            """,
            (message_id, lease_until, now, now),
        )
        return result.fetchone() is not None


def finish_dm_event(message_id: str, status: Literal["sent", "retryable"]) -> None:
    """Record a reply outcome; retryable failures may be claimed again."""
    if status not in ("sent", "retryable"):
        raise ValueError("status must be sent or retryable")
    now = datetime.now(timezone.utc)
    with _connect() as conn:
        result = conn.execute(
            """
            UPDATE nova_instagram_dm_events
               SET status = %s, lease_until = NULL, updated_at = %s
             WHERE message_id = %s AND status = 'processing'
            RETURNING message_id
            """,
            (status, now, message_id),
        )
        if result.fetchone() is None:
            raise RuntimeError("DM event was not in processing state")

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
                expires_at TIMESTAMPTZ NOT NULL,
                message_id TEXT
            )
            """
        )
        conn.execute("ALTER TABLE nova_instagram_dm_memory ADD COLUMN IF NOT EXISTS message_id TEXT")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS nova_instagram_dm_events (
                message_id TEXT PRIMARY KEY,
                status TEXT NOT NULL CHECK (status IN ('processing', 'sent', 'retryable')),
                lease_until TIMESTAMPTZ,
                updated_at TIMESTAMPTZ NOT NULL
            )
            """
        )
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS nova_instagram_dm_memory_message_id_idx ON nova_instagram_dm_memory (message_id) WHERE message_id IS NOT NULL")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS nova_instagram_dm_memory_expiry_idx ON nova_instagram_dm_memory (expires_at)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS nova_instagram_dm_memory_recipient_idx ON nova_instagram_dm_memory (recipient_id, created_at)"
        )
