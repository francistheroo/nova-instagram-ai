"""Ten regression cases for unsupported or malformed incoming DM events."""
import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient

import app.instagram_webhook as webhook
from app.main import app

client = TestClient(app)


@pytest.mark.parametrize(
    "event",
    [
        None,
        "not-an-event",
        {},
        {"message": "not-an-object"},
        {"sender": {"id": "123"}, "message": {"text": "echo", "is_echo": True}},
        {"sender": {}, "message": {"text": "missing sender id"}},
        {"sender": {"id": 123}, "message": {"text": "non-string sender id"}},
        {"sender": {"id": "123"}, "message": {}},
        {"sender": {"id": "123"}, "message": {"text": 123}},
        {"sender": {"id": "123"}, "message": {"text": "   "}},
    ],
)
def test_webhook_skips_unsupported_event_without_claiming_or_storing(monkeypatch, event):
    secret = "test-app-secret"
    monkeypatch.setenv("META_APP_SECRET", secret)
    monkeypatch.setenv("INSTAGRAM_AUTO_DM_REPLIES_ENABLED", "true")

    def unexpected(*args, **kwargs):
        pytest.fail("Unsupported event must not claim a retry slot or store a message")

    monkeypatch.setattr(webhook, "claim_dm_event", unexpected)
    monkeypatch.setattr(webhook, "store_dm_message", unexpected)

    raw = json.dumps({
        "object": "instagram",
        "entry": [{"messaging": [event]}],
    }).encode()
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
    assert response.json() == {
        "received": True,
        "stored_text_messages": 0,
        "automatic_replies_sent": 0,
        "automatic_replies_skipped": 0,
    }
