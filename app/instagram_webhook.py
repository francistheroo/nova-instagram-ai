"""Verified Instagram Messaging webhook receiver.

Only stores incoming text messages. It does not generate or send replies.
Configure the webhook URL and subscribed fields in Meta's developer dashboard.
"""
import hashlib
import hmac
import json
import os

from fastapi import APIRouter, Header, HTTPException, Query, Request, Response

from app.dm_memory import store_dm_message

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
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        # A 5xx lets Meta retry rather than acknowledging an event that wasn't saved.
        if exc.__class__.__module__.startswith("psycopg"):
            raise HTTPException(status_code=503, detail="DM memory storage is unavailable.")
        raise

    return {"received": True, "stored_text_messages": stored, "automatic_replies_sent": 0}
