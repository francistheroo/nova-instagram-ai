import pytest

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
