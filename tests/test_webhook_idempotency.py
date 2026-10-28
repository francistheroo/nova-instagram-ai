import hashlib
import hmac
import json
import time

from fastapi.testclient import TestClient

import app.instagram_webhook as webhook
from app.main import app

client = TestClient(app)


def test_duplicate_message_id_is_not_replied_to_twice(monkeypatch):
    secret = "test-app-secret"
    monkeypatch.setenv("META_APP_SECRET", secret)
    monkeypatch.setenv("INSTAGRAM_AUTO_DM_REPLIES_ENABLED", "true")
    stored_calls = []

    def duplicate_store(recipient_id, role, message, message_id=None):
        stored_calls.append((recipient_id, role, message, message_id))
        return None  # Existing unique message ID: duplicate delivery.

    async def should_not_generate(*args):
        raise AssertionError("duplicate webhook must not generate another reply")

    monkeypatch.setattr(webhook, "store_dm_message", duplicate_store)
    monkeypatch.setattr(webhook, "generate_dm_reply", should_not_generate)
    payload = {
        "object": "instagram",
        "entry": [{"messaging": [{
            "timestamp": int(time.time() * 1000),
            "sender": {"id": "12345"},
            "recipient": {"id": "ig-user-1"},
            "message": {"mid": "mid.duplicate.1", "text": "Hi NOVA"},
        }]}],
    }
    raw = json.dumps(payload).encode()
    signature = "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    response = client.post(
        "/webhooks/instagram",
        content=raw,
        headers={"X-Hub-Signature-256": signature, "Content-Type": "application/json"},
    )

    assert response.status_code == 200
    assert response.json()["stored_text_messages"] == 0
    assert response.json()["automatic_replies_sent"] == 0
    assert response.json()["automatic_replies_skipped"] == 1
    assert stored_calls == [("12345", "user", "Hi NOVA", "mid.duplicate.1")]
