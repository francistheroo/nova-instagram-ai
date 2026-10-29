"""Regression tests for rejecting unsigned or incorrectly signed webhook payloads."""
import json

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_invalid_instagram_webhook_signature_is_rejected(monkeypatch):
    monkeypatch.setenv("META_APP_SECRET", "test-app-secret")
    payload = {"object": "instagram", "entry": []}

    response = client.post(
        "/webhooks/instagram",
        content=json.dumps(payload).encode(),
        headers={
            "X-Hub-Signature-256": "sha256=not-a-valid-signature",
            "Content-Type": "application/json",
        },
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid webhook signature."
