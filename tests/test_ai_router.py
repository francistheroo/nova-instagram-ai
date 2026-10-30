import pytest

from app import ai_router


class FakeResponse:
    def __init__(self, status_code=200, content="answer"):
        self.status_code = status_code
        self.is_error = status_code >= 400
        self._content = content

    def json(self):
        return {"choices": [{"message": {"content": self._content}}]}


def test_router_fails_over_after_rate_limit(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER_ORDER", "gemini,groq")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-test")
    monkeypatch.setenv("GROQ_API_KEY", "groq-test")
    monkeypatch.delenv("AI_BASE_URL", raising=False)
    calls = []

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, **kwargs):
            calls.append(url)
            if "generativelanguage" in url:
                return FakeResponse(429, "quota")
            return FakeResponse(200, "Groq answer")

    monkeypatch.setattr(ai_router.httpx, "AsyncClient", FakeClient)

    import asyncio
    content, provider, model = asyncio.run(ai_router.chat_completion([{"role": "user", "content": "Hi"}]))

    assert content == "Groq answer"
    assert provider == "groq"
    assert model == "openai/gpt-oss-20b"
    assert len(calls) == 2


def test_router_reports_no_configured_provider(monkeypatch):
    for name in ("GEMINI_API_KEY", "GROQ_API_KEY", "HF_TOKEN", "AI_BASE_URL", "AI_API_KEY", "AI_MODEL"):
        monkeypatch.delenv(name, raising=False)
    assert ai_router.configured_provider_names() == []


def test_router_returns_unavailable_when_every_provider_is_rate_limited(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER_ORDER", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "groq-test")
    monkeypatch.delenv("AI_BASE_URL", raising=False)

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, *args, **kwargs):
            return FakeResponse(429, "quota")

    monkeypatch.setattr(ai_router.httpx, "AsyncClient", FakeClient)

    import asyncio
    with pytest.raises(ai_router.AIProviderUnavailable):
        asyncio.run(ai_router.chat_completion([{"role": "user", "content": "Hi"}]))
