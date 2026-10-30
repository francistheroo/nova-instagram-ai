import os
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.personality import NOVA_SYSTEM_PROMPT
from app.ai_router import AIProviderUnavailable, chat_completion

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
        caption, provider, model = await chat_completion(
            [
                {"role": "system", "content": NOVA_SYSTEM_PROMPT},
                {"role": "user", "content": "\\n".join(requirements)},
            ],
            temperature=0.85,
        )
    except AIProviderUnavailable:
        raise HTTPException(status_code=503, detail="All configured AI providers are unavailable or rate-limited. Try again later.") from None

    return {
        "caption": caption.strip(),
        "mode": "ai",
        "provider": provider,
        "model": model,
        "draft_only": True,
        "published_to_instagram": False,
        "review_required": True,
    }
