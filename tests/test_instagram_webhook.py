import hashlib
import hmac
import json

from fastapi.testclient import TestClient

from app.main import app
import app.instagram_webhook as webhook

client = TestClient(app)


def _signature(secret: str, raw: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()


def test_webhook_verification_challenge(monkeypatch):
    monkeypatch.setenv("INSTAGRAM_WEBHOOK_VERIFY_TOKEN", "verify-me")
    response = client.get(
        "/webhooks/instagram",
        params={"hub.mode": "subscribe", "hub.verify_token": "verify-me", "hub.challenge": "12345"},
    )
    assert response.status_code == 200
    assert response.text == "12345"


def test_webhook_rejects_bad_signature(monkeypatch):
    monkeypatch.setenv("META_APP_SECRET", "test-app-secret")
    response = client.post(
        "/webhooks/instagram",
        content=b'{"entry":[]}',
        headers={"X-Hub-Signature-256": "sha256=bad"},
    )
    assert response.status_code == 401


def test_webhook_rejects_signed_malformed_json(monkeypatch):
    secret = "test-app-secret"
    monkeypatch.setenv("META_APP_SECRET", secret)
    raw = b'{"entry":'
    response = client.post(
        "/webhooks/instagram",
        content=raw,
        headers={"X-Hub-Signature-256": _signature(secret, raw)},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid JSON payload."


def test_webhook_storage_runtime_error_returns_service_unavailable(monkeypatch):
    secret = "test-app-secret"
    monkeypatch.setenv("META_APP_SECRET", secret)
    monkeypatch.setenv("INSTAGRAM_AUTO_DM_REPLIES_ENABLED", "false")

    def unavailable(*args, **kwargs):
        raise RuntimeError("DM memory storage is unavailable.")

    monkeypatch.setattr(webhook, "store_dm_message", unavailable)
    raw = json.dumps({
        "object": "instagram",
        "entry": [{
            "messaging": [{
                "sender": {"id": "12345"},
                "message": {"mid": "test-mid-storage-error", "text": "Hello NOVA"},
            }]
        }],
    }).encode()
    response = client.post(
        "/webhooks/instagram",
        content=raw,
        headers={"X-Hub-Signature-256": _signature(secret, raw), "Content-Type": "application/json"},
    )
    assert response.status_code == 503
    assert response.json()["detail"] == "DM memory storage is unavailable."


def test_webhook_stores_signed_incoming_text_only(monkeypatch):
    app_secret = "test-app-secret"
    monkeypatch.setenv("META_APP_SECRET", app_secret)
    stored = []
    monkeypatch.setattr(webhook, "store_dm_message", lambda recipient, role, message, message_id=None: (stored.append((recipient, role, message, message_id)), "stored")[1])
    payload = {
        "object": "instagram",
        "entry": [{
            "messaging": [
                {"sender": {"id": "12345"}, "message": {"text": "Hello NOVA"}},
                {"sender": {"id": "12345"}, "message": {"text": "Echo ignored", "is_echo": True}},
                {"sender": {"id": "12345"}, "message": {"attachments": [{"type": "image"}]}},
            ]
        }]
    }
    raw = json.dumps(payload).encode()
    signature = _signature(app_secret, raw)
    response = client.post(
        "/webhooks/instagram",
        content=raw,
        headers={"X-Hub-Signature-256": signature, "Content-Type": "application/json"},
    )
    assert response.status_code == 200
    assert response.json()["stored_text_messages"] == 1
    assert stored == [("12345", "user", "Hello NOVA", None)]
    assert response.json()["automatic_replies_sent"] == 0
