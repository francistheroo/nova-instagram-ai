from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app, base_url="https://testserver")


def configure_oauth(monkeypatch):
    monkeypatch.setenv("INSTAGRAM_OAUTH_CLIENT_ID", "test-client")
    monkeypatch.setenv("INSTAGRAM_OAUTH_CLIENT_SECRET", "test-secret")
    monkeypatch.setenv("INSTAGRAM_OAUTH_REDIRECT_URI", "https://testserver/oauth/instagram/callback")
    monkeypatch.setenv("INSTAGRAM_OAUTH_SCOPES", "instagram_business_basic")
    monkeypatch.setenv("OAUTH_STATE_SECRET", "x" * 48)
    monkeypatch.setenv("TOKEN_ENCRYPTION_KEY", "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=")
    monkeypatch.setenv("DATABASE_URL", "postgresql://unused.invalid/nova")


def test_oauth_start_requires_configuration(monkeypatch):
    for key in (
        "INSTAGRAM_OAUTH_CLIENT_ID",
        "INSTAGRAM_OAUTH_CLIENT_SECRET",
        "INSTAGRAM_OAUTH_REDIRECT_URI",
        "OAUTH_STATE_SECRET",
        "DATABASE_URL",
    ):
        monkeypatch.delenv(key, raising=False)
    response = client.get("/oauth/instagram/start")
    assert response.status_code == 503


def test_oauth_start_redirects_and_sets_secure_state_cookie(monkeypatch):
    configure_oauth(monkeypatch)
    monkeypatch.setattr("app.instagram_oauth.save_oauth_state", lambda nonce, expires_at: None)
    response = client.get("/oauth/instagram/start", follow_redirects=False)
    assert response.status_code == 302
    parsed = urlparse(response.headers["location"])
    assert parsed.scheme == "https"
    assert parsed.netloc == "www.instagram.com"
    assert parsed.path == "/oauth/authorize"
    query = parse_qs(parsed.query)
    assert query["client_id"] == ["test-client"]
    assert query["redirect_uri"] == ["https://testserver/oauth/instagram/callback"]
    assert query["response_type"] == ["code"]
    assert query["scope"] == ["instagram_business_basic"]
    assert query["state"]
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "secure" in cookie
    assert "samesite=lax" in cookie


def test_oauth_callback_rejects_state_without_browser_cookie(monkeypatch):
    configure_oauth(monkeypatch)
    response = client.get(
        "/oauth/instagram/callback",
        params={"code": "fake-code", "state": "fake-state"},
    )
    assert response.status_code == 400
    assert "state" in response.json()["detail"].lower()


def test_oauth_callback_rejects_missing_code_or_state(monkeypatch):
    configure_oauth(monkeypatch)
    response = client.get("/oauth/instagram/callback")
    assert response.status_code == 400


def test_manual_refresh_requires_api_key(monkeypatch):
    monkeypatch.delenv("NOVA_API_KEY", raising=False)
    response = client.post("/oauth/instagram/refresh")
    assert response.status_code == 503


def test_manual_refresh_rejects_invalid_api_key(monkeypatch):
    monkeypatch.setenv("NOVA_API_KEY", "expected-secret")
    response = client.post(
        "/oauth/instagram/refresh",
        headers={"X-NOVA-API-Key": "wrong-secret"},
    )
    assert response.status_code == 401
