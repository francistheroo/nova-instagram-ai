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


def test_direct_canva_reel_publish_requires_action_flag(monkeypatch):
    monkeypatch.setenv("NOVA_API_KEY", "test-secret")
    monkeypatch.setenv("INSTAGRAM_AUTOMATION_ENABLED", "false")
    from app import canva_direct_publish

    async def fail_if_called(*args, **kwargs):
        raise AssertionError("Canva must not be called when publishing is disabled")

    monkeypatch.setattr(canva_direct_publish, "_canva_request", fail_if_called)
    response = client.post(
        "/canva/instagram-reels/publish",
        headers={"X-NOVA-API-Key": "test-secret"},
        json={"design_id": "design_123", "caption": "Hello"},
    )
    assert response.status_code == 403


def test_direct_canva_reel_publish_exports_waits_and_publishes(monkeypatch):
    monkeypatch.setenv("NOVA_API_KEY", "test-secret")
    monkeypatch.setenv("INSTAGRAM_AUTOMATION_ENABLED", "true")
    from app import canva_direct_publish, main

    async def no_sleep(_seconds):
        return None

    monkeypatch.setattr(canva_direct_publish.asyncio, "sleep", no_sleep)
    canva_calls = []

    async def fake_canva(method, path, *, params=None, json_body=None):
        canva_calls.append((method, path, json_body))
        if method == "GET" and path.endswith("/export-formats"):
            return {"formats": [{"type": "mp4"}]}
        if method == "POST" and path == "exports":
            return {"job": {"id": "job_123", "status": "in_progress"}}
        return {"job": {"id": "job_123", "status": "success", "urls": ["https://export-download.canva.com/temp.mp4"]}}

    meta_calls = []

    async def fake_meta(method, path, *, params=None, data=None):
        meta_calls.append((method, path, params, data))
        if method == "POST" and path == "user_123/media":
            return {"id": "container_123"}
        if method == "GET" and path == "container_123":
            return {"id": "container_123", "status_code": "FINISHED"}
        if method == "POST" and path == "user_123/media_publish":
            return {"id": "published_media_123"}
        raise AssertionError((method, path))

    monkeypatch.setattr(canva_direct_publish, "_canva_request", fake_canva)
    monkeypatch.setattr(main, "instagram_config", lambda: ("token", "user_123", "https://graph.instagram.com/v25.0"))
    monkeypatch.setattr(main, "meta_request", fake_meta)

    response = client.post(
        "/canva/instagram-reels/publish",
        headers={"X-NOVA-API-Key": "test-secret"},
        json={"design_id": "design_123", "caption": "Hello", "share_to_feed": True},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["published"] is True
    assert payload["container_id"] == "container_123"
    assert len(canva_calls) == 3
    assert [call[1] for call in meta_calls] == [
        "user_123/media", "container_123", "user_123/media_publish"
    ]
    assert meta_calls[-1][3] == {"creation_id": "container_123"}


def test_direct_canva_reel_publish_does_not_publish_before_finished(monkeypatch):
    monkeypatch.setenv("NOVA_API_KEY", "test-secret")
    monkeypatch.setenv("INSTAGRAM_AUTOMATION_ENABLED", "true")
    from app import canva_direct_publish, main

    async def no_sleep(_seconds):
        return None

    monkeypatch.setattr(canva_direct_publish.asyncio, "sleep", no_sleep)

    async def fake_canva(method, path, *, params=None, json_body=None):
        if method == "GET" and path.endswith("/export-formats"):
            return {"formats": [{"type": "mp4"}]}
        if method == "POST":
            return {"job": {"id": "job_123"}}
        return {"job": {"status": "success", "urls": ["https://export-download.canva.com/temp.mp4"]}}

    calls = []

    async def fake_meta(method, path, *, params=None, data=None):
        calls.append((method, path))
        if method == "POST" and path == "user_123/media":
            return {"id": "container_123"}
        return {"status_code": "IN_PROGRESS", "status": "Processing"}

    monkeypatch.setattr(canva_direct_publish, "_canva_request", fake_canva)
    monkeypatch.setattr(main, "instagram_config", lambda: ("token", "user_123", "https://graph.instagram.com/v25.0"))
    monkeypatch.setattr(main, "meta_request", fake_meta)

    response = client.post(
        "/canva/instagram-reels/publish",
        headers={"X-NOVA-API-Key": "test-secret"},
        json={"design_id": "design_123"},
    )
    assert response.status_code == 409
    assert response.json()["detail"]["published"] is False
    assert not any(path == "user_123/media_publish" for _, path in calls)


def test_direct_canva_reel_publish_requires_admin_login(monkeypatch):
    app.dependency_overrides.pop(security.require_user, None)
    monkeypatch.setenv("NOVA_API_KEY", "test-secret")
    monkeypatch.setenv("NOVA_ADMIN_USERNAME", "nova-admin")
    monkeypatch.setenv("NOVA_ADMIN_PASSWORD", "test-admin-password")
    monkeypatch.setenv("INSTAGRAM_AUTOMATION_ENABLED", "true")

    response = client.post(
        "/canva/instagram-reels/publish",
        headers={"X-NOVA-API-Key": "test-secret"},
        json={"design_id": "design_123", "caption": "Hello"},
    )

    assert response.status_code == 401


def test_direct_canva_reel_publish_requires_master_switch(monkeypatch):
    app.dependency_overrides.pop(security.require_master_enabled, None)
    monkeypatch.setenv("NOVA_API_KEY", "test-secret")
    monkeypatch.setenv("NOVA_ADMIN_USERNAME", "nova-admin")
    monkeypatch.setenv("NOVA_ADMIN_PASSWORD", "test-admin-password")
    monkeypatch.setenv("INSTAGRAM_AUTOMATION_ENABLED", "true")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    response = client.post(
        "/canva/instagram-reels/publish",
        headers={"X-NOVA-API-Key": "test-secret"},
        auth=("nova-admin", "test-admin-password"),
        json={"design_id": "design_123", "caption": "Hello"},
    )
    assert response.status_code == 503
    assert "master switch is OFF" in response.json()["detail"]
