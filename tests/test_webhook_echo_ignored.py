"""Regression test: Instagram echo events must not be stored as inbound messages."""
import hashlib
import hmac
import json

from fastapi.testclient import TestClient

import app.instagram_webhook as webhook
from app.main import app

client = TestClient(app)


def test_echo_message_is_ignored_without_storage_or_ai(monkeypatch):
    secret = "test-app-secret"
    monkeypatch.setenv("META_APP_SECRET", secret)
    monkeypatch.setenv("INSTAGRAM_AUTO_DM_REPLIES_ENABLED", "true")

    def should_not_store(*args, **kwargs):
        raise AssertionError("echo messages must not be stored as inbound messages")

    async def should_not_generate(*args):
        raise AssertionError("echo messages must not trigger AI replies")

    monkeypatch.setattr(webhook, "store_dm_message", should_not_store)
    monkeypatch.setattr(webhook, "generate_dm_reply", should_not_generate)

    payload = {
        "object": "instagram",
        "entry": [{"messaging": [{
            "sender": {"id": "ig-user-1"},
            "recipient": {"id": "12345"},
            "message": {
                "mid": "mid.echo.regression.1",
                "text": "Previously sent reply",
                "is_echo": True,
            },
        }]}],
    }
    raw = json.dumps(payload).encode()
    signature = "sha256=" + hmac.new(
        secret.encode(), raw, hashlib.sha256
    ).hexdigest()

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
    assert response.json()["automatic_replies_skipped"] == 0
