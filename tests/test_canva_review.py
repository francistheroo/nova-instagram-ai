from fastapi.testclient import TestClient

from app.main import app

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
