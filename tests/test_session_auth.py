from fastapi.testclient import TestClient

from app.main import app
import app.session_auth as sessions

client = TestClient(app)


class FakeConnection:
    def __init__(self):
        self.statements = []
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def execute(self, query, params=None):
        self.statements.append((query, params))
        return self


def test_login_status_and_logout_revoke_browser_session(monkeypatch):
    fake = FakeConnection()
    active = set()
    monkeypatch.setenv("NOVA_ADMIN_USERNAME", "test-admin")
    monkeypatch.setenv("NOVA_ADMIN_PASSWORD", "test-password")
    monkeypatch.setenv("NOVA_COOKIE_SECURE", "false")
    monkeypatch.setattr(sessions, "_connect", lambda: fake)

    original_hash = sessions._token_hash
    def execute_and_track(query, params=None):
        result = fake.execute(query, params)
        if query.startswith("INSERT INTO nova_web_sessions"):
            active.add(params[0])
        elif query.startswith("DELETE FROM nova_web_sessions WHERE token_hash"):
            active.discard(params[0])
        return result
    fake.execute = execute_and_track

    monkeypatch.setattr(
        sessions, "session_username",
        lambda token: "test-admin" if token and original_hash(token) in active else None,
    )

    bad = client.post("/auth/login", json={"username": "test-admin", "password": "wrong"})
    assert bad.status_code == 401

    login = client.post("/auth/login", json={"username": "test-admin", "password": "test-password"})
    assert login.status_code == 200
    assert login.json()["authenticated"] is True
    assert sessions.COOKIE_NAME in client.cookies

    status = client.get("/auth/status")
    assert status.status_code == 200
    assert status.json() == {"authenticated": True, "username": "test-admin"}

    logout = client.post("/auth/logout")
    assert logout.status_code == 200
    assert logout.json()["authenticated"] is False

    status_after_logout = client.get("/auth/status")
    assert status_after_logout.status_code == 200
    assert status_after_logout.json() == {"authenticated": False, "username": None}


def test_studio_page_contains_login_status_and_sign_out_controls():
    response = client.get("/app")
    assert response.status_code == 200
    assert 'id="loginForm"' in response.text
    assert 'id="authStatus"' in response.text
    assert 'id="signOutButton"' in response.text
