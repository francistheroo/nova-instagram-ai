from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_integrations_status_is_safe_and_explicit(monkeypatch):
    for key in (
        "NOVA_API_KEY", "DATABASE_URL", "INSTAGRAM_ACCESS_TOKEN", "INSTAGRAM_USER_ID",
        "INSTAGRAM_OAUTH_CLIENT_ID", "INSTAGRAM_OAUTH_CLIENT_SECRET",
        "INSTAGRAM_OAUTH_REDIRECT_URI", "OAUTH_STATE_SECRET", "TOKEN_ENCRYPTION_KEY",
        "CANVA_CLIENT_ID", "CANVA_CLIENT_SECRET", "CANVA_REDIRECT_URI",
        "AI_BASE_URL", "AI_API_KEY", "AI_MODEL", "GEMINI_API_KEY", "GROQ_API_KEY", "HF_TOKEN",
        "IMAGE_API_BASE_URL", "IMAGE_API_KEY", "IMAGE_MODEL",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("INSTAGRAM_AUTOMATION_ENABLED", "false")

    response = client.get("/integrations/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["checks_are_configuration_only"] is True
    assert payload["live_account_verification"] == "not_performed"
    assert payload["nova_api_key_configured"] is False
    assert payload["database_configured"] is False
    assert payload["instagram"]["oauth_environment_ready"] is False
    assert payload["instagram"]["publishing_enabled"] is False
    assert payload["canva"]["oauth_environment_ready"] is False
    assert "do not prove" in payload["warning"]


def test_integrations_status_reports_presence_without_exposing_secrets(monkeypatch):
    monkeypatch.setenv("NOVA_API_KEY", "super-secret-test-value")
    monkeypatch.setenv("DATABASE_URL", "postgresql://private")
    monkeypatch.setenv("INSTAGRAM_ACCESS_TOKEN", "instagram-secret")
    monkeypatch.setenv("INSTAGRAM_USER_ID", "123")
    monkeypatch.setenv("INSTAGRAM_AUTOMATION_ENABLED", "false")

    response = client.get("/integrations/status")

    assert response.status_code == 200
    payload = response.json()
    serialized = response.text
    assert payload["nova_api_key_configured"] is True
    assert payload["database_configured"] is True
    assert payload["instagram"]["manual_credentials_present"] is True
    assert "super-secret-test-value" not in serialized
    assert "instagram-secret" not in serialized
    assert "postgresql://private" not in serialized
