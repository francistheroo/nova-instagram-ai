import pytest

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


def test_oauth_callback_exchanges_code_and_keeps_tokens_server_side(monkeypatch):
    from app import instagram_oauth
    from app.oauth_security import create_oauth_state, validate_oauth_state

    configure_oauth(monkeypatch)
    state = create_oauth_state()
    nonce = validate_oauth_state(state)["nonce"]
    monkeypatch.setattr(instagram_oauth, "consume_oauth_state", lambda value: value == nonce)

    saved = []

    def save_token(user_id, token, *, expires_at):
        saved.append((user_id, token, expires_at))

    monkeypatch.setattr(instagram_oauth, "save_instagram_token", save_token)

    class FakeResponse:
        def __init__(self, payload):
            self.payload = payload
            self.is_error = False

        def json(self):
            return self.payload

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, *, data):
            assert url == "https://api.instagram.com/oauth/access_token"
            assert data["code"] == "fake-auth-code"
            assert data["client_secret"] == "test-secret"
            return FakeResponse({"access_token": "short-token-secret", "user_id": "123456"})

        async def get(self, url, *, params):
            assert url == "https://graph.instagram.com/v25.0/access_token"
            assert params["access_token"] == "short-token-secret"
            return FakeResponse({"access_token": "long-token-secret", "expires_in": 3600})

    monkeypatch.setattr(instagram_oauth.httpx, "AsyncClient", lambda **kwargs: FakeClient())
    response = client.get(
        "/oauth/instagram/callback",
        params={"code": "fake-auth-code", "state": state},
        cookies={instagram_oauth.STATE_COOKIE: state},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/?instagram_connected=pending_verification"
    assert saved[0][0] == "123456"
    assert saved[0][1] == "long-token-secret"
    assert saved[0][2] is not None
    assert "short-token-secret" not in response.text
    assert "long-token-secret" not in response.text
    assert "long-token-secret" not in response.headers["location"]
    assert "max-age=0" in response.headers["set-cookie"].lower()


def test_oauth_callback_rejects_replayed_persisted_state_before_exchange(monkeypatch):
    from app import instagram_oauth
    from app.oauth_security import create_oauth_state

    configure_oauth(monkeypatch)
    state = create_oauth_state()
    monkeypatch.setattr(instagram_oauth, "consume_oauth_state", lambda nonce: False)

    async def should_not_exchange(*args, **kwargs):
        pytest.fail("A replayed OAuth state must not exchange the code")

    monkeypatch.setattr(instagram_oauth.httpx, "AsyncClient", lambda **kwargs: should_not_exchange())
    response = client.get(
        "/oauth/instagram/callback",
        params={"code": "fake-auth-code", "state": state},
        cookies={instagram_oauth.STATE_COOKIE: state},
        follow_redirects=False,
    )

    assert response.status_code == 400
    assert "already used" in response.json()["detail"]


@pytest.mark.parametrize(
    "parameter,value",
    [
        ("code", "x" * 4097),
        ("state", "x" * 2049),
        ("error", "x" * 201),
    ],
)
def test_oauth_callback_rejects_oversized_query_values(monkeypatch, parameter, value):
    configure_oauth(monkeypatch)
    response = client.get("/oauth/instagram/callback", params={parameter: value})
    assert response.status_code == 422
