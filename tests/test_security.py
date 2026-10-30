from fastapi.testclient import TestClient

import app.security as security
from app.main import app


def test_normal_app_requires_password(monkeypatch):
    monkeypatch.setenv("NOVA_ADMIN_USERNAME", "nova-admin")
    monkeypatch.setenv("NOVA_ADMIN_PASSWORD", "test-only-password")
    response = TestClient(app).get("/app")
    assert response.status_code == 401
    assert "WWW-Authenticate" in response.headers


def test_normal_app_accepts_configured_account(monkeypatch):
    monkeypatch.setenv("NOVA_ADMIN_USERNAME", "nova-admin")
    monkeypatch.setenv("NOVA_ADMIN_PASSWORD", "test-only-password")
    response = TestClient(app).get("/app", auth=("nova-admin", "test-only-password"))
    assert response.status_code == 200
    assert "NOVA Content Studio" in response.text


def test_ai_endpoint_fails_closed_when_master_switch_is_off(monkeypatch):
    monkeypatch.setenv("NOVA_ADMIN_USERNAME", "nova-admin")
    monkeypatch.setenv("NOVA_ADMIN_PASSWORD", "test-only-password")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(security, "master_enabled", lambda: False)
    response = TestClient(app).post(
        "/ai/generate-caption",
        auth=("nova-admin", "test-only-password"),
        json={"topic": "Kerala monsoon", "language": "English"},
    )
    assert response.status_code == 503
    assert "master switch is OFF" in response.json()["detail"]
