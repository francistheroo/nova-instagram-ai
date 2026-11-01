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


def test_canva_instagram_draft_export_requires_key(monkeypatch):
    monkeypatch.setenv("NOVA_API_KEY", "test-secret")
    response = client.post(
        "/canva/instagram-draft-exports",
        json={"design_id": "design_123", "target": "post", "caption": "Hello"},
    )
    assert response.status_code == 401


def test_canva_post_export_checks_format_and_stops_for_review(monkeypatch):
    monkeypatch.setenv("NOVA_API_KEY", "test-secret")
    from app import canva_review

    calls = []

    async def fake_request(method, path, *, params=None, json_body=None):
        calls.append((method, path, json_body))
        if method == "GET" and path.endswith("/export-formats"):
            return {"formats": [{"type": "png"}, {"type": "mp4"}]}
        return {"job": {"id": "job_123", "status": "in_progress"}}

    monkeypatch.setattr(canva_review, "_canva_request", fake_request)
    response = client.post(
        "/canva/instagram-draft-exports",
        headers={"X-NOVA-API-Key": "test-secret"},
        json={"design_id": "design_123", "target": "post", "caption": "Hello"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["review_required"] is True
    assert payload["published"] is False
    assert payload["available_formats_checked"] is True
    assert payload["caption"] == "Hello"
    assert calls[0][0:2] == ("GET", "designs/design_123/export-formats")
    assert calls[1][2] == {"design_id": "design_123", "format": {"type": "png"}}


def test_canva_reel_export_uses_vertical_mp4_and_never_publishes(monkeypatch):
    monkeypatch.setenv("NOVA_API_KEY", "test-secret")
    from app import canva_review

    calls = []

    async def fake_request(method, path, *, params=None, json_body=None):
        calls.append((method, path, json_body))
        if method == "GET" and path.endswith("/export-formats"):
            return {"formats": [{"type": "png"}, {"type": "mp4"}]}
        return {"job": {"id": "job_456", "status": "in_progress"}}

    monkeypatch.setattr(canva_review, "_canva_request", fake_request)
    response = client.post(
        "/canva/instagram-draft-exports",
        headers={"X-NOVA-API-Key": "test-secret"},
        json={"design_id": "design_456", "target": "reel"},
    )
    assert response.status_code == 200
    assert response.json()["published"] is False
    assert calls[1][2] == {
        "design_id": "design_456",
        "format": {"type": "mp4", "quality": "vertical_1080p"},
    }


def test_canva_export_rejects_unsupported_format_before_creating_job(monkeypatch):
    monkeypatch.setenv("NOVA_API_KEY", "test-secret")
    from app import canva_review

    calls = []

    async def fake_request(method, path, *, params=None, json_body=None):
        calls.append((method, path, json_body))
        return {"formats": [{"type": "pdf"}]}

    monkeypatch.setattr(canva_review, "_canva_request", fake_request)
    response = client.post(
        "/canva/instagram-draft-exports",
        headers={"X-NOVA-API-Key": "test-secret"},
        json={"design_id": "design_789", "target": "reel"},
    )
    assert response.status_code == 422
    assert response.json()["detail"]["available_formats"] == ["pdf"]
    assert len(calls) == 1


def test_canva_draft_export_poll_returns_review_url_not_publish(monkeypatch):
    monkeypatch.setenv("NOVA_API_KEY", "test-secret")
    from app import canva_review

    async def fake_request(method, path, *, params=None, json_body=None):
        return {"job": {"id": "job_123", "status": "success", "urls": ["https://export-download.canva.com/temp.png"]}}

    monkeypatch.setattr(canva_review, "_canva_request", fake_request)
    response = client.get(
        "/canva/instagram-draft-exports/job_123",
        headers={"X-NOVA-API-Key": "test-secret"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["preview_urls"] == ["https://export-download.canva.com/temp.png"]
    assert payload["review_required"] is True
    assert payload["published"] is False


def test_canva_draft_export_rejects_invalid_job_id(monkeypatch):
    monkeypatch.setenv("NOVA_API_KEY", "test-secret")
    response = client.get(
        "/canva/instagram-draft-exports/bad.job",
        headers={"X-NOVA-API-Key": "test-secret"},
    )
    assert response.status_code == 422



def test_canva_mp4_export_creates_reel_container_without_publishing(monkeypatch):
    monkeypatch.setenv("NOVA_API_KEY", "test-secret")
    monkeypatch.setenv("INSTAGRAM_AUTOMATION_ENABLED", "true")
    from app import canva_review, main

    async def fake_canva_request(method, path, *, params=None, json_body=None):
        assert method == "GET"
        assert path == "exports/job_mp4"
        return {
            "job": {
                "id": "job_mp4",
                "status": "success",
                "urls": ["https://export-download.canva.com/temp.mp4"],
            }
        }

    calls = []

    async def fake_meta_request(method, path, *, params=None, data=None):
        calls.append((method, path, params, data))
        return {"id": "reel_container_123"}

    monkeypatch.setattr(canva_review, "_canva_request", fake_canva_request)
    monkeypatch.setattr(main, "instagram_config", lambda: ("token", "user_123", "https://graph.instagram.com/v25.0"))
    monkeypatch.setattr(main, "meta_request", fake_meta_request)
    response = client.post(
        "/canva/instagram-reel-drafts/job_mp4",
        headers={"X-NOVA-API-Key": "test-secret"},
        json={"caption": "My Reel", "share_to_feed": True},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["container_id"] == "reel_container_123"
    assert payload["published"] is False
    assert payload["review_required"] is True
    assert calls[0][0:2] == ("POST", "user_123/media")
    assert calls[0][3]["media_type"] == "REELS"
    assert calls[0][3]["video_url"] == "https://export-download.canva.com/temp.mp4"
    assert len(calls) == 1


def test_canva_export_must_be_successful_before_reel_draft(monkeypatch):
    monkeypatch.setenv("NOVA_API_KEY", "test-secret")
    monkeypatch.setenv("INSTAGRAM_AUTOMATION_ENABLED", "true")
    from app import canva_review

    async def fake_canva_request(method, path, *, params=None, json_body=None):
        return {"job": {"id": "job_pending", "status": "in_progress"}}

    monkeypatch.setattr(canva_review, "_canva_request", fake_canva_request)
    response = client.post(
        "/canva/instagram-reel-drafts/job_pending",
        headers={"X-NOVA-API-Key": "test-secret"},
        json={"caption": "My Reel"},
    )
    assert response.status_code == 409
    assert response.json()["detail"]["status"] == "in_progress"


def test_canva_export_to_reel_respects_disabled_actions(monkeypatch):
    monkeypatch.setenv("NOVA_API_KEY", "test-secret")
    monkeypatch.setenv("INSTAGRAM_AUTOMATION_ENABLED", "false")
    from app import canva_review

    async def fail_if_called(method, path, *, params=None, json_body=None):
        raise AssertionError("Canva export must not be fetched while actions are disabled")

    monkeypatch.setattr(canva_review, "_canva_request", fail_if_called)
    response = client.post(
        "/canva/instagram-reel-drafts/job_mp4",
        headers={"X-NOVA-API-Key": "test-secret"},
        json={"caption": "My Reel"},
    )
    assert response.status_code == 403


def test_canva_reel_draft_requires_master_switch(monkeypatch):
    app.dependency_overrides.pop(security.require_master_enabled, None)
    monkeypatch.setenv("NOVA_API_KEY", "test-secret")
    monkeypatch.setenv("NOVA_ADMIN_USERNAME", "nova-admin")
    monkeypatch.setenv("NOVA_ADMIN_PASSWORD", "test-admin-password")
    monkeypatch.delenv("DATABASE_URL", raising=False)

    response = client.post(
        "/canva/instagram-reel-drafts/job_mp4",
        headers={"X-NOVA-API-Key": "test-secret"},
        auth=("nova-admin", "test-admin-password"),
        json={"caption": "Hello"},
    )

    assert response.status_code == 503
    assert "master switch is OFF" in response.json()["detail"]



def test_canva_png_export_creates_photo_container_without_publishing(monkeypatch):
    monkeypatch.setenv("NOVA_API_KEY", "test-secret")
    monkeypatch.setenv("INSTAGRAM_AUTOMATION_ENABLED", "true")
    from app import canva_review, main

    async def fake_canva(method, path, *, params=None, json_body=None):
        assert (method, path) == ("GET", "exports/png_job")
        return {"job": {"id": "png_job", "status": "success", "urls": ["https://export-download.canva.com/photo.png"]}}

    calls = []

    async def fake_meta(method, path, *, params=None, data=None):
        calls.append((method, path, params, data))
        return {"id": "photo_container_123"}

    monkeypatch.setattr(canva_review, "_canva_request", fake_canva)
    monkeypatch.setattr(main, "instagram_config", lambda: ("token", "user_123", "https://graph.instagram.com/v26.0"))
    monkeypatch.setattr(main, "meta_request", fake_meta)

    response = client.post(
        "/canva/instagram-photo-drafts/png_job",
        headers={"X-NOVA-API-Key": "test-secret"},
        json={"caption": "A reviewed photo"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["container_id"] == "photo_container_123"
    assert payload["published"] is False
    assert payload["review_required"] is True
    assert calls == [(
        "POST", "user_123/media", None,
        {"image_url": "https://export-download.canva.com/photo.png", "caption": "A reviewed photo"},
    )]


def test_canva_photo_draft_rejects_unfinished_export(monkeypatch):
    monkeypatch.setenv("NOVA_API_KEY", "test-secret")
    monkeypatch.setenv("INSTAGRAM_AUTOMATION_ENABLED", "true")
    from app import canva_review

    async def fake_canva(method, path, *, params=None, json_body=None):
        return {"job": {"id": "png_job", "status": "in_progress"}}

    monkeypatch.setattr(canva_review, "_canva_request", fake_canva)
    response = client.post(
        "/canva/instagram-photo-drafts/png_job",
        headers={"X-NOVA-API-Key": "test-secret"},
        json={"caption": "Wait"},
    )
    assert response.status_code == 409
    assert response.json()["detail"]["published"] is False


def test_canva_photo_status_reports_publish_readiness_without_publishing(monkeypatch):
    monkeypatch.setenv("NOVA_API_KEY", "test-secret")
    from app import main

    calls = []

    async def fake_meta(method, path, *, params=None, data=None):
        calls.append((method, path, params, data))
        return {"id": "photo_container_123", "status_code": "FINISHED", "status": "Finished"}

    monkeypatch.setattr(main, "meta_request", fake_meta)
    response = client.get(
        "/canva/instagram-photo-drafts/photo_container_123/status",
        headers={"X-NOVA-API-Key": "test-secret"},
    )
    assert response.status_code == 200
    assert response.json()["publish_allowed"] is True
    assert response.json()["published"] is False
    assert calls == [("GET", "photo_container_123", {"fields": "id,status_code,status"}, None)]


def test_canva_photo_publish_requires_finished_container(monkeypatch):
    monkeypatch.setenv("NOVA_API_KEY", "test-secret")
    monkeypatch.setenv("INSTAGRAM_AUTOMATION_ENABLED", "true")
    from app import canva_review, main

    calls = []

    async def fake_meta(method, path, *, params=None, data=None):
        calls.append((method, path, params, data))
        return {"id": "photo_container_123", "status_code": "IN_PROGRESS", "status": "Processing"}

    monkeypatch.setattr(main, "instagram_config", lambda: ("token", "user_123", "https://graph.instagram.com/v26.0"))
    monkeypatch.setattr(main, "meta_request", fake_meta)
    response = client.post(
        "/canva/instagram-photo-drafts/photo_container_123/publish",
        headers={"X-NOVA-API-Key": "test-secret"},
    )
    assert response.status_code == 409
    assert response.json()["detail"]["published"] is False
    assert [call[1] for call in calls] == ["photo_container_123"]


def test_canva_photo_publish_is_explicit_after_finished_status(monkeypatch):
    monkeypatch.setenv("NOVA_API_KEY", "test-secret")
    monkeypatch.setenv("INSTAGRAM_AUTOMATION_ENABLED", "true")
    from app import main

    calls = []

    async def fake_meta(method, path, *, params=None, data=None):
        calls.append((method, path, params, data))
        if method == "GET":
            return {"id": "photo_container_123", "status_code": "FINISHED"}
        return {"id": "published_photo_123"}

    monkeypatch.setattr(main, "instagram_config", lambda: ("token", "user_123", "https://graph.instagram.com/v26.0"))
    monkeypatch.setattr(main, "meta_request", fake_meta)
    response = client.post(
        "/canva/instagram-photo-drafts/photo_container_123/publish",
        headers={"X-NOVA-API-Key": "test-secret"},
    )
    assert response.status_code == 200
    assert response.json()["published"] is True
    assert [call[1] for call in calls] == ["photo_container_123", "user_123/media_publish"]
    assert calls[-1][3] == {"creation_id": "photo_container_123"}
