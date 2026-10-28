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


def test_canva_status_reports_oauth_code_but_not_design_export():
    response = client.get("/canva/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["oauth_implemented"] is True
    assert payload["design_listing_implemented"] is False
    assert payload["export_implemented"] is False


def test_health_reports_canva_oauth_implementation():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["canva_oauth_implemented"] is True
