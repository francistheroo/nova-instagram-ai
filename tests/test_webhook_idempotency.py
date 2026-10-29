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
    monkeypatch.setattr(webhook, "claim_dm_event", lambda message_id: False)
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
    # A failed event claim means the duplicate is rejected before touching memory.
    assert stored_calls == []


def test_retryable_ai_failure_can_be_reclaimed_and_replied_to(monkeypatch):
    from datetime import datetime, timezone

    secret = "test-app-secret"
    monkeypatch.setenv("META_APP_SECRET", secret)
    monkeypatch.setenv("INSTAGRAM_AUTO_DM_REPLIES_ENABLED", "true")
    monkeypatch.setenv("INSTAGRAM_ACCESS_TOKEN", "test-token")
    monkeypatch.setenv("INSTAGRAM_USER_ID", "ig-user-1")

    claims = []
    finishes = []
    user_store_calls = []
    generation_calls = []

    def claim(message_id):
        claims.append(message_id)
        return True  # First delivery, then retryable redelivery is reclaimed.

    def finish(message_id, status):
        finishes.append((message_id, status))

    def store(recipient_id, role, message, message_id=None):
        if role == "user":
            user_store_calls.append(message_id)
            # The retry finds the user message already in short-lived memory.
            return datetime.now(timezone.utc) if len(user_store_calls) == 1 else None
        return datetime.now(timezone.utc)

    async def generate(recipient_id, current_message):
        generation_calls.append(current_message)
        if len(generation_calls) == 1:
            raise RuntimeError("temporary AI provider failure")
        return "Hello! How can I help?"

    class Response:
        is_success = True

    class FakeAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, *args, **kwargs):
            return Response()

    monkeypatch.setattr(webhook, "claim_dm_event", claim)
    monkeypatch.setattr(webhook, "finish_dm_event", finish)
    monkeypatch.setattr(webhook, "store_dm_message", store)
    monkeypatch.setattr(webhook, "generate_dm_reply", generate)
    monkeypatch.setattr(webhook.httpx, "AsyncClient", FakeAsyncClient)

    payload = {
        "object": "instagram",
        "entry": [{"messaging": [{
            "timestamp": int(time.time() * 1000),
            "sender": {"id": "12345"},
            "recipient": {"id": "ig-user-1"},
            "message": {"mid": "mid.retry.1", "text": "Hi NOVA"},
        }]}],
    }

    def deliver():
        raw = json.dumps(payload).encode()
        signature = "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
        return client.post(
            "/webhooks/instagram",
            content=raw,
            headers={"X-Hub-Signature-256": signature, "Content-Type": "application/json"},
        )

    first = deliver()
    assert first.status_code == 200
    assert first.json()["automatic_replies_sent"] == 0
    assert finishes == [("mid.retry.1", "retryable")]

    second = deliver()
    assert second.status_code == 200
    assert second.json()["automatic_replies_sent"] == 1
    assert claims == ["mid.retry.1", "mid.retry.1"]
    assert generation_calls == ["Hi NOVA", "Hi NOVA"]
    assert finishes == [("mid.retry.1", "retryable"), ("mid.retry.1", "sent")]
    assert user_store_calls == ["mid.retry.1", "mid.retry.1"]
