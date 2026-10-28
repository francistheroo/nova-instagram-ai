from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_canva_oauth_start_requires_server_configuration(monkeypatch):
    monkeypatch.delenv("CANVA_CLIENT_ID", raising=False)
    monkeypatch.delenv("CANVA_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("CANVA_REDIRECT_URI", raising=False)
    response = client.get("/oauth/canva/start")
    assert response.status_code == 503


def test_canva_oauth_callback_rejects_missing_code_and_state():
    response = client.get("/oauth/canva/callback")
    assert response.status_code == 400


def test_canva_status_reports_oauth_and_design_export_implementation():
    response = client.get("/canva/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["oauth_implemented"] is True
    assert payload["design_listing_implemented"] is True
    assert payload["export_implemented"] is True


def test_health_reports_canva_oauth_implementation():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["canva_oauth_implemented"] is True


def test_canva_design_routes_require_nova_key(monkeypatch):
    monkeypatch.setenv("NOVA_API_KEY", "test-secret")
    response = client.get("/canva/designs")
    assert response.status_code == 401


def test_canva_design_routes_reject_missing_canva_connection(monkeypatch):
    monkeypatch.setenv("NOVA_API_KEY", "test-secret")
    from app import canva_api
    monkeypatch.setattr(canva_api, "load_latest_canva_tokens", lambda: None)
    response = client.get("/canva/designs", headers={"X-NOVA-API-Key": "test-secret"})
    assert response.status_code == 503
    assert "not connected" in response.json()["detail"]


def test_canva_export_request_rejects_unsupported_format(monkeypatch):
    monkeypatch.setenv("NOVA_API_KEY", "test-secret")
    response = client.post(
        "/canva/exports",
        headers={"X-NOVA-API-Key": "test-secret"},
        json={"design_id": "design_123", "format": "exe"},
    )
    assert response.status_code == 422


def test_canva_status_reports_design_and_export_routes():
    response = client.get("/canva/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["design_listing_implemented"] is True
    assert payload["export_implemented"] is True



def test_canva_refresh_requires_nova_key(monkeypatch):
    monkeypatch.setenv("NOVA_API_KEY", "test-secret")
    response = client.post("/oauth/canva/refresh")
    assert response.status_code == 401


def test_canva_refresh_requires_configured_client_and_stored_refresh_token(monkeypatch):
    monkeypatch.setenv("NOVA_API_KEY", "test-secret")
    monkeypatch.setenv("CANVA_CLIENT_ID", "test-client")
    monkeypatch.setenv("CANVA_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("CANVA_REDIRECT_URI", "https://example.com/oauth/canva/callback")
    from app import canva_oauth
    monkeypatch.setattr(canva_oauth, "load_latest_canva_tokens", lambda: {"access_token": "old-access", "refresh_token": ""})
    response = client.post("/oauth/canva/refresh", headers={"X-NOVA-API-Key": "test-secret"})
    assert response.status_code == 503
    assert "refresh token" in response.json()["detail"].lower()
