"""Verified Instagram Messaging webhook receiver.

Stores incoming text messages and optionally replies when explicitly enabled.
Retry state is database-backed when Meta supplies a stable message ID.
"""
import hashlib
import hmac
import json
import os
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Header, HTTPException, Query, Request, Response

from app.dm_memory import (
    claim_dm_event,
    finish_dm_event,
    generate_dm_reply,
    store_dm_message,
)
from app.oauth_store import load_latest_instagram_token

router = APIRouter(prefix="/webhooks/instagram", tags=["Instagram webhook"])


def _secret(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise HTTPException(status_code=503, detail=f"{name} is not configured.")
    return value


@router.get("")
async def verify_instagram_webhook(
    mode: str | None = Query(default=None, alias="hub.mode"),
    verify_token: str | None = Query(default=None, alias="hub.verify_token"),
    challenge: str | None = Query(default=None, alias="hub.challenge"),
):
    """Handle Meta's initial webhook subscription challenge."""
    expected = _secret("INSTAGRAM_WEBHOOK_VERIFY_TOKEN")
    if mode == "subscribe" and verify_token and hmac.compare_digest(verify_token, expected) and challenge:
        return Response(content=challenge, media_type="text/plain")
    raise HTTPException(status_code=403, detail="Webhook verification failed.")


@router.post("")
async def receive_instagram_webhook(
    request: Request,
    x_hub_signature_256: str | None = Header(default=None, alias="X-Hub-Signature-256"),
):
    """Verify Meta's signature and process supported incoming text DM events."""
    app_secret = _secret("META_APP_SECRET")
    raw_body = await request.body()
    expected = "sha256=" + hmac.new(app_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    if not x_hub_signature_256 or not hmac.compare_digest(x_hub_signature_256, expected):
        raise HTTPException(status_code=401, detail="Invalid webhook signature.")

    try:
        payload = json.loads(raw_body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(status_code=400, detail="Invalid JSON payload.")

    stored = sent = skipped = 0
    retry_requested = False
    auto_enabled = os.getenv("INSTAGRAM_AUTO_DM_REPLIES_ENABLED", "false").lower() == "true"
    try:
        entries = payload.get("entry", []) if isinstance(payload, dict) else []
        if not isinstance(entries, list):
            entries = []
        for entry in entries:
            events = entry.get("messaging", []) if isinstance(entry, dict) else []
            if not isinstance(events, list):
                events = []
            for event in events:
                if not isinstance(event, dict):
                    continue
                sender = event.get("sender", {})
                message = event.get("message", {})
                if not isinstance(message, dict) or message.get("is_echo"):
                    continue
                sender_id = sender.get("id") if isinstance(sender, dict) else None
                text = message.get("text")
                raw_mid = message.get("mid")
                message_id = raw_mid if isinstance(raw_mid, str) and 0 < len(raw_mid) <= 512 else None
                if not (isinstance(sender_id, str) and sender_id.strip() and isinstance(text, str) and text.strip()):
                    continue

                # A stable Meta message ID is required for safe retry claims. Without
                # one, store the message but don't automatically reply to it.
                event_claimed = False
                if auto_enabled and message_id:
                    event_claimed = claim_dm_event(message_id)
                    if not event_claimed:
                        skipped += 1
                        continue

                try:
                    stored_until = store_dm_message(
                        sender_id, "user", text.strip(), message_id=message_id
                    )
                except Exception:
                    # Ask Meta to redeliver failed storage work instead of
                    # acknowledging the delivery as successfully processed.
                    if event_claimed and message_id:
                        try:
                            finish_dm_event(message_id, "retryable")
                        except Exception:
                            pass
                    retry_requested = True
                    skipped += 1
                    continue
                if stored_until is None and not event_claimed:
                    # Already stored and not claimed for retry: duplicate delivery.
                    skipped += 1
                    continue
                if stored_until is not None:
                    stored += 1

                if not auto_enabled:
                    skipped += 1
                    continue
                if not event_claimed:
                    skipped += 1
                    continue

                # The event is terminally ignored when it cannot qualify for the
                # standard 24-hour messaging window. Never infer eligibility from
                # the 12-hour memory TTL.
                event_timestamp = event.get("timestamp")
                if not isinstance(event_timestamp, (int, float)) or event_timestamp <= 0:
                    finish_dm_event(message_id, "ignored")
                    skipped += 1
                    continue
                try:
                    event_time = datetime.fromtimestamp(event_timestamp / 1000, tz=timezone.utc)
                except (OverflowError, OSError, ValueError):
                    finish_dm_event(message_id, "ignored")
                    skipped += 1
                    continue
                age_seconds = (datetime.now(timezone.utc) - event_time).total_seconds()
                if age_seconds < -300 or age_seconds > 24 * 60 * 60:
                    finish_dm_event(message_id, "ignored")
                    skipped += 1
                    continue

                try:
                    reply_text = (await generate_dm_reply(sender_id, text.strip())).strip()
                    if not reply_text:
                        finish_dm_event(message_id, "retryable")
                        retry_requested = True
                        skipped += 1
                        continue

                    manual_token = os.getenv("INSTAGRAM_ACCESS_TOKEN", "").strip()
                    user_id = os.getenv("INSTAGRAM_USER_ID", "").strip()
                    token = manual_token
                    if not token:
                        stored_token = load_latest_instagram_token()
                        if stored_token:
                            expiry = stored_token.get("expires_at")
                            if expiry is not None and expiry <= datetime.now(timezone.utc):
                                finish_dm_event(message_id, "retryable")
                                retry_requested = True
                                skipped += 1
                                continue
                            token = stored_token["access_token"]
                            user_id = user_id or stored_token["instagram_user_id"]
                    if not token or not user_id:
                        finish_dm_event(message_id, "retryable")
                        retry_requested = True
                        skipped += 1
                        continue

                    graph_base = os.getenv("META_GRAPH_BASE_URL", "https://graph.instagram.com").rstrip("/")
                    version = os.getenv("META_API_VERSION", "v25.0").strip("/")
                    async with httpx.AsyncClient(timeout=30.0) as client:
                        response = await client.post(
                            f"{graph_base}/{version}/{user_id}/messages",
                            headers={"Authorization": f"Bearer {token}"},
                            data={
                                "recipient": json.dumps({"id": sender_id}),
                                "message": json.dumps({"text": reply_text}),
                            },
                        )
                    if response.is_success:
                        store_dm_message(sender_id, "assistant", reply_text)
                        finish_dm_event(message_id, "sent")
                        sent += 1
                    else:
                        finish_dm_event(message_id, "retryable")
                        retry_requested = True
                        skipped += 1
                except Exception:
                    # A non-2xx response lets Meta retry this delivery. A timeout
                    # after Meta accepts a send can still cause a duplicate; the
                    # public API offers no general idempotency key for this send.
                    finish_dm_event(message_id, "retryable")
                    retry_requested = True
                    skipped += 1
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        if exc.__class__.__module__.startswith("psycopg"):
            raise HTTPException(status_code=503, detail="DM memory storage is unavailable.")
        raise

    if retry_requested:
        raise HTTPException(
            status_code=503,
            detail="One or more Instagram DM events are retryable; please retry this webhook delivery.",
        )

    return {
        "received": True,
        "stored_text_messages": stored,
        "automatic_replies_sent": sent,
        "automatic_replies_skipped": skipped,
    }
