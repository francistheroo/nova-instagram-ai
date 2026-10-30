from fastapi.testclient import TestClient

from app.main import app
import app.security as security

client = TestClient(app)
KEY = {"X-NOVA-API-Key": "test-secret"}
ADMIN = ("nova-admin", "test-admin-password")


def _enable_reel_writes(monkeypatch):
    monkeypatch.setenv("NOVA_ADMIN_USERNAME", ADMIN[0])
    monkeypatch.setenv("NOVA_ADMIN_PASSWORD", ADMIN[1])
    monkeypatch.setitem(app.dependency_overrides, security.require_master_enabled, lambda: True)


def test_reel_routes_require_api_key(monkeypatch):
    monkeypatch.setenv("NOVA_API_KEY", "test-secret")
    response = client.post(
        "/instagram/reels/drafts",
        json={"video_url": "https://example.com/reel.mp4", "caption": "Hello"},
    )
    assert response.status_code == 401


def test_reel_draft_creates_container_without_publishing(monkeypatch):
    monkeypatch.setenv("NOVA_API_KEY", "test-secret")
    monkeypatch.setenv("INSTAGRAM_AUTOMATION_ENABLED", "true")
    _enable_reel_writes(monkeypatch)
    from app import main

    calls = []

    async def fake_request(method, path, *, params=None, data=None):
        calls.append((method, path, params, data))
        return {"id": "container_123"}

    monkeypatch.setattr(main, "instagram_config", lambda: ("token", "user_123", "https://graph.instagram.com/v25.0"))
    monkeypatch.setattr(main, "meta_request", fake_request)
    response = client.post(
        "/instagram/reels/drafts",
        headers=KEY,
        auth=ADMIN,
        json={
            "video_url": "https://example.com/reel.mp4",
            "caption": "Hello",
            "share_to_feed": True,
        },
    )
    assert response.status_code == 200
    assert response.json()["published"] is False
    assert response.json()["review_required"] is True
    assert calls[0][0:2] == ("POST", "user_123/media")
    assert calls[0][3]["media_type"] == "REELS"
    assert len(calls) == 1


def test_reel_draft_requires_https(monkeypatch):
    monkeypatch.setenv("NOVA_API_KEY", "test-secret")
    _enable_reel_writes(monkeypatch)
    response = client.post(
        "/instagram/reels/drafts",
        headers=KEY,
        json={"video_url": "http://example.com/reel.mp4"},
    )
    assert response.status_code == 422


def test_reel_status_is_read_only(monkeypatch):
    monkeypatch.setenv("NOVA_API_KEY", "test-secret")
    from app import main

    async def fake_request(method, path, *, params=None, data=None):
        assert method == "GET"
        return {"id": "container_123", "status_code": "FINISHED", "status": "Finished"}

    monkeypatch.setattr(main, "meta_request", fake_request)
    response = client.get("/instagram/reels/drafts/container_123", headers=KEY, auth=ADMIN)
    assert response.status_code == 200
    assert response.json()["publish_allowed"] is True
    assert response.json()["published"] is False


def test_reel_publish_refuses_container_not_finished(monkeypatch):
    monkeypatch.setenv("NOVA_API_KEY", "test-secret")
    monkeypatch.setenv("INSTAGRAM_AUTOMATION_ENABLED", "true")
    from app import main

    calls = []

    async def fake_request(method, path, *, params=None, data=None):
        calls.append((method, path, params, data))
        return {"id": "container_123", "status_code": "IN_PROGRESS", "status": "Processing"}

    monkeypatch.setattr(main, "instagram_config", lambda: ("token", "user_123", "https://graph.instagram.com/v25.0"))
    monkeypatch.setattr(main, "meta_request", fake_request)
    response = client.post("/instagram/reels/drafts/container_123/publish", headers=KEY)
    assert response.status_code == 409
    assert len(calls) == 1
    assert calls[0][0] == "GET"


def test_reel_publish_is_explicit_and_requires_finished(monkeypatch):
    monkeypatch.setenv("NOVA_API_KEY", "test-secret")
    monkeypatch.setenv("INSTAGRAM_AUTOMATION_ENABLED", "true")
    from app import main

    calls = []

    async def fake_request(method, path, *, params=None, data=None):
        calls.append((method, path, params, data))
        if method == "GET":
            return {"id": "container_123", "status_code": "FINISHED"}
        return {"id": "published_media_456"}

    monkeypatch.setattr(main, "instagram_config", lambda: ("token", "user_123", "https://graph.instagram.com/v25.0"))
    monkeypatch.setattr(main, "meta_request", fake_request)
    response = client.post("/instagram/reels/drafts/container_123/publish", headers=KEY)
    assert response.status_code == 200
    assert response.json()["published"] is True
    assert calls[-1][0:2] == ("POST", "user_123/media_publish")
    assert calls[-1][3] == {"creation_id": "container_123"}
