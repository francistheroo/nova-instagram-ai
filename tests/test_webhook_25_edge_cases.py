"""Batch of 25 malformed/unsupported Instagram webhook event regression cases."""
import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient

import app.instagram_webhook as webhook
from app.main import app



@pytest.mark.parametrize(
    "event",
    [
        None,
        False,
        True,
        0,
        1,
        1.5,
        "",
        "event",
        [],
        ["nested"],
        {},
        {"message": None},
        {"message": []},
        {"message": "text"},
        {"sender": None, "message": {"text": "hello"}},
        {"sender": [], "message": {"text": "hello"}},
        {"sender": "123", "message": {"text": "hello"}},
        {"sender": {"id": None}, "message": {"text": "hello"}},
        {"sender": {"id": ""}, "message": {"text": "hello"}},
        {"sender": {"id": "123"}, "message": None},
        {"sender": {"id": "123"}, "message": []},
        {"sender": {"id": "123"}, "message": {"text": None}},
        {"sender": {"id": "123"}, "message": {"text": ""}},
        {"sender": {"id": "123"}, "message": {"text": "echo", "is_echo": True}},
        {"sender": {"id": "123"}, "message": {"text": "echo", "is_echo": 1}},
    ],
)
def test_webhook_skips_25_unsupported_event_shapes_without_side_effects(monkeypatch, event):
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

    with TestClient(app) as client:
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
