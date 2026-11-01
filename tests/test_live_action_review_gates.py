from fastapi.testclient import TestClient

from app.main import app
import app.security as security


def test_legacy_one_step_image_publish_requires_review_and_never_calls_meta(monkeypatch):
    app.dependency_overrides[security.require_user] = lambda: True
    app.dependency_overrides[security.require_master_enabled] = lambda: True
    monkeypatch.setenv("NOVA_API_KEY", "test-secret")
    monkeypatch.setenv("INSTAGRAM_AUTOMATION_ENABLED", "true")

    from app import main

    async def fail_if_called(*args, **kwargs):
        raise AssertionError("Legacy direct publisher must never call Meta")

    monkeypatch.setattr(main, "meta_request", fail_if_called)
    try:
        response = TestClient(app).post(
            "/instagram/publish-image",
            headers={"X-NOVA-API-Key": "test-secret"},
            json={"image_url": "https://example.test/image.png", "caption": "Review me"},
        )
    finally:
        app.dependency_overrides.pop(security.require_user, None)
        app.dependency_overrides.pop(security.require_master_enabled, None)

    assert response.status_code == 410
    assert response.json()["detail"]["review_required"] is True
    assert response.json()["detail"]["published"] is False
