import hashlib
import hmac
import json
import time

import pytest
from fastapi.testclient import TestClient

import app.instagram_webhook as webhook
from app.main import app

client = TestClient(app)


class _FakeResponse:
    is_success = True
    status_code = 200


class _FakeAsyncClient:
    sent = []

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, **kwargs):
        self.sent.append((url, kwargs))
        return _FakeResponse()


def test_auto_reply_sends_only_when_explicitly_enabled(monkeypatch):
    secret = "test-app-secret"
    monkeypatch.setenv("META_APP_SECRET", secret)
    monkeypatch.setenv("INSTAGRAM_AUTO_DM_REPLIES_ENABLED", "true")
    monkeypatch.setenv("INSTAGRAM_ACCESS_TOKEN", "test-token")
    monkeypatch.setenv("INSTAGRAM_USER_ID", "ig-user-1")
    monkeypatch.setenv("AI_BASE_URL", "https://ai.example/v1")
    monkeypatch.setenv("AI_API_KEY", "ai-test")
    monkeypatch.setenv("AI_MODEL", "test-model")
    stored = []
    monkeypatch.setattr(webhook, "store_dm_message", lambda recipient, role, message: stored.append((recipient, role, message)))
    async def fake_generate(recipient_id, message):
        assert recipient_id == "12345"
        assert message == "Hi NOVA"
        return "Hello! How can I help?"
    monkeypatch.setattr(webhook, "generate_dm_reply", fake_generate)
    monkeypatch.setattr(webhook.httpx, "AsyncClient", _FakeAsyncClient)
    _FakeAsyncClient.sent = []

    payload = {
        "object": "instagram",
        "entry": [{"messaging": [{
            "timestamp": int(time.time() * 1000),
            "sender": {"id": "12345"},
            "recipient": {"id": "ig-user-1"},
            "message": {"mid": "mid.test.1", "text": "Hi NOVA"},
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
    assert response.json()["automatic_replies_sent"] == 1
    assert len(_FakeAsyncClient.sent) == 1
    assert stored == [
        ("12345", "user", "Hi NOVA"),
        ("12345", "assistant", "Hello! How can I help?"),
    ]
