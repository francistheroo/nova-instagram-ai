import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)



@pytest.fixture(autouse=True)
def authenticate_admin_requests(monkeypatch):
    monkeypatch.setenv("NOVA_ADMIN_USERNAME", "test-admin")
    monkeypatch.setenv("NOVA_ADMIN_PASSWORD", "test-password")
    original_request = client.request

    def authenticated_request(method, url, *args, **kwargs):
        headers = dict(kwargs.get("headers") or {})
        headers.setdefault("Authorization", "Basic dGVzdC1hZG1pbjp0ZXN0LXBhc3N3b3Jk")
        kwargs["headers"] = headers
        kwargs.pop("auth", None)
        return original_request(method, url, *args, **kwargs)

    monkeypatch.setattr(client, "request", authenticated_request)


def _admin_auth(monkeypatch):
    monkeypatch.setenv("NOVA_ADMIN_USERNAME", "test-admin")
    monkeypatch.setenv("NOVA_ADMIN_PASSWORD", "test-password")
    return ("test-admin", "test-password")



def test_canva_photo_publish_disabled(monkeypatch):
    monkeypatch.setenv("NOVA_API_KEY", "test-secret")
    admin = _admin_auth(monkeypatch)
    monkeypatch.setenv("INSTAGRAM_AUTOMATION_ENABLED", "false")
    from app import canva_direct_post

    async def fail_if_called(*args, **kwargs):
        raise AssertionError("Canva must not be called while publishing is disabled")

    monkeypatch.setattr(canva_direct_post, "_canva_request", fail_if_called)
    response = client.post(
        "/canva/instagram-posts/publish",
        headers={"X-NOVA-API-Key": "test-secret"},
        json={"design_id": "design_123", "caption": "Hello"},
    )
    assert response.status_code == 403


def test_canva_photo_publish_success(monkeypatch):
    monkeypatch.setenv("NOVA_API_KEY", "test-secret")
    monkeypatch.setenv("INSTAGRAM_AUTOMATION_ENABLED", "true")
    monkeypatch.setattr("app.canva_direct_post.require_master_enabled", lambda: True)
    monkeypatch.setattr("app.canva_direct_post.require_master_enabled", lambda: True)
    from app import canva_direct_post, main

    async def no_sleep(_seconds):
        return None

    monkeypatch.setattr(canva_direct_post.asyncio, "sleep", no_sleep)
    canva_calls = []

    async def fake_canva(method, path, *, params=None, json_body=None):
        canva_calls.append((method, path, json_body))
        if method == "GET" and path.endswith("/export-formats"):
            return {"formats": [{"type": "png"}]}
        if method == "POST":
            return {"job": {"id": "job_123"}}
        return {"job": {"id": "job_123", "status": "success", "urls": ["https://export-download.canva.com/temp.png"]}}

    meta_calls = []

    async def fake_meta(method, path, *, params=None, data=None):
        meta_calls.append((method, path, data))
        if path == "user_123/media":
            return {"id": "container_123"}
        if path == "user_123/media_publish":
            return {"id": "media_123"}
        raise AssertionError(path)

    monkeypatch.setattr(canva_direct_post, "_canva_request", fake_canva)
    monkeypatch.setattr(main, "instagram_config", lambda: ("token", "user_123", "https://graph.instagram.com/v25.0"))
    monkeypatch.setattr(main, "meta_request", fake_meta)

    response = client.post(
        "/canva/instagram-posts/publish",
        headers={"X-NOVA-API-Key": "test-secret"},
        json={"design_id": "design_123", "caption": "Hello"},
    )
    assert response.status_code == 200
    assert response.json()["published"] is True
    assert len(canva_calls) == 3
    assert [call[1] for call in meta_calls] == ["user_123/media", "user_123/media_publish"]
