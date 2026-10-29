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

    class NoExchangeClient:
        async def __aenter__(self):
            pytest.fail("A replayed OAuth state must not exchange the code")

        async def __aexit__(self, *args):
            return False

    monkeypatch.setattr(instagram_oauth.httpx, "AsyncClient", lambda **kwargs: NoExchangeClient())
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


@pytest.mark.parametrize(
    "short_payload",
    [
        None,
        [],
        "unexpected",
        {},
        {"access_token": [] , "user_id": "123456"},
        {"access_token": "short-token", "user_id": {"nested": "id"}},
    ],
)
def test_instagram_callback_rejects_malformed_short_token_payload(monkeypatch, short_payload):
    from app import instagram_oauth
    from app.oauth_security import create_oauth_state, validate_oauth_state

    configure_oauth(monkeypatch)
    state = create_oauth_state()
    nonce = validate_oauth_state(state)["nonce"]
    monkeypatch.setattr(instagram_oauth, "consume_oauth_state", lambda value: value == nonce)
    monkeypatch.setattr(
        instagram_oauth,
        "save_instagram_token",
        lambda *args, **kwargs: pytest.fail("Malformed token response must not be stored"),
    )

    class FakeResponse:
        is_error = False

        def json(self):
            return short_payload

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, *args, **kwargs):
            return FakeResponse()

        async def get(self, *args, **kwargs):
            pytest.fail("Long-lived exchange must not run after malformed short-token response")

    monkeypatch.setattr(instagram_oauth.httpx, "AsyncClient", lambda **kwargs: FakeClient())
    response = client.get(
        "/oauth/instagram/callback",
        params={"code": "fake-auth-code", "state": state},
        cookies={instagram_oauth.STATE_COOKIE: state},
        follow_redirects=False,
    )

    assert response.status_code == 502
    assert "short-token" not in response.text
    assert "client_secret" not in response.text


@pytest.mark.parametrize(
    "long_payload",
    [
        None,
        [],
        "unexpected",
        {},
        {"access_token": []},
        {"access_token": "long-token", "expires_in": "3600"},
        {"access_token": "long-token", "expires_in": True},
        {"access_token": "long-token", "expires_in": float("inf")},
        {"access_token": "long-token", "expires_in": 10**100},
    ],
)
def test_instagram_callback_rejects_malformed_long_token_payload(monkeypatch, long_payload):
    from app import instagram_oauth
    from app.oauth_security import create_oauth_state, validate_oauth_state

    configure_oauth(monkeypatch)
    state = create_oauth_state()
    nonce = validate_oauth_state(state)["nonce"]
    monkeypatch.setattr(instagram_oauth, "consume_oauth_state", lambda value: value == nonce)
    monkeypatch.setattr(
        instagram_oauth,
        "save_instagram_token",
        lambda *args, **kwargs: pytest.fail("Malformed token response must not be stored"),
    )

    class FakeResponse:
        is_error = False

        def __init__(self, payload):
            self.payload = payload

        def json(self):
            return self.payload

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, *args, **kwargs):
            return FakeResponse({"access_token": "short-token", "user_id": "123456"})

        async def get(self, *args, **kwargs):
            return FakeResponse(long_payload)

    monkeypatch.setattr(instagram_oauth.httpx, "AsyncClient", lambda **kwargs: FakeClient())
    response = client.get(
        "/oauth/instagram/callback",
        params={"code": "fake-auth-code", "state": state},
        cookies={instagram_oauth.STATE_COOKIE: state},
        follow_redirects=False,
    )

    assert response.status_code == 502
    assert "short-token" not in response.text
    assert "client_secret" not in response.text


def _configure_instagram_refresh(monkeypatch, stored=None):
    from datetime import datetime, timedelta, timezone

    from app import instagram_oauth

    monkeypatch.setenv("NOVA_API_KEY", "refresh-test-key")
    configure_oauth(monkeypatch)
    if stored is None:
        stored = {
            "instagram_user_id": "123456",
            "access_token": "old-access-secret",
            "expires_at": datetime.now(timezone.utc) + timedelta(days=30),
        }
    monkeypatch.setattr(instagram_oauth, "load_latest_instagram_token", lambda: stored)
    return instagram_oauth, stored


def test_instagram_refresh_stores_new_token_without_returning_it(monkeypatch):
    from datetime import datetime, timezone

    from app import instagram_oauth

    _configure_instagram_refresh(monkeypatch)
    saved = []
    monkeypatch.setattr(
        instagram_oauth,
        "save_instagram_token",
        lambda user_id, token, *, expires_at: saved.append((user_id, token, expires_at)),
    )

    class FakeResponse:
        is_error = False
        status_code = 200

        def json(self):
            return {"access_token": "new-access-secret", "expires_in": 7200}

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, *, params):
            assert url == "https://graph.instagram.com/refresh_access_token"
            assert params == {"grant_type": "ig_refresh_token", "access_token": "old-access-secret"}
            return FakeResponse()

    monkeypatch.setattr(instagram_oauth.httpx, "AsyncClient", lambda **kwargs: FakeClient())
    response = client.post("/oauth/instagram/refresh", headers={"X-NOVA-API-Key": "refresh-test-key"})

    assert response.status_code == 200
    assert response.json()["status"] == "refreshed"
    assert response.json()["token_returned"] is False
    assert saved[0][0] == "123456"
    assert saved[0][1] == "new-access-secret"
    assert saved[0][2] > datetime.now(timezone.utc)
    assert "new-access-secret" not in response.text
    assert "old-access-secret" not in response.text


def test_instagram_refresh_preserves_known_expiry_when_provider_omits_it(monkeypatch):
    from datetime import datetime, timedelta, timezone

    from app import instagram_oauth

    _configure_instagram_refresh(monkeypatch)
    fallback = datetime.now(timezone.utc) + timedelta(days=12)
    stored = {"instagram_user_id": "123456", "access_token": "old-access", "expires_at": fallback}
    monkeypatch.setattr(instagram_oauth, "load_latest_instagram_token", lambda: stored)
    saved = []
    monkeypatch.setattr(
        instagram_oauth,
        "save_instagram_token",
        lambda user_id, token, *, expires_at: saved.append((user_id, token, expires_at)),
    )

    class FakeResponse:
        is_error = False
        status_code = 200

        def json(self):
            return {"access_token": "new-access"}

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setattr(instagram_oauth.httpx, "AsyncClient", lambda **kwargs: FakeClient())
    response = client.post("/oauth/instagram/refresh", headers={"X-NOVA-API-Key": "refresh-test-key"})

    assert response.status_code == 200
    assert saved[0][2] == fallback
    assert response.json()["expires_at"] == fallback.isoformat()


def test_instagram_refresh_rejects_expired_token_without_contacting_provider(monkeypatch):
    from datetime import datetime, timedelta, timezone

    from app import instagram_oauth

    _configure_instagram_refresh(
        monkeypatch,
        {"instagram_user_id": "123456", "access_token": "expired-secret", "expires_at": datetime.now(timezone.utc) - timedelta(seconds=1)},
    )

    class NoRequestClient:
        async def __aenter__(self):
            pytest.fail("An already-expired token must not be refreshed")

        async def __aexit__(self, *args):
            return False

    monkeypatch.setattr(instagram_oauth.httpx, "AsyncClient", lambda **kwargs: NoRequestClient())
    response = client.post("/oauth/instagram/refresh", headers={"X-NOVA-API-Key": "refresh-test-key"})
    assert response.status_code == 409
    assert "Reconnect Instagram" in response.json()["detail"]
    assert "expired-secret" not in response.text


@pytest.mark.parametrize(
    "stored",
    [
        None,
        [],
        {},
        {"instagram_user_id": "123456", "access_token": "", "expires_at": None},
        {"instagram_user_id": "", "access_token": "some-token", "expires_at": None},
    ],
)
def test_instagram_refresh_rejects_missing_or_malformed_stored_credentials(monkeypatch, stored):
    from app import instagram_oauth

    _configure_instagram_refresh(monkeypatch, stored)

    class NoRequestClient:
        async def __aenter__(self):
            pytest.fail("Malformed stored credentials must be rejected before contacting Instagram")

        async def __aexit__(self, *args):
            return False

    monkeypatch.setattr(instagram_oauth.httpx, "AsyncClient", lambda **kwargs: NoRequestClient())
    response = client.post("/oauth/instagram/refresh", headers={"X-NOVA-API-Key": "refresh-test-key"})

    assert response.status_code in (404, 503)
    assert "some-token" not in response.text


@pytest.mark.parametrize("expires_at", ["not-a-date", "naive"])
def test_instagram_refresh_rejects_invalid_stored_expiry(monkeypatch, expires_at):
    from datetime import datetime

    from app import instagram_oauth

    if expires_at == "naive":
        expires_at = datetime(2030, 1, 1)
    _configure_instagram_refresh(
        monkeypatch,
        {"instagram_user_id": "123456", "access_token": "old-access", "expires_at": expires_at},
    )

    class NoRequestClient:
        async def __aenter__(self):
            pytest.fail("Invalid stored expiry must be rejected before contacting Instagram")

        async def __aexit__(self, *args):
            return False

    monkeypatch.setattr(instagram_oauth.httpx, "AsyncClient", lambda **kwargs: NoRequestClient())
    response = client.post("/oauth/instagram/refresh", headers={"X-NOVA-API-Key": "refresh-test-key"})
    assert response.status_code == 503


@pytest.mark.parametrize(
    "provider_status,expected_status",
    [(400, 409), (401, 409), (403, 409), (429, 503), (500, 502), (503, 502)],
)
def test_instagram_refresh_classifies_provider_failures_without_leaking_token(
    monkeypatch, provider_status, expected_status
):
    from app import instagram_oauth

    _configure_instagram_refresh(monkeypatch)

    class FakeResponse:
        is_error = True
        status_code = provider_status

        def json(self):
            return {"error": {"message": "private upstream detail"}}

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setattr(instagram_oauth.httpx, "AsyncClient", lambda **kwargs: FakeClient())
    response = client.post("/oauth/instagram/refresh", headers={"X-NOVA-API-Key": "refresh-test-key"})

    assert response.status_code == expected_status
    assert "old-access-secret" not in response.text
    assert "private upstream detail" not in response.text


@pytest.mark.parametrize(
    "payload",
    [
        None,
        [],
        "unexpected",
        {},
        {"access_token": []},
        {"access_token": "new-token", "expires_in": "3600"},
        {"access_token": "new-token", "expires_in": True},
        {"access_token": "new-token", "expires_in": float("inf")},
        {"access_token": "new-token", "expires_in": 10**100},
    ],
)
def test_instagram_refresh_does_not_save_malformed_provider_payload(monkeypatch, payload):
    from app import instagram_oauth

    _configure_instagram_refresh(monkeypatch)
    monkeypatch.setattr(
        instagram_oauth,
        "save_instagram_token",
        lambda *args, **kwargs: pytest.fail("Malformed refresh response must not be saved"),
    )

    class FakeResponse:
        is_error = False
        status_code = 200

        def json(self):
            return payload

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setattr(instagram_oauth.httpx, "AsyncClient", lambda **kwargs: FakeClient())
    response = client.post("/oauth/instagram/refresh", headers={"X-NOVA-API-Key": "refresh-test-key"})

    assert response.status_code == 502
    assert "old-access-secret" not in response.text
    assert "new-token" not in response.text


def test_instagram_refresh_maps_database_read_failure_to_service_unavailable(monkeypatch):
    import psycopg

    from app import instagram_oauth

    monkeypatch.setenv("NOVA_API_KEY", "refresh-test-key")
    configure_oauth(monkeypatch)
    monkeypatch.setattr(
        instagram_oauth,
        "load_latest_instagram_token",
        lambda: (_ for _ in ()).throw(psycopg.OperationalError("private database connection detail")),
    )
    response = client.post("/oauth/instagram/refresh", headers={"X-NOVA-API-Key": "refresh-test-key"})
    assert response.status_code == 503
    assert "private database connection detail" not in response.text


def test_instagram_refresh_reports_save_failure_without_returning_new_token(monkeypatch):
    import psycopg

    from app import instagram_oauth

    _configure_instagram_refresh(monkeypatch)
    monkeypatch.setattr(
        instagram_oauth,
        "save_instagram_token",
        lambda *args, **kwargs: (_ for _ in ()).throw(psycopg.OperationalError("private database error")),
    )

    class FakeResponse:
        is_error = False
        status_code = 200

        def json(self):
            return {"access_token": "new-access-secret", "expires_in": 7200}

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setattr(instagram_oauth.httpx, "AsyncClient", lambda **kwargs: FakeClient())
    response = client.post("/oauth/instagram/refresh", headers={"X-NOVA-API-Key": "refresh-test-key"})

    assert response.status_code == 503
    assert "new-access-secret" not in response.text
    assert "private database error" not in response.text
