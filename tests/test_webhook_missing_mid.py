"""Regression coverage for messages without stable Meta IDs."""
import hashlib
import hmac
import json
import time

from fastapi.testclient import TestClient

import app.instagram_webhook as webhook
from app.main import app

client = TestClient(app)


def test_message_without_meta_mid_is_stored_but_never_auto_replied_to(monkeypatch):
    secret = "test-app-secret"
    monkeypatch.setenv("META_APP_SECRET", secret)
    monkeypatch.setenv("INSTAGRAM_AUTO_DM_REPLIES_ENABLED", "true")

    stored = []
    monkeypatch.setattr(
        webhook, "store_dm_message",
        lambda recipient, role, message, message_id=None: (
            stored.append((recipient, role, message, message_id)) or "stored"
        ),
    )

    async def should_not_generate(*args):
        raise AssertionError("messages without a stable Meta ID must not trigger auto-replies")

    monkeypatch.setattr(webhook, "generate_dm_reply", should_not_generate)

    payload = {
        "object": "instagram",
        "entry": [{"messaging": [{
            "timestamp": int(time.time() * 1000),
            "sender": {"id": "12345"},
            "recipient": {"id": "ig-user-1"},
            "message": {"text": "Hello NOVA"},
        }]}],
    }
    raw = json.dumps(payload).encode()
    signature = "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()

    response = client.post(
        "/webhooks/instagram",
        content=raw,
        headers={
            "X-Hub-Signature-256": signature,
            "Content-Type": "application/json",
        },
    )

    assert response.status_code == 200
    assert response.json()["stored_text_messages"] == 1
    assert response.json()["automatic_replies_sent"] == 0
    assert response.json()["automatic_replies_skipped"] == 1
    assert stored == [("12345", "user", "Hello NOVA", None)]
