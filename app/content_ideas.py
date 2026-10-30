import json
import os
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.personality import NOVA_SYSTEM_PROMPT
from app.ai_router import AIProviderUnavailable, chat_completion

router = APIRouter()


class ContentIdeasRequest(BaseModel):
    topic: str = Field(min_length=3, max_length=1000)
    count: int = Field(default=5, ge=1, le=10)
    format: str = Field(default="mix of Reels, carousels, and photo posts", min_length=2, max_length=120)
    language: str = Field(default="Manglish", min_length=2, max_length=30)
    audience: Optional[str] = Field(default=None, max_length=200)


@router.post("/ai/content-ideas")
async def generate_content_ideas(body: ContentIdeasRequest):
    """Generate original content ideas; no scheduling or publishing occurs."""
    brief = [
        f"Topic or niche: {body.topic}",
        f"Number of ideas: {body.count}",
        f"Preferred format: {body.format}",
        f"Language: {body.language}",
        "Create original ideas, not copies of named creators. Do not claim these are live or trending topics.",
        "Return only valid JSON in this shape: "
        '{"ideas":[{"title":"short title","format":"Reel, carousel, or photo","hook":"opening hook",'
        '"concept":"one-sentence concept","call_to_action":"optional CTA"}]}',
        f"Return exactly {body.count} ideas. Keep each item concise and practical.",
    ]
    if body.audience:
        brief.append(f"Intended audience: {body.audience}")
    try:
        raw, provider, model = await chat_completion(
            [
                {"role": "system", "content": NOVA_SYSTEM_PROMPT + "\\nFor this task, follow the requested JSON output format exactly."},
                {"role": "user", "content": "\n".join(brief)},
            ],
            temperature=0.9,
        )
        parsed = json.loads(raw.strip())
        ideas = parsed.get("ideas") if isinstance(parsed, dict) else None
        if not isinstance(ideas, list) or len(ideas) != body.count:
            raise ValueError("Invalid ideas array")
        for idea in ideas:
            if not isinstance(idea, dict) or not all(
                isinstance(idea.get(key), str) and idea[key].strip()
                for key in ("title", "format", "hook", "concept")
            ):
                raise ValueError("Invalid idea item")
            idea.setdefault("call_to_action", "")
            if not isinstance(idea["call_to_action"], str):
                raise ValueError("Invalid call to action")
    except AIProviderUnavailable:
        raise HTTPException(status_code=503, detail="All configured AI providers are unavailable or rate-limited. Try again later.") from None
    except (ValueError, TypeError, json.JSONDecodeError):
        raise HTTPException(status_code=502, detail="AI providers returned invalid content ideas. Please try again.") from None

    return {
        "ideas": ideas,
        "count": len(ideas),
        "provider": provider,
        "model": model,
        "draft_only": True,
        "scheduled": False,
        "published_to_instagram": False,
        "live_trend_data_used": False,
    }
