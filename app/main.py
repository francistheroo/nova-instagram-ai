import os
import asyncio
from typing import Optional, Any
from datetime import datetime, timezone

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Depends
from pydantic import BaseModel, Field, HttpUrl

from app.personality import NOVA_SYSTEM_PROMPT
from app.ai_router import AIProviderUnavailable, chat_completion, configured_provider_names
from app.instagram_oauth import router as instagram_oauth_router
from app.ai_caption import router as ai_caption_router
from app.content_ideas import router as content_ideas_router
from app.web_ui import router as web_ui_router
from app.dm_memory import router as dm_memory_router
from app.instagram_webhook import router as instagram_webhook_router
from app.canva_oauth import router as canva_oauth_router
from app.canva_api import router as canva_api_router
from app.canva_review import router as canva_review_router
from app.canva_direct_publish import router as canva_direct_publish_router
from app.canva_direct_post import router as canva_direct_post_router
from app.instagram_reels import router as instagram_reels_router
from app.oauth_store import load_instagram_token, load_latest_instagram_token, OAuthStoreError
from app.admin import router as admin_router
from app.auto_publisher import scheduler_loop, initialize_scheduler_schema
from app.security import require_user, require_master_enabled, master_enabled

load_dotenv()
app = FastAPI(title="NOVA Instagram AI", version="0.3.0")
app.include_router(instagram_oauth_router)
app.include_router(ai_caption_router, dependencies=[Depends(require_user), Depends(require_master_enabled)])
app.include_router(content_ideas_router, dependencies=[Depends(require_user), Depends(require_master_enabled)])
app.include_router(web_ui_router, dependencies=[Depends(require_user)])
app.include_router(dm_memory_router)
app.include_router(instagram_webhook_router)
app.include_router(canva_oauth_router)
app.include_router(canva_api_router)
app.include_router(canva_review_router)
app.include_router(canva_direct_publish_router, dependencies=[Depends(require_user), Depends(require_master_enabled)])
app.include_router(canva_direct_post_router, dependencies=[Depends(require_user), Depends(require_master_enabled)])
app.include_router(instagram_reels_router, dependencies=[Depends(require_user), Depends(require_master_enabled)])
app.include_router(admin_router)


@app.on_event("startup")
async def start_auto_publisher():
    # The durable scheduler is opt-in and never starts from an API request.
    if os.getenv("NOVA_SCHEDULER_ENABLED", "false").lower() == "true":
        from app.auto_publisher import initialize_scheduler_schema
        try:
            initialize_scheduler_schema()
            app.state.nova_scheduler_stop = asyncio.Event()
            app.state.nova_scheduler_task = asyncio.create_task(
                scheduler_loop(meta_request, instagram_config, app.state.nova_scheduler_stop)
            )
        except Exception:
            # Keep the API available; /health reports scheduler readiness separately.
            app.state.nova_scheduler_error = "scheduler_initialization_failed"


@app.on_event("shutdown")
async def stop_auto_publisher():
    stop = getattr(app.state, "nova_scheduler_stop", None)
    task = getattr(app.state, "nova_scheduler_task", None)
    if stop is not None:
        stop.set()
    if task is not None:
        await task


class ReplyRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    language_hint: Optional[str] = Field(default=None, max_length=30)


class CommentReplyRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2200)


class PublishImageRequest(BaseModel):
    image_url: HttpUrl
    caption: str = Field(default="", max_length=2200)


class MessageReplyRequest(BaseModel):
    recipient_id: str = Field(min_length=1, max_length=200)
    message: str = Field(min_length=1, max_length=1000)


class ImageGenerationRequest(BaseModel):
    prompt: str = Field(min_length=3, max_length=2000)
    size: str = Field(default="1024x1024", pattern=r"^(1024x1024|1024x1536|1536x1024)$")


def require_nova_key(x_nova_api_key: Optional[str] = Header(default=None)):
    expected = os.getenv("NOVA_API_KEY", "")
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="Set NOVA_API_KEY in Render environment variables before using action endpoints.",
        )
    if not x_nova_api_key or x_nova_api_key != expected:
        raise HTTPException(status_code=401, detail="Missing or invalid X-NOVA-API-Key.")
    return True


def instagram_config():
    token = os.getenv("INSTAGRAM_ACCESS_TOKEN", "").strip()
    user_id = os.getenv("INSTAGRAM_USER_ID", "").strip()
    if token and user_id:
        base = os.getenv("META_GRAPH_BASE_URL", "https://graph.instagram.com").rstrip("/")
        version = os.getenv("META_API_VERSION", "v25.0").strip("/")
        return token, user_id, f"{base}/{version}"

    # OAuth-connected credentials are read from encrypted PostgreSQL storage.
    try:
        stored = load_instagram_token(user_id) if user_id else load_latest_instagram_token()
    except OAuthStoreError:
        stored = None
    except Exception:
        stored = None
    if stored:
        expiry = stored.get("expires_at")
        if expiry is not None and expiry <= datetime.now(timezone.utc):
            raise HTTPException(status_code=503, detail="Instagram access token has expired. Reconnect Instagram; automatic refresh is not implemented yet.")
        token = stored["access_token"]
        user_id = user_id or stored["instagram_user_id"]

    if not token or not user_id:
        raise HTTPException(
            status_code=503,
            detail="Instagram is not connected yet. Configure OAuth and PostgreSQL, or set INSTAGRAM_ACCESS_TOKEN and INSTAGRAM_USER_ID in Render.",
        )
    base = os.getenv("META_GRAPH_BASE_URL", "https://graph.instagram.com").rstrip("/")
    version = os.getenv("META_API_VERSION", "v25.0").strip("/")
    return token, user_id, f"{base}/{version}"

async def meta_request(method: str, path: str, *, params: Optional[dict] = None, data: Optional[dict] = None) -> dict[str, Any]:
    token, _, graph_base = instagram_config()
    request_params = dict(params or {})
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.request(
            method,
            f"{graph_base}/{path.lstrip('/')}",
            params=request_params,
            data=data,
            headers=headers,
        )
    try:
        payload = response.json()
    except ValueError:
        payload = {"detail": response.text[:1000]}
    if response.is_error:
        error = payload.get("error", payload) if isinstance(payload, dict) else payload
        raise HTTPException(status_code=response.status_code, detail={"instagram_api_error": error})
    return payload


@app.get("/")
async def root():
    return {
        "service": "NOVA Instagram AI",
        "status": "online",
        "docs": "/docs",
        "note": "AI preview works separately. Instagram actions require official Meta authorization and environment configuration.",
    }


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "NOVA Instagram AI",
        # These compatibility flags report environment presence/code paths, not live verification.
        "instagram_configured": bool(os.getenv("INSTAGRAM_ACCESS_TOKEN", "").strip() and os.getenv("INSTAGRAM_USER_ID", "").strip()),
        "instagram_manual_credentials_present": bool(os.getenv("INSTAGRAM_ACCESS_TOKEN", "").strip() and os.getenv("INSTAGRAM_USER_ID", "").strip()),
        "instagram_live_connection_verified": False,
        "instagram_oauth_implemented": True,
        "instagram_token_refresh_implemented": True,
        "instagram_manual_token_refresh_implemented": True,
        "instagram_automatic_token_refresh_implemented": False,
        "instagram_webhooks_implemented": True,
        "instagram_webhook_receiver_implemented": True,
        "instagram_webhook_verification_route_implemented": True,
        "instagram_webhook_subscription_automated": False,
        "instagram_automation_enabled": os.getenv("INSTAGRAM_AUTOMATION_ENABLED", "false").lower() == "true",
        "auto_scheduler_enabled": os.getenv("NOVA_SCHEDULER_ENABLED", "false").lower() == "true",
        "ai_master_enabled": master_enabled(),
        "auto_scheduler_running": hasattr(app.state, "nova_scheduler_task"),
        "instagram_auto_dm_replies_enabled": os.getenv("INSTAGRAM_AUTO_DM_REPLIES_ENABLED", "false").lower() == "true",
        "ai_configured": bool(configured_provider_names()),
        "ai_providers_configured": configured_provider_names(),
        "image_generation_configured": bool(os.getenv("IMAGE_API_BASE_URL", "").strip() and os.getenv("IMAGE_API_KEY", "").strip() and os.getenv("IMAGE_MODEL", "").strip()),
        "canva_configured": bool(os.getenv("CANVA_CLIENT_ID", "").strip() and os.getenv("CANVA_CLIENT_SECRET", "").strip()),
        "canva_live_connection_verified": False,
        "canva_oauth_implemented": True,
        "canva_token_refresh_implemented": True,
        "canva_manual_token_refresh_implemented": True,
        "canva_automatic_token_refresh_implemented": False,
        "notes_music_supported": False,
        "instagram_like_actions_supported": False,
    }


@app.get("/integrations/status")
async def integrations_status():
    """Report environment readiness only; this does not validate live credentials."""
    env = os.getenv
    instagram_oauth_configured = all(env(key, "").strip() for key in (
        "INSTAGRAM_OAUTH_CLIENT_ID", "INSTAGRAM_OAUTH_CLIENT_SECRET",
        "INSTAGRAM_OAUTH_REDIRECT_URI", "OAUTH_STATE_SECRET", "TOKEN_ENCRYPTION_KEY",
        "DATABASE_URL",
    ))
    canva_oauth_configured = all(env(key, "").strip() for key in (
        "CANVA_CLIENT_ID", "CANVA_CLIENT_SECRET", "CANVA_REDIRECT_URI",
        "OAUTH_STATE_SECRET", "TOKEN_ENCRYPTION_KEY", "DATABASE_URL",
    ))
    return {
        "service": "NOVA Instagram AI",
        "checks_are_configuration_only": True,
        "live_account_verification": "not_performed",
        "nova_api_key_configured": bool(env("NOVA_API_KEY", "").strip()),
        "database_configured": bool(env("DATABASE_URL", "").strip()),
        "instagram": {
            "manual_credentials_present": bool(env("INSTAGRAM_ACCESS_TOKEN", "").strip() and env("INSTAGRAM_USER_ID", "").strip()),
            "oauth_environment_ready": instagram_oauth_configured,
            "publishing_enabled": env("INSTAGRAM_AUTOMATION_ENABLED", "false").lower() == "true",
        },
        "canva": {
            "oauth_environment_ready": canva_oauth_configured,
            "direct_photo_publish_route_implemented": True,
            "direct_reel_publish_route_implemented": True,
        },
        "ai": {
            "text_provider_configured": bool(configured_provider_names()),
            "text_providers_configured": configured_provider_names(),
            "image_provider_configured": bool(env("IMAGE_API_BASE_URL", "").strip() and env("IMAGE_API_KEY", "").strip() and env("IMAGE_MODEL", "").strip()),
        },
        "warning": "Configured variables do not prove that credentials are valid, permissions are approved, or external services are connected.",
    }


@app.post("/preview-reply")
async def preview_reply(body: ReplyRequest, _: bool = Depends(require_user), __: bool = Depends(require_master_enabled)):
    """Generate a reply preview. This endpoint does not send anything to Instagram."""
    if not configured_provider_names():
        return {
            "reply": (
                "NOVA AI: Enikku Manglish, Malayalam, English okke handle cheyyan "
                "designed aanu 😄 AI provider connect cheythal njan natural reply "
                "generate cheyyum. This is only a preview; nothing was sent."
            ),
            "mode": "fallback",
            "sent_to_instagram": False,
        }

    user_message = body.message
    if body.language_hint:
        user_message += f"\\n\\nLanguage preference hint: {body.language_hint}"
    try:
        reply, provider, model = await chat_completion(
            [
                {"role": "system", "content": NOVA_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=0.8,
        )
    except AIProviderUnavailable:
        raise HTTPException(status_code=503, detail="All configured AI providers are unavailable or rate-limited. Try again later.") from None
    return {
        "reply": reply,
        "mode": "ai",
        "provider": provider,
        "model": model,
        "sent_to_instagram": False,
    }


@app.get("/instagram/verify")
async def verify_instagram_connection(_: bool = Depends(require_nova_key)):
    """Verify configured credentials against Meta and return the authorized profile identity."""
    _, user_id, _ = instagram_config()
    profile = await meta_request("GET", user_id, params={"fields": "id,username"})
    if not isinstance(profile, dict) or not profile.get("id"):
        raise HTTPException(status_code=502, detail="Meta did not return a valid Instagram profile response.")
    return {"connected": True, "profile_id": str(profile["id"]), "username": profile.get("username")}


@app.get("/instagram/media")
async def list_instagram_media(_: bool = Depends(require_nova_key)):
    """List media available to the authorized Instagram professional account."""
    _, user_id, _ = instagram_config()
    return await meta_request(
        "GET",
        f"{user_id}/media",
        params={"fields": "id,caption,media_type,media_url,permalink,timestamp,like_count,comments_count", "limit": "25"},
    )


@app.get("/instagram/media/{media_id}/comments")
async def list_comments(media_id: str, _: bool = Depends(require_nova_key)):
    return await meta_request(
        "GET",
        f"{media_id}/comments",
        params={"fields": "id,text,timestamp,username", "limit": "50"},
    )


@app.post("/instagram/comments/{comment_id}/reply")
async def reply_to_comment(comment_id: str, body: CommentReplyRequest, _: bool = Depends(require_nova_key)):
    if os.getenv("INSTAGRAM_AUTOMATION_ENABLED", "false").lower() != "true":
        raise HTTPException(status_code=403, detail="Instagram actions are disabled. Set INSTAGRAM_AUTOMATION_ENABLED=true only after testing and authorization.")
    return await meta_request("POST", f"{comment_id}/replies", data={"message": body.message})


@app.post("/instagram/messages/reply")
async def reply_to_message(body: MessageReplyRequest, _: bool = Depends(require_nova_key)):
    """Send a reply to an eligible Instagram-scoped recipient ID after Meta messaging authorization."""
    if os.getenv("INSTAGRAM_AUTOMATION_ENABLED", "false").lower() != "true":
        raise HTTPException(status_code=403, detail="Instagram actions are disabled. Enable only after testing and authorization.")
    _, user_id, _ = instagram_config()
    return await meta_request(
        "POST",
        f"{user_id}/messages",
        data={
            "recipient": __import__("json").dumps({"id": body.recipient_id}),
            "message": __import__("json").dumps({"text": body.message}),
        },
    )


@app.post("/instagram/publish-image")
async def publish_image(body: PublishImageRequest, _: bool = Depends(require_nova_key), __: bool = Depends(require_user), ___: bool = Depends(require_master_enabled)):
    """Publish a publicly reachable image URL using Instagram's content publishing flow."""
    if os.getenv("INSTAGRAM_AUTOMATION_ENABLED", "false").lower() != "true":
        raise HTTPException(status_code=403, detail="Publishing is disabled. Set INSTAGRAM_AUTOMATION_ENABLED=true only after an authorized test.")
    _, user_id, _ = instagram_config()
    container = await meta_request(
        "POST",
        f"{user_id}/media",
        data={"image_url": str(body.image_url), "caption": body.caption, "media_type": "IMAGE"},
    )
    creation_id = container.get("id")
    if not creation_id:
        raise HTTPException(status_code=502, detail={"message": "Instagram did not return a media container ID", "response": container})
    published = await meta_request(
        "POST",
        f"{user_id}/media_publish",
        data={"creation_id": creation_id},
    )
    return {"container": container, "published": published, "status": "published_if_confirmed_by_meta"}


@app.post("/ai/generate-image")
async def generate_image(body: ImageGenerationRequest, _: bool = Depends(require_nova_key), __: bool = Depends(require_user), ___: bool = Depends(require_master_enabled)):
    """Call a separately configured OpenAI-compatible image-generation API."""
    base_url = os.getenv("IMAGE_API_BASE_URL", "").rstrip("/")
    api_key = os.getenv("IMAGE_API_KEY", "")
    model = os.getenv("IMAGE_MODEL", "")
    if not (base_url and api_key and model):
        raise HTTPException(status_code=503, detail="Image generation is not configured. Add IMAGE_API_BASE_URL, IMAGE_API_KEY, and IMAGE_MODEL in Render.")
    async with httpx.AsyncClient(timeout=90.0) as client:
        response = await client.post(
            f"{base_url}/images/generations",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"model": model, "prompt": body.prompt, "size": body.size, "n": 1},
        )
    if response.is_error:
        raise HTTPException(status_code=502, detail="Image provider request failed. Check its API compatibility and Render settings.")
    payload = response.json()
    return {"provider_response": payload, "note": "A returned image URL must be publicly accessible to Instagram before publishing."}


@app.get("/canva/status")
async def canva_status():
    """Report configuration and implementation status without exposing credentials."""
    return {
        "configured": bool(os.getenv("CANVA_CLIENT_ID") and os.getenv("CANVA_CLIENT_SECRET")),
        "oauth_implemented": True,
        "design_listing_implemented": True,
        "export_implemented": True,
        "token_refresh_implemented": True,
        "message": "Canva OAuth, manual token refresh, design listing, export-format lookup, and asynchronous export routes are implemented in code. A configured Canva app and live verification are still required.",
    }
