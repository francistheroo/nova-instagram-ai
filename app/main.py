import os
from typing import Optional

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel, Field

from app.personality import NOVA_SYSTEM_PROMPT

load_dotenv()
app = FastAPI(title="NOVA Instagram AI", version="0.1.0")


class ReplyRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    language_hint: Optional[str] = Field(default=None, max_length=30)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "NOVA Instagram AI",
        "instagram_automation_enabled": os.getenv(
            "INSTAGRAM_AUTOMATION_ENABLED", "false"
        ).lower() == "true",
        "ai_configured": bool(
            os.getenv("AI_BASE_URL")
            and os.getenv("AI_API_KEY")
            and os.getenv("AI_MODEL")
        ),
    }


@app.post("/preview-reply")
async def preview_reply(body: ReplyRequest):
    """Generate a reply preview. This endpoint does not send anything to Instagram."""
    base_url = os.getenv("AI_BASE_URL", "").rstrip("/")
    api_key = os.getenv("AI_API_KEY", "")
    model = os.getenv("AI_MODEL", "")

    if not (base_url and api_key and model):
        return {
            "reply": (
                "NOVA AI: Enikku Manglish, Malayalam, English okke handle cheyyan "
                "designed aanu 😄 AI provider connect cheythal njan natural reply "
                "generate cheyyum. This is only a preview; nothing was sent."
            ),
            "mode": "fallback",
            "sent_to_instagram": False,
        }

    # OpenAI-compatible chat completions endpoint. Configure base URL to the
    # provider's documented API root, typically ending in /v1.
    url = f"{base_url}/chat/completions"
    user_message = body.message
    if body.language_hint:
        user_message += f"\n\nLanguage preference hint: {body.language_hint}"

    async with httpx.AsyncClient(timeout=45.0) as client:
        response = await client.post(
            url,
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": NOVA_SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                "temperature": 0.8,
            },
        )
        response.raise_for_status()
        data = response.json()

    reply = data["choices"][0]["message"]["content"]
    return {
        "reply": reply,
        "mode": "ai",
        "sent_to_instagram": False,
    }
