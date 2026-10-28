from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_caption_draft_requires_ai_configuration(monkeypatch):
    monkeypatch.delenv("AI_BASE_URL", raising=False)
    monkeypatch.delenv("AI_API_KEY", raising=False)
    monkeypatch.delenv("AI_MODEL", raising=False)

    response = client.post("/ai/generate-caption", json={"topic": "Kerala monsoon", "tone": "funny"})

    assert response.status_code == 503
    assert "AI caption generation is not configured" in response.json()["detail"]


def test_caption_draft_validates_input():
    response = client.post("/ai/generate-caption", json={"topic": "x"})

    assert response.status_code == 422


def test_caption_draft_is_registered_and_does_not_publish(monkeypatch):
    monkeypatch.setenv("AI_BASE_URL", "https://ai.example.test/v1")
    monkeypatch.setenv("AI_API_KEY", "test-key")
    monkeypatch.setenv("AI_MODEL", "test-model")

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

    monkeypatch.setattr("app.ai_caption.httpx.AsyncClient", FakeClient)

    response = client.post(
        "/ai/generate-caption",
        json={
            "topic": "Kerala monsoon",
            "tone": "funny",
            "language": "Manglish",
            "include_hashtags": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["caption"].startswith("Mazha")
    assert payload["draft_only"] is True
    assert payload["published_to_instagram"] is False
    assert payload["review_required"] is True
