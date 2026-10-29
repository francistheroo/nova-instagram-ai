"""Regression test: a replay of an already-claimed DM is not replied to twice."""
import hashlib
import hmac
import json
import time

from fastapi.testclient import TestClient

import app.instagram_webhook as webhook
from app.main import app

client = TestClient(app)


def test_duplicate_sent_message_is_skipped_without_regenerating_or_sending(monkeypatch):
    secret = "test-app-secret"
    monkeypatch.setenv("META_APP_SECRET", secret)
    monkeypatch.setenv("INSTAGRAM_AUTO_DM_REPLIES_ENABLED", "true")

    claims = []
    finishes = []
    monkeypatch.setattr(
        webhook, "claim_dm_event",
        lambda mid: claims.append(mid) or False,
    )
    monkeypatch.setattr(
        webhook, "finish_dm_event",
        lambda mid, status: finishes.append((mid, status)),
    )

    def should_not_store_or_generate(*args, **kwargs):
        raise AssertionError("duplicate event must be skipped before memory/AI work")

    monkeypatch.setattr(webhook, "store_dm_message", should_not_store_or_generate)

    async def should_not_generate(*args):
        raise AssertionError("duplicate event must not invoke the AI provider")

    monkeypatch.setattr(webhook, "generate_dm_reply", should_not_generate)

    payload = {
        "object": "instagram",
        "entry": [{"messaging": [{
            "timestamp": int(time.time() * 1000),
            "sender": {"id": "12345"},
            "recipient": {"id": "ig-user-1"},
            "message": {"mid": "mid.already-sent.1", "text": "Hi NOVA"},
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
    assert response.json()["automatic_replies_skipped"] == 1
    assert claims == ["mid.already-sent.1"]
    assert finishes == []
