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
