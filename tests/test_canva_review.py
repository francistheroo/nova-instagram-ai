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
