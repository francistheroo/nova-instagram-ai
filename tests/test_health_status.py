from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_distinguishes_implementation_from_live_configuration(monkeypatch):
    for key in (
        "INSTAGRAM_ACCESS_TOKEN",
        "INSTAGRAM_USER_ID",
        "INSTAGRAM_AUTOMATION_ENABLED",
        "INSTAGRAM_AUTO_DM_REPLIES_ENABLED",
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
    assert payload["status"] == "ok"

    # The health route describes code paths and environment presence; it never
    # calls Meta or Canva and must not claim live account verification.
    assert payload["instagram_configured"] is False
    assert payload["instagram_manual_credentials_present"] is False
    assert payload["instagram_live_connection_verified"] is False
    assert payload["instagram_oauth_implemented"] is True
    assert payload["instagram_token_refresh_implemented"] is True
    assert payload["instagram_manual_token_refresh_implemented"] is True
    assert payload["instagram_automatic_token_refresh_implemented"] is True
    assert payload["instagram_automatic_token_refresh_enabled"] is False
    assert payload["instagram_automatic_token_refresh_running"] is False
    assert payload["instagram_automatic_token_refresh_error"] is None

    assert payload["instagram_webhooks_implemented"] is True
    assert payload["instagram_webhook_receiver_implemented"] is True
    assert payload["instagram_webhook_verification_route_implemented"] is True
    assert payload["instagram_webhook_subscription_automated"] is False
    assert payload["instagram_automation_enabled"] is False
    assert payload["instagram_auto_dm_replies_enabled"] is False

    assert payload["canva_configured"] is False
    assert payload["canva_live_connection_verified"] is False
    assert payload["canva_oauth_implemented"] is True
    assert payload["canva_manual_token_refresh_implemented"] is True
    assert payload["canva_automatic_token_refresh_implemented"] is False


def test_health_treats_whitespace_only_configuration_as_missing(monkeypatch):
    for key, value in (
        ("INSTAGRAM_ACCESS_TOKEN", "   "),
        ("INSTAGRAM_USER_ID", "\t"),
        ("AI_BASE_URL", " "),
        ("AI_API_KEY", "\n"),
        ("AI_MODEL", "  "),
        ("IMAGE_API_BASE_URL", " "),
        ("IMAGE_API_KEY", "\t"),
        ("IMAGE_MODEL", "\n"),
        ("CANVA_CLIENT_ID", " "),
        ("CANVA_CLIENT_SECRET", "\t"),
    ):
        monkeypatch.setenv(key, value)

    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["instagram_configured"] is False
    assert payload["instagram_manual_credentials_present"] is False
    assert payload["ai_configured"] is False
    assert payload["image_generation_configured"] is False
    assert payload["canva_configured"] is False


def test_health_reflects_opt_in_flags_without_sending_anything(monkeypatch):
    monkeypatch.setenv("INSTAGRAM_AUTOMATION_ENABLED", "true")
    monkeypatch.setenv("INSTAGRAM_AUTO_DM_REPLIES_ENABLED", "true")

    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["instagram_automation_enabled"] is True
    assert payload["instagram_auto_dm_replies_enabled"] is True


def test_health_does_not_expose_configured_secret_values(monkeypatch):
    monkeypatch.setenv("INSTAGRAM_ACCESS_TOKEN", "private-instagram-token")
    monkeypatch.setenv("INSTAGRAM_USER_ID", "test-account-id")
    monkeypatch.setenv("AI_API_KEY", "private-ai-key")
    monkeypatch.setenv("IMAGE_API_KEY", "private-image-key")
    monkeypatch.setenv("CANVA_CLIENT_SECRET", "private-canva-secret")

    response = client.get("/health")

    assert response.status_code == 200
    for secret in (
        "private-instagram-token",
        "test-account-id",
        "private-ai-key",
        "private-image-key",
        "private-canva-secret",
    ):
        assert secret not in response.text
