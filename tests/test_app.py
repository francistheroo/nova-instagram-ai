import os

import pytest

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root_is_online():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["service"] == "NOVA Instagram AI"


def test_health_does_not_claim_instagram_is_connected(monkeypatch):
    for name in (
        "INSTAGRAM_ACCESS_TOKEN",
        "INSTAGRAM_USER_ID",
        "NOVA_API_KEY",
        "IMAGE_API_BASE_URL",
        "IMAGE_API_KEY",
        "IMAGE_MODEL",
        "CANVA_CLIENT_ID",
        "CANVA_CLIENT_SECRET",
    ):
        monkeypatch.delenv(name, raising=False)
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["instagram_configured"] is False
    assert payload["instagram_oauth_implemented"] is True
    assert payload["instagram_token_refresh_implemented"] is True
    assert payload["instagram_webhooks_implemented"] is True
    assert payload["canva_configured"] is False
    assert payload["canva_oauth_implemented"] is True
    assert payload["image_generation_configured"] is False


def test_preview_reply_uses_fallback_when_provider_not_configured(monkeypatch):
    monkeypatch.delenv("AI_BASE_URL", raising=False)
    monkeypatch.delenv("AI_API_KEY", raising=False)
    monkeypatch.delenv("AI_MODEL", raising=False)
    response = client.post("/preview-reply", json={"message": "Hi NOVA"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "fallback"
    assert payload["sent_to_instagram"] is False


def test_protected_media_route_rejects_missing_key(monkeypatch):
    monkeypatch.setenv("NOVA_API_KEY", "test-secret")
    response = client.get("/instagram/media")
    assert response.status_code == 401


def test_protected_media_route_requires_instagram_configuration(monkeypatch):
    monkeypatch.setenv("NOVA_API_KEY", "test-secret")
    monkeypatch.delenv("INSTAGRAM_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("INSTAGRAM_USER_ID", raising=False)
    response = client.get(
        "/instagram/media",
        headers={"X-NOVA-API-Key": "test-secret"},
    )
    assert response.status_code == 503
    assert "not connected" in response.json()["detail"]


def test_write_action_stays_disabled_by_default(monkeypatch):
    monkeypatch.setenv("NOVA_API_KEY", "test-secret")
    monkeypatch.delenv("INSTAGRAM_AUTOMATION_ENABLED", raising=False)
    response = client.post(
        "/instagram/comments/123/reply",
        headers={"X-NOVA-API-Key": "test-secret"},
        json={"message": "Thanks for commenting!"},
    )
    assert response.status_code == 403
    assert "disabled" in response.json()["detail"]



def test_verify_route_requires_api_key(monkeypatch):
    monkeypatch.setenv("NOVA_API_KEY", "test-secret")
    response = client.get("/instagram/verify")
    assert response.status_code == 401


def test_verify_route_returns_profile_from_meta(monkeypatch):
    import app.main as main_module

    monkeypatch.setenv("NOVA_API_KEY", "test-secret")
    monkeypatch.setenv("INSTAGRAM_ACCESS_TOKEN", "fake-token-for-test")
    monkeypatch.setenv("INSTAGRAM_USER_ID", "123456")

    async def fake_meta_request(method, path, *, params=None, data=None):
        assert method == "GET"
        assert path == "123456"
        assert params == {"fields": "id,username"}
        return {"id": "123456", "username": "nova_test"}

    monkeypatch.setattr(main_module, "meta_request", fake_meta_request)
    response = client.get("/instagram/verify", headers={"X-NOVA-API-Key": "test-secret"})
    assert response.status_code == 200
    assert response.json() == {"connected": True, "profile_id": "123456", "username": "nova_test"}


def test_verify_route_requires_key_configuration_before_calling_meta(monkeypatch):
    import app.main as main_module

    monkeypatch.delenv("NOVA_API_KEY", raising=False)

    async def should_not_call_meta(*args, **kwargs):
        pytest.fail("Meta must not be called when NOVA_API_KEY is not configured")

    monkeypatch.setattr(main_module, "meta_request", should_not_call_meta)
    response = client.get("/instagram/verify", headers={"X-NOVA-API-Key": "anything"})

    assert response.status_code == 503
    assert "NOVA_API_KEY" in response.json()["detail"]


@pytest.mark.parametrize(
    "profile",
    [None, [], {}, {"username": "profile-without-id"}, {"id": ""}],
)
def test_verify_route_rejects_malformed_meta_profile(monkeypatch, profile):
    import app.main as main_module

    monkeypatch.setenv("NOVA_API_KEY", "test-secret")
    monkeypatch.setenv("INSTAGRAM_ACCESS_TOKEN", "fake-token-for-test")
    monkeypatch.setenv("INSTAGRAM_USER_ID", "123456")

    async def fake_meta_request(method, path, *, params=None, data=None):
        assert method == "GET"
        assert path == "123456"
        return profile

    monkeypatch.setattr(main_module, "meta_request", fake_meta_request)
    response = client.get(
        "/instagram/verify",
        headers={"X-NOVA-API-Key": "test-secret"},
    )

    assert response.status_code == 502
    assert response.json()["detail"] == "Meta did not return a valid Instagram profile response."
    assert "fake-token-for-test" not in response.text
