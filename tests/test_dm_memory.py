from fastapi.testclient import TestClient

from app.dm_memory import MEMORY_TTL_HOURS
from app.main import app

ADMIN = ("nova-admin", "test-admin-password")

client = TestClient(app)


def test_dm_memory_requires_nova_api_key(monkeypatch):
    monkeypatch.setenv("NOVA_API_KEY", "test-secret")
    response = client.post(
        "/instagram/dm-memory/messages",
        json={"recipient_id": "123456", "role": "user", "message": "Hello"},
    )
    assert response.status_code == 401


def test_dm_memory_fails_closed_without_database(monkeypatch):
    monkeypatch.setenv("NOVA_API_KEY", "test-secret")
    monkeypatch.setenv("NOVA_ADMIN_USERNAME", ADMIN[0])
    monkeypatch.setenv("NOVA_ADMIN_PASSWORD", ADMIN[1])
    monkeypatch.delenv("DATABASE_URL", raising=False)
    response = client.post(
        "/instagram/dm-memory/messages",
        headers={"X-NOVA-API-Key": "test-secret"},
        auth=ADMIN,
        json={"recipient_id": "123456", "role": "user", "message": "Hello"},
    )
    assert response.status_code == 503
    assert response.json()["detail"] == "DATABASE_URL is not configured."


def test_dm_memory_has_twelve_hour_ttl():
    assert MEMORY_TTL_HOURS == 12


def test_dm_memory_rejects_invalid_recipient_id(monkeypatch):
    monkeypatch.setenv("NOVA_API_KEY", "test-secret")
    monkeypatch.setenv("NOVA_ADMIN_USERNAME", ADMIN[0])
    monkeypatch.setenv("NOVA_ADMIN_PASSWORD", ADMIN[1])
    response = client.get(
        "/instagram/dm-memory/bad%2Fid",
        headers={"X-NOVA-API-Key": "test-secret"},
        auth=ADMIN,
    )
    assert response.status_code in (404, 422)



def test_dm_memory_api_key_alone_cannot_read_memory(monkeypatch):
    monkeypatch.setenv("NOVA_API_KEY", "test-secret")
    monkeypatch.setenv("NOVA_ADMIN_USERNAME", ADMIN[0])
    monkeypatch.setenv("NOVA_ADMIN_PASSWORD", ADMIN[1])
    response = client.get(
        "/instagram/dm-memory/123456",
        headers={"X-NOVA-API-Key": "test-secret"},
    )
    assert response.status_code == 401


def test_store_dm_message_sets_expiry_exactly_twelve_hours_after_insert(monkeypatch):
    from datetime import timedelta

    import app.dm_memory as memory

    class Result:
        def fetchone(self):
            return (1,)

    class Connection:
        def __init__(self):
            self.calls = []

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute(self, sql, params=None):
            self.calls.append((" ".join(sql.split()), params))
            return Result()

    connection = Connection()
    monkeypatch.setattr(memory, "_connect", lambda: connection)

    expires_at = memory.store_dm_message("123456", "user", "Hello", message_id="ttl-message-id")

    delete_sql, delete_params = connection.calls[0]
    insert_sql, insert_params = connection.calls[1]
    assert "DELETE FROM nova_instagram_dm_memory WHERE expires_at <= %s" in delete_sql
    assert "ON CONFLICT (message_id)" in insert_sql
    assert expires_at == insert_params[3] + timedelta(hours=12)
    assert insert_params[4] == expires_at
    assert delete_params == (insert_params[3],)


def test_get_dm_memory_filters_expired_rows_in_database_query(monkeypatch):
    from datetime import datetime, timezone

    import app.dm_memory as memory

    now = datetime.now(timezone.utc)
    active_row = {
        "role": "user",
        "message": "Still within the 12-hour window",
        "created_at": now,
        "expires_at": now + memory.MEMORY_TTL,
    }

    class Result:
        def fetchall(self):
            return [active_row]

    class Connection:
        def __init__(self):
            self.calls = []

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def execute(self, sql, params=None):
            self.calls.append((" ".join(sql.split()), params))
            return Result()

    connection = Connection()
    monkeypatch.setattr(memory, "_connect", lambda: connection)

    response = memory.get_dm_memory("123456")

    delete_sql, delete_params = connection.calls[0]
    select_sql, select_params = connection.calls[1]
    assert "expires_at <= %s" in delete_sql
    assert "expires_at > %s" in select_sql
    assert delete_params[0] == select_params[1]
    assert response["ttl_hours"] == 12
    assert response["messages"] == [{
        "role": "user",
        "message": active_row["message"],
        "created_at": active_row["created_at"].isoformat(),
        "expires_at": active_row["expires_at"].isoformat(),
    }]
