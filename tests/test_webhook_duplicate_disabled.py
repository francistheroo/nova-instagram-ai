"""Regression coverage for duplicate webhook deliveries when replies are off."""
import hashlib
import hmac
import json

from fastapi.testclient import TestClient

import app.instagram_webhook as webhook
from app.main import app

client = TestClient(app)


def test_duplicate_inbound_message_is_not_processed_twice_when_auto_replies_disabled(monkeypatch):
    secret = "test-app-secret"
    monkeypatch.setenv("META_APP_SECRET", secret)
    monkeypatch.setenv("INSTAGRAM_AUTO_DM_REPLIES_ENABLED", "false")

    stored_attempts = []
    def duplicate_store(recipient_id, role, message, message_id=None):
        stored_attempts.append((recipient_id, role, message, message_id))
        return None  # The unique message_id already exists in memory.

    async def should_not_generate(*args):
        raise AssertionError("duplicate webhook deliveries must not invoke AI")

    monkeypatch.setattr(webhook, "store_dm_message", duplicate_store)
    monkeypatch.setattr(webhook, "generate_dm_reply", should_not_generate)

    payload = {
        "object": "instagram",
        "entry": [{"messaging": [{
            "timestamp": 1_798_000_000_000,
            "sender": {"id": "12345"},
            "recipient": {"id": "ig-user-1"},
            "message": {"mid": "mid.duplicate.disabled.1", "text": "Hello NOVA"},
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
    assert response.json()["stored_text_messages"] == 0
    assert response.json()["automatic_replies_sent"] == 0
    assert response.json()["automatic_replies_skipped"] == 1
    assert stored_attempts == [("12345", "user", "Hello NOVA", "mid.duplicate.disabled.1")]
