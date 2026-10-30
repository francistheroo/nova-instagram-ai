from contextlib import nullcontext

import pytest

from fastapi.testclient import TestClient

from app.main import app

@pytest.fixture(autouse=True)
def bypass_shared_refresh_lock_for_unit_tests(monkeypatch):
    """Unit tests mock token storage/provider calls and do not need PostgreSQL."""
    from app import canva_oauth

    monkeypatch.setattr(canva_oauth, "canva_refresh_lock", lambda: nullcontext())

client = TestClient(app)


def test_canva_oauth_start_requires_server_configuration(monkeypatch):
    monkeypatch.setenv("NOVA_ADMIN_USERNAME", "nova-admin")
    monkeypatch.setenv("NOVA_ADMIN_PASSWORD", "test-admin-password")
    monkeypatch.delenv("CANVA_CLIENT_ID", raising=False)
    monkeypatch.delenv("CANVA_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("CANVA_REDIRECT_URI", raising=False)
    response = client.get("/oauth/canva/start", auth=("nova-admin", "test-admin-password"))
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
    assert payload["token_refresh_implemented"] is True


def test_health_reports_canva_oauth_implementation():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["canva_oauth_implemented"] is True
    assert response.json()["canva_token_refresh_implemented"] is True


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


def test_canva_callback_exchanges_code_with_pkce_and_keeps_tokens_server_side(monkeypatch):
    from app import canva_oauth
    from app.oauth_security import create_oauth_state, validate_oauth_state

    monkeypatch.setenv("CANVA_CLIENT_ID", "test-client")
    monkeypatch.setenv("CANVA_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("CANVA_REDIRECT_URI", "https://testserver/oauth/canva/callback")
    monkeypatch.setenv("OAUTH_STATE_SECRET", "s" * 48)
    state = create_oauth_state()
    nonce = validate_oauth_state(state)["nonce"]
    monkeypatch.setattr(canva_oauth, "consume_oauth_state", lambda value: value == nonce)

    saved = []

    def save_tokens(token_payload, *, expires_at):
        saved.append((token_payload, expires_at))

    monkeypatch.setattr(canva_oauth, "save_canva_tokens", save_tokens)

    class FakeResponse:
        is_error = False

        def json(self):
            return {
                "access_token": "canva-access-secret",
                "refresh_token": "canva-refresh-secret",
                "expires_in": 3600,
                "user_id": "canva-user",
            }

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, *, auth, data, headers):
            assert url == "https://api.canva.com/rest/v1/oauth/token"
            assert auth == ("test-client", "test-client-secret")
            assert data["grant_type"] == "authorization_code"
            assert data["code"] == "fake-canva-code"
            assert data["code_verifier"] == "test-pkce-verifier"
            assert headers["Content-Type"] == "application/x-www-form-urlencoded"
            return FakeResponse()

    monkeypatch.setattr(canva_oauth.httpx, "AsyncClient", lambda **kwargs: FakeClient())
    response = client.get(
        "/oauth/canva/callback",
        params={"code": "fake-canva-code", "state": state},
        cookies={
            "nova_canva_oauth_state": state,
            "nova_canva_pkce_verifier": "test-pkce-verifier",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/?canva_connected=pending_verification"
    assert len(saved) == 1
    assert saved[0][0]["access_token"] == "canva-access-secret"
    assert saved[0][0]["refresh_token"] == "canva-refresh-secret"
    assert saved[0][1] is not None
    assert "canva-access-secret" not in response.text
    assert "canva-refresh-secret" not in response.text
    assert "canva-access-secret" not in response.headers["location"]
    cookies = " ".join(response.headers.get_list("set-cookie")).lower()
    assert "nova_canva_oauth_state" in cookies
    assert "nova_canva_pkce_verifier" in cookies
    assert cookies.count("max-age=0") == 2


def test_canva_callback_rejects_replayed_persisted_state_before_exchange(monkeypatch):
    from app import canva_oauth
    from app.oauth_security import create_oauth_state

    monkeypatch.setenv("CANVA_CLIENT_ID", "test-client")
    monkeypatch.setenv("CANVA_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("CANVA_REDIRECT_URI", "https://testserver/oauth/canva/callback")
    monkeypatch.setenv("OAUTH_STATE_SECRET", "s" * 48)
    state = create_oauth_state()
    monkeypatch.setattr(canva_oauth, "consume_oauth_state", lambda nonce: False)

    class NoExchangeClient:
        async def __aenter__(self):
            pytest.fail("A replayed Canva state must not exchange the code")

        async def __aexit__(self, *args):
            return False

    monkeypatch.setattr(canva_oauth.httpx, "AsyncClient", lambda **kwargs: NoExchangeClient())
    response = client.get(
        "/oauth/canva/callback",
        params={"code": "fake-canva-code", "state": state},
        cookies={
            "nova_canva_oauth_state": state,
            "nova_canva_pkce_verifier": "test-pkce-verifier",
        },
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
def test_canva_callback_rejects_oversized_query_values(parameter, value):
    response = client.get("/oauth/canva/callback", params={parameter: value})
    assert response.status_code == 422


@pytest.mark.parametrize(
    "token_payload",
    [
        None,
        [],
        "unexpected",
        {},
        {"access_token": []},
        {"access_token": "canva-token", "expires_in": "3600"},
        {"access_token": "canva-token", "expires_in": True},
        {"access_token": "canva-token", "expires_in": float("nan")},
        {"access_token": "canva-token", "expires_in": 10**100},
    ],
)
def test_canva_callback_rejects_malformed_token_payload(monkeypatch, token_payload):
    from app import canva_oauth
    from app.oauth_security import create_oauth_state, validate_oauth_state

    monkeypatch.setenv("CANVA_CLIENT_ID", "test-client")
    monkeypatch.setenv("CANVA_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("CANVA_REDIRECT_URI", "https://testserver/oauth/canva/callback")
    monkeypatch.setenv("OAUTH_STATE_SECRET", "s" * 48)
    state = create_oauth_state()
    nonce = validate_oauth_state(state)["nonce"]
    monkeypatch.setattr(canva_oauth, "consume_oauth_state", lambda value: value == nonce)
    monkeypatch.setattr(
        canva_oauth,
        "save_canva_tokens",
        lambda *args, **kwargs: pytest.fail("Malformed token response must not be stored"),
    )

    class FakeResponse:
        is_error = False

        def json(self):
            return token_payload

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setattr(canva_oauth.httpx, "AsyncClient", lambda **kwargs: FakeClient())
    response = client.get(
        "/oauth/canva/callback",
        params={"code": "fake-canva-code", "state": state},
        cookies={
            "nova_canva_oauth_state": state,
            "nova_canva_pkce_verifier": "test-pkce-verifier",
        },
        follow_redirects=False,
    )

    assert response.status_code == 502
    assert "canva-token" not in response.text
    assert "test-client-secret" not in response.text


@pytest.mark.parametrize(
    "replacement",
    [
        None,
        [],
        "unexpected",
        {},
        {"access_token": [], "refresh_token": "new-refresh"},
        {"access_token": "new-access", "refresh_token": []},
        {"access_token": "new-access", "refresh_token": "new-refresh", "expires_in": "3600"},
        {"access_token": "new-access", "refresh_token": "new-refresh", "expires_in": float("inf")},
    ],
)
def test_canva_refresh_rejects_malformed_provider_response(monkeypatch, replacement):
    from app import canva_oauth

    monkeypatch.setenv("NOVA_API_KEY", "test-secret")
    monkeypatch.setenv("CANVA_CLIENT_ID", "test-client")
    monkeypatch.setenv("CANVA_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("CANVA_REDIRECT_URI", "https://testserver/oauth/canva/callback")
    monkeypatch.setattr(
        canva_oauth,
        "load_latest_canva_tokens",
        lambda: {
            "user_id": "canva-user",
            "access_token": "old-access",
            "refresh_token": "old-refresh",
        },
    )
    monkeypatch.setattr(canva_oauth, "mark_canva_refresh_pending", lambda account_key: None)
    monkeypatch.setattr(canva_oauth, "clear_canva_refresh_pending", lambda account_key: None)
    monkeypatch.setattr(
        canva_oauth,
        "save_canva_tokens",
        lambda *args, **kwargs: pytest.fail("Malformed replacement token must not be stored"),
    )

    class FakeResponse:
        is_error = False

        def json(self):
            return replacement

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setattr(canva_oauth.httpx, "AsyncClient", lambda **kwargs: FakeClient())
    response = client.post("/oauth/canva/refresh", headers={"X-NOVA-API-Key": "test-secret"})

    assert response.status_code == 502
    assert "old-refresh" not in response.text
    assert "test-client-secret" not in response.text


def _configure_canva_refresh(monkeypatch, current=None):
    from app import canva_oauth

    monkeypatch.setenv("NOVA_API_KEY", "canva-refresh-test-key")
    monkeypatch.setenv("CANVA_CLIENT_ID", "canva-client")
    monkeypatch.setenv("CANVA_CLIENT_SECRET", "canva-client-secret")
    monkeypatch.setenv("CANVA_REDIRECT_URI", "https://testserver/oauth/canva/callback")
    if current is None:
        current = {
            "user_id": "canva-user",
            "access_token": "old-canva-access-secret",
            "refresh_token": "old-canva-refresh-secret",
            "expires_at": None,
        }
    monkeypatch.setattr(canva_oauth, "load_latest_canva_tokens", lambda: current)
    monkeypatch.setattr(canva_oauth, "mark_canva_refresh_pending", lambda account_key: None)
    monkeypatch.setattr(canva_oauth, "clear_canva_refresh_pending", lambda account_key: None)
    return canva_oauth, current


def test_canva_refresh_rotates_token_and_preserves_account_id(monkeypatch):
    from datetime import datetime, timezone

    from app import canva_oauth

    _configure_canva_refresh(monkeypatch)
    saved = []
    monkeypatch.setattr(
        canva_oauth,
        "save_canva_tokens",
        lambda bundle, *, expires_at: saved.append((bundle.copy(), expires_at)),
    )

    class FakeResponse:
        is_error = False
        status_code = 200

        def json(self):
            return {
                "access_token": "new-canva-access-secret",
                "refresh_token": "new-canva-refresh-secret",
                "expires_in": 3600,
            }

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, *, auth, data, headers):
            assert url == "https://api.canva.com/rest/v1/oauth/token"
            assert auth == ("canva-client", "canva-client-secret")
            assert data == {
                "grant_type": "refresh_token",
                "refresh_token": "old-canva-refresh-secret",
            }
            assert headers["Content-Type"] == "application/x-www-form-urlencoded"
            return FakeResponse()

    monkeypatch.setattr(canva_oauth.httpx, "AsyncClient", lambda **kwargs: FakeClient())
    response = client.post("/oauth/canva/refresh", headers={"X-NOVA-API-Key": "canva-refresh-test-key"})

    assert response.status_code == 200
    assert response.json()["refreshed"] is True
    assert response.json()["token_returned"] is False
    assert saved[0][0]["user_id"] == "canva-user"
    assert saved[0][0]["access_token"] == "new-canva-access-secret"
    assert saved[0][0]["refresh_token"] == "new-canva-refresh-secret"
    assert saved[0][1] > datetime.now(timezone.utc)
    assert "new-canva-access-secret" not in response.text
    assert "new-canva-refresh-secret" not in response.text
    assert "old-canva-refresh-secret" not in response.text


@pytest.mark.parametrize(
    "stored",
    [
        [],
        "unexpected",
        {},
        {"user_id": "canva-user", "refresh_token": ""},
        {"user_id": "canva-user", "refresh_token": []},
    ],
)
def test_canva_refresh_rejects_malformed_stored_refresh_credentials(monkeypatch, stored):
    from app import canva_oauth

    _configure_canva_refresh(monkeypatch, stored)

    class NoRequestClient:
        async def __aenter__(self):
            pytest.fail("Malformed stored credentials must not call Canva")

        async def __aexit__(self, *args):
            return False

    monkeypatch.setattr(canva_oauth.httpx, "AsyncClient", lambda **kwargs: NoRequestClient())
    response = client.post("/oauth/canva/refresh", headers={"X-NOVA-API-Key": "canva-refresh-test-key"})

    assert response.status_code == 503
    assert "old-canva-refresh-secret" not in response.text


@pytest.mark.parametrize(
    "provider_status,expected_status",
    [(400, 409), (401, 409), (403, 409), (429, 503), (500, 502), (503, 502)],
)
def test_canva_refresh_classifies_provider_failures_without_leaking_token(
    monkeypatch, provider_status, expected_status
):
    from app import canva_oauth

    _configure_canva_refresh(monkeypatch)

    class FakeResponse:
        is_error = True
        status_code = provider_status

        def json(self):
            return {"error": {"message": "private Canva provider detail"}}

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setattr(canva_oauth.httpx, "AsyncClient", lambda **kwargs: FakeClient())
    response = client.post("/oauth/canva/refresh", headers={"X-NOVA-API-Key": "canva-refresh-test-key"})

    assert response.status_code == expected_status
    assert "old-canva-refresh-secret" not in response.text
    assert "private Canva provider detail" not in response.text


def test_canva_refresh_maps_database_read_failure_to_service_unavailable(monkeypatch):
    import psycopg

    from app import canva_oauth

    monkeypatch.setenv("NOVA_API_KEY", "canva-refresh-test-key")
    monkeypatch.setenv("CANVA_CLIENT_ID", "canva-client")
    monkeypatch.setenv("CANVA_CLIENT_SECRET", "canva-client-secret")
    monkeypatch.setenv("CANVA_REDIRECT_URI", "https://testserver/oauth/canva/callback")
    monkeypatch.setattr(
        canva_oauth,
        "load_latest_canva_tokens",
        lambda: (_ for _ in ()).throw(psycopg.OperationalError("private Canva database error")),
    )
    response = client.post("/oauth/canva/refresh", headers={"X-NOVA-API-Key": "canva-refresh-test-key"})

    assert response.status_code == 503
    assert "private Canva database error" not in response.text


def test_canva_refresh_warns_if_rotated_token_bundle_cannot_be_saved(monkeypatch):
    import psycopg

    from app import canva_oauth

    _configure_canva_refresh(monkeypatch)
    monkeypatch.setattr(
        canva_oauth,
        "save_canva_tokens",
        lambda *args, **kwargs: (_ for _ in ()).throw(psycopg.OperationalError("private database error")),
    )

    class FakeResponse:
        is_error = False
        status_code = 200

        def json(self):
            return {
                "access_token": "new-canva-access-secret",
                "refresh_token": "new-canva-refresh-secret",
                "expires_in": 3600,
            }

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setattr(canva_oauth.httpx, "AsyncClient", lambda **kwargs: FakeClient())
    response = client.post("/oauth/canva/refresh", headers={"X-NOVA-API-Key": "canva-refresh-test-key"})

    assert response.status_code == 503
    assert "old refresh token" in response.json()["detail"].lower()
    assert "new-canva-access-secret" not in response.text
    assert "new-canva-refresh-secret" not in response.text
    assert "private database error" not in response.text


def test_canva_refresh_returns_conflict_when_another_worker_holds_lock(monkeypatch):
    from contextlib import contextmanager

    from app import canva_oauth
    from app.canva_store import CanvaRefreshInProgress

    _configure_canva_refresh(monkeypatch)

    @contextmanager
    def busy_lock():
        raise CanvaRefreshInProgress("already refreshing")
        yield

    monkeypatch.setattr(canva_oauth, "canva_refresh_lock", busy_lock)
    monkeypatch.setattr(
        canva_oauth,
        "load_latest_canva_tokens",
        lambda: pytest.fail("A busy refresh lock must not read or rotate the token"),
    )

    response = client.post(
        "/oauth/canva/refresh",
        headers={"X-NOVA-API-Key": "canva-refresh-test-key"},
    )

    assert response.status_code == 409
    assert "already in progress" in response.json()["detail"]


def test_canva_refresh_requires_database_lock_configuration(monkeypatch):
    from contextlib import contextmanager

    from app import canva_oauth
    from app.canva_store import CanvaStoreError

    _configure_canva_refresh(monkeypatch)

    @contextmanager
    def unavailable_lock():
        raise CanvaStoreError("private connection detail")
        yield

    monkeypatch.setattr(canva_oauth, "canva_refresh_lock", unavailable_lock)
    response = client.post(
        "/oauth/canva/refresh",
        headers={"X-NOVA-API-Key": "canva-refresh-test-key"},
    )

    assert response.status_code == 503
    assert "private connection detail" not in response.text


def test_canva_callback_maps_token_storage_failure_to_safe_503(monkeypatch):
    import psycopg

    from app import canva_oauth
    from app.oauth_security import create_oauth_state, validate_oauth_state

    monkeypatch.setenv("CANVA_CLIENT_ID", "test-client")
    monkeypatch.setenv("CANVA_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("CANVA_REDIRECT_URI", "https://testserver/oauth/canva/callback")
    monkeypatch.setenv("OAUTH_STATE_SECRET", "s" * 48)
    state = create_oauth_state()
    nonce = validate_oauth_state(state)["nonce"]
    monkeypatch.setattr(canva_oauth, "consume_oauth_state", lambda value: value == nonce)
    monkeypatch.setattr(
        canva_oauth,
        "save_canva_tokens",
        lambda *args, **kwargs: (_ for _ in ()).throw(psycopg.OperationalError("private database detail")),
    )

    class FakeResponse:
        is_error = False

        def json(self):
            return {
                "access_token": "canva-access-secret",
                "refresh_token": "canva-refresh-secret",
                "expires_in": 3600,
                "user_id": "canva-user",
            }

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setattr(canva_oauth.httpx, "AsyncClient", lambda **kwargs: FakeClient())
    response = client.get(
        "/oauth/canva/callback",
        params={"code": "fake-canva-code", "state": state},
        cookies={
            "nova_canva_oauth_state": state,
            "nova_canva_pkce_verifier": "test-pkce-verifier",
        },
        follow_redirects=False,
    )

    assert response.status_code == 503
    assert "private database detail" not in response.text
    assert "canva-access-secret" not in response.text
    assert "canva-refresh-secret" not in response.text
    assert "do not retry this authorization code" in response.json()["detail"]


def test_canva_callback_maps_raw_postgres_state_error_to_503(monkeypatch):
    import psycopg

    from app import canva_oauth
    from app.oauth_security import create_oauth_state

    monkeypatch.setenv("CANVA_CLIENT_ID", "test-client")
    monkeypatch.setenv("CANVA_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("CANVA_REDIRECT_URI", "https://testserver/oauth/canva/callback")
    monkeypatch.setenv("OAUTH_STATE_SECRET", "s" * 48)
    state = create_oauth_state()

    def unavailable_state_storage(_nonce):
        raise psycopg.OperationalError("private database failure")

    monkeypatch.setattr(canva_oauth, "consume_oauth_state", unavailable_state_storage)
    response = client.get(
        "/oauth/canva/callback",
        params={"code": "fake-canva-code", "state": state},
        cookies={
            "nova_canva_oauth_state": state,
            "nova_canva_pkce_verifier": "test-pkce-verifier",
        },
        follow_redirects=False,
    )

    assert response.status_code == 503
    assert "private database failure" not in response.text


def test_canva_api_maps_raw_database_failure_to_service_unavailable(monkeypatch):
    import psycopg

    from app import canva_api

    monkeypatch.setenv("NOVA_API_KEY", "test-secret")
    monkeypatch.setattr(
        canva_api,
        "load_latest_canva_tokens",
        lambda: (_ for _ in ()).throw(psycopg.OperationalError("private database endpoint")),
    )

    response = client.get("/canva/designs", headers={"X-NOVA-API-Key": "test-secret"})

    assert response.status_code == 503
    assert "private database endpoint" not in response.text
