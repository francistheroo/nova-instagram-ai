from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_reports_webhook_implementation_without_claiming_live_connection(monkeypatch):
    for key in (
        "INSTAGRAM_ACCESS_TOKEN",
        "INSTAGRAM_USER_ID",
        "INSTAGRAM_AUTOMATION_ENABLED",
        "AI_BASE_URL",
        "AI_API_KEY",
        "AI_MODEL",
        "IMAGE_API_BASE_URL",
        "IMAGE_API_KEY",
        "IMAGE_MODEL",
        "CANVA_CLIENT_ID",
        "CANVA_CLIENT_SECRET",
    ):
        monkeypatch.delenv(key, raising=False)

    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["instagram_webhooks_implemented"] is True
    assert payload["instagram_configured"] is False
    assert payload["instagram_automation_enabled"] is False
    assert payload["status"] == "ok"


def test_health_does_not_expose_configured_secret_values(monkeypatch):
    monkeypatch.setenv("INSTAGRAM_ACCESS_TOKEN", "private-instagram-token")
    monkeypatch.setenv("INSTAGRAM_USER_ID", "test-account-id")
    monkeypatch.setenv("INSTAGRAM_AUTOMATION_ENABLED", "false")

    response = client.get("/health")

    assert response.status_code == 200
    assert "private-instagram-token" not in response.text
    assert "test-account-id" not in response.text
