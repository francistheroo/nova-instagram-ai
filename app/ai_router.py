"""Shared multi-provider AI routing with quota-aware failover.

Only configured providers are called. HTTP 429, transient 5xx/network failures,
and malformed provider responses move to the next configured provider.
"""
import os
import time
from typing import Any

import httpx


_provider_cooldowns: dict[str, float] = {}


class AIProviderUnavailable(RuntimeError):
    """Raised when no configured AI provider can complete a request."""


def _configured_providers() -> list[dict[str, str]]:
    providers: dict[str, dict[str, str]] = {}
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    if gemini_key:
        providers["gemini"] = {
            "name": "gemini",
            "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
            "api_key": gemini_key,
            "model": os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip(),
        }
    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    if groq_key:
        providers["groq"] = {
            "name": "groq",
            "base_url": "https://api.groq.com/openai/v1",
            "api_key": groq_key,
            "model": os.getenv("GROQ_MODEL", "openai/gpt-oss-20b").strip(),
        }
    hf_key = os.getenv("HF_TOKEN", "").strip()
    if hf_key:
        providers["huggingface"] = {
            "name": "huggingface",
            "base_url": "https://router.huggingface.co/v1",
            "api_key": hf_key,
            "model": os.getenv("HF_CHAT_MODEL", "openai/gpt-oss-120b:fastest").strip(),
        }
    legacy = {
        "name": "legacy",
        "base_url": os.getenv("AI_BASE_URL", "").rstrip("/"),
        "api_key": os.getenv("AI_API_KEY", "").strip(),
        "model": os.getenv("AI_MODEL", "").strip(),
    }
    if all(legacy.values()):
        providers["legacy"] = legacy

    order = [item.strip().lower() for item in os.getenv(
        "AI_PROVIDER_ORDER", "gemini,groq,huggingface,legacy"
    ).split(",") if item.strip()]
    return [providers[name] for name in order if name in providers]


def configured_provider_names() -> list[str]:
    """Return configured provider identifiers without exposing credentials."""
    return [provider["name"] for provider in _configured_providers()]


async def chat_completion(
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.7,
    timeout: float = 45.0,
) -> tuple[str, str, str]:
    """Return (content, provider_name, model_name), failing over on provider errors."""
    providers = _configured_providers()
    if not providers:
        raise AIProviderUnavailable("No AI text provider is configured.")
    failures: list[str] = []
    for provider in providers:
        if _provider_cooldowns.get(provider['name'], 0) > time.monotonic():
            failures.append(provider['name'] + ':cooldown')
            continue
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    f"{provider['base_url']}/chat/completions",
                    headers={"Authorization": f"Bearer {provider['api_key']}"},
                    json={
                        "model": provider["model"],
                        "messages": messages,
                        "temperature": temperature,
                    },
                )
            if response.is_error:
                failures.append(f"{provider['name']}:{response.status_code}")
                if response.status_code == 429:
                    try:
                        cooldown = max(30, min(900, int(getattr(response, 'headers', {}).get('Retry-After', '60'))))
                    except (ValueError, TypeError):
                        cooldown = 60
                    _provider_cooldowns[provider['name']] = time.monotonic() + cooldown
                elif response.status_code >= 500:
                    _provider_cooldowns[provider['name']] = time.monotonic() + 15
                continue
            payload: Any = response.json()
            content = payload["choices"][0]["message"]["content"]
            if not isinstance(content, str) or not content.strip():
                failures.append(f"{provider['name']}:invalid_response")
                continue
            return content.strip(), provider["name"], provider["model"]
        except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError):
            failures.append(f"{provider['name']}:unavailable")
            continue
    raise AIProviderUnavailable("All configured AI providers are unavailable: " + ", ".join(failures))
