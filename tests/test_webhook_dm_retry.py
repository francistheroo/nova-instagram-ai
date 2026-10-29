import hashlib
import hmac
import json
import time

from fastapi.testclient import TestClient

import app.instagram_webhook as webhook
from app.main import app

client = TestClient(app)


def signed_payload(secret, message_id="mid.retry.1"):
    payload = {
        "object": "instagram",
        "entry": [{"messaging": [{
            "timestamp": int(time.time() * 1000),
            "sender": {"id": "12345"},
            "recipient": {"id": "ig-user-1"},
            "message": {"mid": message_id, "text": "Hi NOVA"},
        }]}],
    }
    raw = json.dumps(payload).encode()
    signature = "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    return raw, signature


def post_event(secret):
    raw, signature = signed_payload(secret)
    return client.post(
        "/webhooks/instagram",
        content=raw,
        headers={"X-Hub-Signature-256": signature, "Content-Type": "application/json"},
    )


def test_ai_failure_can_retry_even_when_user_message_was_already_stored(monkeypatch):
    secret = "test-app-secret"
    monkeypatch.setenv("META_APP_SECRET", secret)
    monkeypatch.setenv("INSTAGRAM_AUTO_DM_REPLIES_ENABLED", "true")
    monkeypatch.setenv("INSTAGRAM_ACCESS_TOKEN", "test-token")
    monkeypatch.setenv("INSTAGRAM_USER_ID", "ig-user-1")

    claims = []
    finishes = []
    store_calls = []
    generation_count = {"value": 0}

    monkeypatch.setattr(webhook, "claim_dm_event", lambda mid: claims.append(mid) or True)

    def store(recipient_id, role, message, message_id=None):
        store_calls.append((recipient_id, role, message, message_id))
        # The retry sees the existing user message in memory, but must still retry.
        if role == "user" and len([x for x in store_calls if x[1] == "user"]) == 2:
            return None
        return "stored"

    monkeypatch.setattr(webhook, "store_dm_message", store)
    monkeypatch.setattr(webhook, "finish_dm_event", lambda mid, status: finishes.append((mid, status)))

    async def generate(*args):
        generation_count["value"] += 1
        if generation_count["value"] == 1:
            raise RuntimeError("temporary AI failure")
        return "Hello! How can I help?"

    monkeypatch.setattr(webhook, "generate_dm_reply", generate)

    class Response:
        is_success = True

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, *args, **kwargs):
            return Response()

    monkeypatch.setattr(webhook.httpx, "AsyncClient", lambda **kwargs: FakeClient())

    first = post_event(secret)
    second = post_event(secret)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["automatic_replies_sent"] == 0
    assert second.json()["automatic_replies_sent"] == 1
    assert finishes == [
        ("mid.retry.1", "retryable"),
        ("mid.retry.1", "sent"),
    ]
    assert len(claims) == 2



def test_meta_send_failure_can_retry_same_message(monkeypatch):
    secret = "test-app-secret"
    monkeypatch.setenv("META_APP_SECRET", secret)
    monkeypatch.setenv("INSTAGRAM_AUTO_DM_REPLIES_ENABLED", "true")
    monkeypatch.setenv("INSTAGRAM_ACCESS_TOKEN", "test-token")
    monkeypatch.setenv("INSTAGRAM_USER_ID", "ig-user-1")

    finishes = []
    user_store_count = {"value": 0}
    monkeypatch.setattr(webhook, "claim_dm_event", lambda mid: True)
    monkeypatch.setattr(
        webhook, "finish_dm_event",
        lambda mid, status: finishes.append((mid, status)),
    )

    def store(recipient_id, role, message, message_id=None):
        if role == "user":
            user_store_count["value"] += 1
            # The same inbound message is already in memory on the retry.
            if user_store_count["value"] == 2:
                return None
        return "stored"

    monkeypatch.setattr(webhook, "store_dm_message", store)

    async def generate(*args):
        return "Hello! How can I help?"

    monkeypatch.setattr(webhook, "generate_dm_reply", generate)

    class Response:
        def __init__(self, is_success):
            self.is_success = is_success

    class FakeClient:
        def __init__(self):
            self.responses = [Response(False), Response(True)]

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, *args, **kwargs):
            return self.responses.pop(0)

    fake_client = FakeClient()
    monkeypatch.setattr(webhook.httpx, "AsyncClient", lambda **kwargs: fake_client)

    first = post_event(secret)
    second = post_event(secret)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["automatic_replies_sent"] == 0
    assert second.json()["automatic_replies_sent"] == 1
    assert finishes == [
        ("mid.retry.1", "retryable"),
        ("mid.retry.1", "sent"),
    ]
