import os
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.personality import NOVA_SYSTEM_PROMPT

router = APIRouter()


class CaptionDraftRequest(BaseModel):
    topic: str = Field(min_length=3, max_length=1000)
    tone: str = Field(default="funny and engaging", min_length=2, max_length=100)
    language: str = Field(default="Manglish", min_length=2, max_length=30)
    audience: Optional[str] = Field(default=None, max_length=200)
    include_hashtags: bool = True


@router.post("/ai/generate-caption")
async def generate_caption(body: CaptionDraftRequest):
    """Generate an Instagram caption draft only; this endpoint never publishes."""
    base_url = os.getenv("AI_BASE_URL", "").rstrip("/")
    api_key = os.getenv("AI_API_KEY", "")
    model = os.getenv("AI_MODEL", "")
    if not (base_url and api_key and model):
        raise HTTPException(
            status_code=503,
            detail="AI caption generation is not configured. Set AI_BASE_URL, AI_API_KEY, and AI_MODEL.",
        )

    requirements = [
        f"Topic: {body.topic}",
        f"Tone: {body.tone}",
        f"Output language: {body.language}",
        f"Include relevant hashtags: {'yes' if body.include_hashtags else 'no'}",
    ]
    if body.audience:
        requirements.append(f"Intended audience: {body.audience}")
    requirements.append(
        "Write one original Instagram caption, ready for the user to review. "
        "Do not claim facts about the topic unless supplied. Do not include a preamble."
    )

    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post(
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": NOVA_SYSTEM_PROMPT},
                        {"role": "user", "content": "\\n".join(requirements)},
                    ],
                    "temperature": 0.85,
                },
            )
            if response.is_error:
                raise HTTPException(status_code=502, detail="AI provider request failed. Check provider settings.")
            payload = response.json()
            caption = payload["choices"][0]["message"]["content"]
            if not isinstance(caption, str) or not caption.strip():
                raise ValueError("Empty caption")
    except HTTPException:
        raise
    except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError):
        raise HTTPException(status_code=502, detail="AI provider returned an invalid caption response.")

    return {
        "caption": caption.strip(),
        "mode": "ai",
        "draft_only": True,
        "published_to_instagram": False,
        "review_required": True,
    }
