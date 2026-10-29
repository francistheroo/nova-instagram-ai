"""Regression coverage for stale Instagram DM webhook events."""
import hashlib
import hmac
import json
import time

from fastapi.testclient import TestClient

import app.instagram_webhook as webhook
from app.main import app

client = TestClient(app)


def test_out_of_window_message_is_ignored_without_ai_or_send(monkeypatch):
    secret = "test-app-secret"
    monkeypatch.setenv("META_APP_SECRET", secret)
    monkeypatch.setenv("INSTAGRAM_AUTO_DM_REPLIES_ENABLED", "true")

    finishes = []
    monkeypatch.setattr(webhook, "claim_dm_event", lambda mid: True)
    monkeypatch.setattr(
        webhook, "finish_dm_event",
        lambda mid, status: finishes.append((mid, status)),
    )
    monkeypatch.setattr(
        webhook, "store_dm_message",
        lambda *args, **kwargs: "stored",
    )

    async def should_not_generate(*args):
        raise AssertionError("out-of-window messages must not invoke the AI provider")

    monkeypatch.setattr(webhook, "generate_dm_reply", should_not_generate)

    payload = {
        "object": "instagram",
        "entry": [{"messaging": [{
            "timestamp": int((time.time() - 25 * 60 * 60) * 1000),
            "sender": {"id": "12345"},
            "recipient": {"id": "ig-user-1"},
            "message": {"mid": "mid.stale.1", "text": "Hi NOVA"},
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
    assert response.json()["automatic_replies_sent"] == 0
    assert finishes == [("mid.stale.1", "ignored")]
