from fastapi.testclient import TestClient
import pytest

import app.security as security

from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def authenticated_ai_client(monkeypatch):
    monkeypatch.setenv("NOVA_ADMIN_USERNAME", "test-admin")
    monkeypatch.setenv("NOVA_ADMIN_PASSWORD", "test-password")
    app.dependency_overrides[security.require_master_enabled] = lambda: True
    yield
    app.dependency_overrides.pop(security.require_master_enabled, None)


def test_caption_draft_requires_ai_configuration(monkeypatch):
    monkeypatch.delenv("AI_BASE_URL", raising=False)
    monkeypatch.delenv("AI_API_KEY", raising=False)
    monkeypatch.delenv("AI_MODEL", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("HF_TOKEN", raising=False)

    response = client.post("/ai/generate-caption", json={"topic": "Kerala monsoon", "tone": "funny"}, auth=("test-admin", "test-password"))

    assert response.status_code == 503
    assert "AI providers are unavailable" in response.json()["detail"]


def test_caption_draft_validates_input():
    response = client.post("/ai/generate-caption", json={"topic": "x"}, auth=("test-admin", "test-password"))

    assert response.status_code == 422


def test_caption_draft_is_registered_and_does_not_publish(monkeypatch):
    monkeypatch.setenv("AI_BASE_URL", "https://ai.example.test/v1")
    monkeypatch.setenv("AI_API_KEY", "test-key")
    monkeypatch.setenv("AI_MODEL", "test-model")
    monkeypatch.setenv("AI_PROVIDER_ORDER", "legacy")

    class FakeResponse:
        is_error = False

        def json(self):
            return {"choices": [{"message": {"content": "Mazha + chai = Kerala mood 🌧️☕ #Kerala"}}]}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setattr("app.ai_router.httpx.AsyncClient", FakeClient)

    response = client.post(
        "/ai/generate-caption",
        json={
            "topic": "Kerala monsoon",
            "tone": "funny",
            "language": "Manglish",
            "include_hashtags": True,
        },
        auth=("test-admin", "test-password"),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["caption"].startswith("Mazha")
    assert payload["draft_only"] is True
    assert payload["published_to_instagram"] is False
    assert payload["review_required"] is True
