from fastapi.testclient import TestClient

from app.main import app


def test_admin_dashboard_requires_admin_login(monkeypatch):
    monkeypatch.setenv("NOVA_ADMIN_USERNAME", "nova-admin")
    monkeypatch.setenv("NOVA_ADMIN_PASSWORD", "test-only-password")

    response = TestClient(app).get("/admin")

    assert response.status_code == 401
    assert "WWW-Authenticate" in response.headers


def test_admin_dashboard_accepts_admin_login(monkeypatch):
    monkeypatch.setenv("NOVA_ADMIN_USERNAME", "nova-admin")
    monkeypatch.setenv("NOVA_ADMIN_PASSWORD", "test-only-password")

    response = TestClient(app).get(
        "/admin",
        auth=("nova-admin", "test-only-password"),
    )

    assert response.status_code == 200
    assert "NOVA Admin" in response.text


def test_admin_dashboard_fails_closed_without_credentials(monkeypatch):
    monkeypatch.delenv("NOVA_ADMIN_USERNAME", raising=False)
    monkeypatch.delenv("NOVA_ADMIN_PASSWORD", raising=False)

    response = TestClient(app).get("/admin")

    assert response.status_code == 503
