from fastapi.testclient import TestClient

from app.main import app
import pytest
import app.security as security


@pytest.fixture(autouse=True)
def allow_authenticated_admin_in_unit_tests():
    app.dependency_overrides[security.require_user] = lambda: True
    app.dependency_overrides[security.require_master_enabled] = lambda: True
    yield
    app.dependency_overrides.pop(security.require_user, None)
    app.dependency_overrides.pop(security.require_master_enabled, None)


client = TestClient(app)


def test_legacy_canva_photo_publish_is_permanently_disabled_even_when_all_flags_are_on(monkeypatch):
    monkeypatch.setenv("NOVA_API_KEY", "test-secret")
    monkeypatch.setenv("INSTAGRAM_AUTOMATION_ENABLED", "true")
    from app import canva_direct_post

    async def fail_if_called(*args, **kwargs):
        raise AssertionError("Legacy direct endpoint must never call Canva")

    monkeypatch.setattr(canva_direct_post, "_canva_request", fail_if_called)
    response = client.post(
        "/canva/instagram-posts/publish",
        headers={"X-NOVA-API-Key": "test-secret"},
        json={"design_id": "design_123", "caption": "Hello"},
    )
    assert response.status_code == 410
    assert response.json()["detail"]["review_required"] is True
    assert response.json()["detail"]["published"] is False


def test_legacy_canva_photo_publish_requires_admin_login(monkeypatch):
    app.dependency_overrides.pop(security.require_user, None)
    monkeypatch.setenv("NOVA_API_KEY", "test-secret")
    monkeypatch.setenv("NOVA_ADMIN_USERNAME", "nova-admin")
    monkeypatch.setenv("NOVA_ADMIN_PASSWORD", "test-admin-password")
    monkeypatch.setenv("INSTAGRAM_AUTOMATION_ENABLED", "true")

    response = client.post(
        "/canva/instagram-posts/publish",
        headers={"X-NOVA-API-Key": "test-secret"},
        json={"design_id": "design_123", "caption": "Hello"},
    )

    assert response.status_code == 401
