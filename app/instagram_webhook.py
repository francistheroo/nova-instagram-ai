"""Verified Instagram Messaging webhook receiver.

Stores incoming text messages and can optionally auto-reply when explicitly enabled.
Configure the webhook URL and subscribed fields in Meta's developer dashboard.
"""
import hashlib
import hmac
import json
import os
from datetime import datetime, timezone

import httpx

from fastapi import APIRouter, Header, HTTPException, Query, Request, Response

from app.dm_memory import store_dm_message, generate_dm_reply
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
    """Verify Meta's signature and store supported incoming text DM events."""
    app_secret = _secret("META_APP_SECRET")
    raw_body = await request.body()
    expected = "sha256=" + hmac.new(app_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    if not x_hub_signature_256 or not hmac.compare_digest(x_hub_signature_256, expected):
        raise HTTPException(status_code=401, detail="Invalid webhook signature.")

    try:
        payload = json.loads(raw_body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(status_code=400, detail="Invalid JSON payload.")

    stored = 0
    sent = 0
    skipped = 0
    try:
        for entry in payload.get("entry", []) if isinstance(payload, dict) else []:
            events = entry.get("messaging", []) if isinstance(entry, dict) else []
            for event in events:
                if not isinstance(event, dict) or event.get("message", {}).get("is_echo"):
                    continue
                sender = event.get("sender", {})
                message = event.get("message", {})
                sender_id = sender.get("id") if isinstance(sender, dict) else None
                text = message.get("text") if isinstance(message, dict) else None
                if isinstance(sender_id, str) and isinstance(text, str) and text.strip():
                    store_dm_message(sender_id, "user", text.strip())
                    stored += 1

                    # Automatic replies are opt-in and remain off by default.
                    if os.getenv("INSTAGRAM_AUTO_DM_REPLIES_ENABLED", "false").lower() != "true":
                        skipped += 1
                        continue

                    # Only reply to recent, user-initiated messages in Meta's standard
                    # 24-hour messaging window. Never infer eligibility from memory TTL.
                    event_timestamp = event.get("timestamp")
                    if not isinstance(event_timestamp, (int, float)) or event_timestamp <= 0:
                        skipped += 1
                        continue
                    event_time = datetime.fromtimestamp(event_timestamp / 1000, tz=timezone.utc)
                    age_seconds = (datetime.now(timezone.utc) - event_time).total_seconds()
                    if age_seconds < -300 or age_seconds > 24 * 60 * 60:
                        skipped += 1
                        continue

                    try:
                        reply_text = (await generate_dm_reply(sender_id, text.strip())).strip()
                        if not reply_text:
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
                                    skipped += 1
                                    continue
                                token = stored_token["access_token"]
                                user_id = user_id or stored_token["instagram_user_id"]
                        if not token or not user_id:
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
                            sent += 1
                        else:
                            skipped += 1
                    except Exception:
                        # A failed reply does not fail webhook delivery; Meta retries
                        # could otherwise cause duplicate replies for the same event.
                        skipped += 1
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        # A 5xx lets Meta retry rather than acknowledging an event that wasn't saved.
        if exc.__class__.__module__.startswith("psycopg"):
            raise HTTPException(status_code=503, detail="DM memory storage is unavailable.")
        raise

    return {"received": True, "stored_text_messages": stored, "automatic_replies_sent": sent, "automatic_replies_skipped": skipped}
