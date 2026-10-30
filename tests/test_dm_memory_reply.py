from fastapi.testclient import TestClient

import app.dm_memory as memory
from app.main import app

client = TestClient(app)


class _FakeResult:
    def fetchall(self):
        return [{"role": "user", "message": "Earlier context"}]


class _FakeConnection:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, *args):
        return _FakeResult()


def test_dm_reply_preview_requires_api_key(monkeypatch):
    monkeypatch.setenv("NOVA_API_KEY", "test-secret")
    response = client.post(
        "/instagram/dm-memory/preview-reply",
        json={"recipient_id": "123456", "message": "What did I say?"},
    )
    assert response.status_code == 401


def test_dm_reply_preview_uses_memory_but_needs_ai_config(monkeypatch):
    monkeypatch.setenv("NOVA_API_KEY", "test-secret")
    monkeypatch.setenv("DATABASE_URL", "postgresql://fake")
    monkeypatch.delenv("AI_BASE_URL", raising=False)
    monkeypatch.delenv("AI_API_KEY", raising=False)
    monkeypatch.delenv("AI_MODEL", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.setattr(memory, "_connect", lambda: _FakeConnection())
    response = client.post(
        "/instagram/dm-memory/preview-reply",
        headers={"X-NOVA-API-Key": "test-secret"},
        json={"recipient_id": "123456", "message": "What did I say?"},
    )
    assert response.status_code == 503
    assert "AI providers are unavailable" in response.json()["detail"]
