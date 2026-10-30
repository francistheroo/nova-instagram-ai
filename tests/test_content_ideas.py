import json

from fastapi.testclient import TestClient
import pytest

import app.security as security

from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def authenticated_ai_client(monkeypatch):
    monkeypatch.setenv("NOVA_USER_USERNAME", "test-user")
    monkeypatch.setenv("NOVA_USER_PASSWORD", "test-password")
    app.dependency_overrides[security.require_master_enabled] = lambda: True
    yield
    app.dependency_overrides.pop(security.require_master_enabled, None)


def test_content_ideas_requires_ai_configuration(monkeypatch):
    monkeypatch.delenv("AI_BASE_URL", raising=False)
    monkeypatch.delenv("AI_API_KEY", raising=False)
    monkeypatch.delenv("AI_MODEL", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("HF_TOKEN", raising=False)

    response = client.post("/ai/content-ideas", json={"topic": "Kerala food"}, auth=("test-user", "test-password"))

    assert response.status_code == 503
    assert "AI providers are unavailable" in response.json()["detail"]


def test_content_ideas_rejects_out_of_range_count():
    response = client.post("/ai/content-ideas", json={"topic": "Kerala food", "count": 11}, auth=("test-user", "test-password"))

    assert response.status_code == 422


def test_content_ideas_returns_review_only_ideas(monkeypatch):
    monkeypatch.setenv("AI_BASE_URL", "https://ai.example.test/v1")
    monkeypatch.setenv("AI_API_KEY", "test-key")
    monkeypatch.setenv("AI_MODEL", "test-model")
    monkeypatch.setenv("AI_PROVIDER_ORDER", "legacy")

    ideas = [
        {
            "title": "Kerala snack challenge",
            "format": "Reel",
            "hook": "Guess the snack!",
            "concept": "Show three local snacks and reveal the names.",
            "call_to_action": "Comment your favourite.",
        },
        {
            "title": "Tea-time favourites",
            "format": "Carousel",
            "hook": "Chaya time!",
            "concept": "Share a simple list of tea-time pairings.",
            "call_to_action": "Save for later.",
        },
    ]

    class FakeResponse:
        is_error = False

        def json(self):
            return {"choices": [{"message": {"content": json.dumps({"ideas": ideas})}}]}

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

    response = client.post("/ai/content-ideas", json={"topic": "Kerala food", "count": 2}, auth=("test-user", "test-password"))

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 2
    assert payload["ideas"][0]["title"] == "Kerala snack challenge"
    assert payload["draft_only"] is True
    assert payload["scheduled"] is False
    assert payload["published_to_instagram"] is False
    assert payload["live_trend_data_used"] is False


def test_content_ideas_rejects_malformed_ai_output(monkeypatch):
    monkeypatch.setenv("AI_BASE_URL", "https://ai.example.test/v1")
    monkeypatch.setenv("AI_API_KEY", "test-key")
    monkeypatch.setenv("AI_MODEL", "test-model")
    monkeypatch.setenv("AI_PROVIDER_ORDER", "legacy")

    class FakeResponse:
        is_error = False

        def json(self):
            return {"choices": [{"message": {"content": "not valid JSON"}}]}

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

    response = client.post("/ai/content-ideas", json={"topic": "Kerala food", "count": 2})

    assert response.status_code == 502
    assert "invalid content ideas" in response.json()["detail"]
