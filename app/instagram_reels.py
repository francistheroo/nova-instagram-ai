"""Instagram Reel publishing with a deliberate create -> status -> publish flow.

Creating a container never publishes. Publication only happens through the separate
protected publish endpoint after Meta reports the container is FINISHED.
"""
import os
import re

from fastapi import APIRouter, Depends, Header, HTTPException

from app.security import require_user, require_master_enabled
from pydantic import BaseModel, Field, HttpUrl

router = APIRouter(prefix="/instagram/reels", tags=["Instagram Reels"])
_CONTAINER_ID = re.compile(r"^[A-Za-z0-9_-]{1,200}$")


def _require_nova_key(x_nova_api_key: str | None = Header(default=None)):
    expected = os.getenv("NOVA_API_KEY", "")
    if not expected:
        raise HTTPException(status_code=503, detail="NOVA_API_KEY is not configured.")
    if not x_nova_api_key or not __import__("hmac").compare_digest(x_nova_api_key, expected):
        raise HTTPException(status_code=401, detail="Missing or invalid X-NOVA-API-Key.")
    return True


def _require_actions_enabled():
    if os.getenv("INSTAGRAM_AUTOMATION_ENABLED", "false").lower() != "true":
        raise HTTPException(
            status_code=403,
            detail="Instagram actions are disabled. Enable only after testing and authorization.",
        )


class ReelDraftRequest(BaseModel):
    video_url: HttpUrl
    caption: str = Field(default="", max_length=2200)
    share_to_feed: bool = True


@router.post("/drafts")
async def create_reel_draft(body: ReelDraftRequest, _: bool = Depends(_require_nova_key), __: bool = Depends(require_user), ___: bool = Depends(require_master_enabled)):
    """Create a Meta video container for review; this endpoint never publishes."""
    if body.video_url.scheme != "https":
        raise HTTPException(status_code=422, detail="video_url must use HTTPS.")
    _require_actions_enabled()
    from app.main import instagram_config, meta_request

    _, user_id, _ = instagram_config()
    payload = await meta_request(
        "POST",
        f"{user_id}/media",
        data={
            "media_type": "REELS",
            "video_url": str(body.video_url),
            "caption": body.caption,
            "share_to_feed": "true" if body.share_to_feed else "false",
        },
    )
    container_id = payload.get("id")
    if not container_id:
        raise HTTPException(status_code=502, detail={"message": "Meta did not return a Reel container ID.", "response": payload})
    return {
        "container_id": container_id,
        "status": "created",
        "published": False,
        "review_required": True,
        "next_step": f"Check GET /instagram/reels/drafts/{container_id}; publish only after Meta reports FINISHED and you approve.",
    }


@router.get("/drafts/{container_id}")
async def get_reel_draft_status(container_id: str, _: bool = Depends(_require_nova_key), __: bool = Depends(require_user)):
    """Read Meta's processing status without publishing the Reel."""
    if not _CONTAINER_ID.fullmatch(container_id):
        raise HTTPException(status_code=422, detail="Invalid Reel container ID.")
    from app.main import meta_request

    payload = await meta_request(
        "GET",
        container_id,
        params={"fields": "id,status_code,status"},
    )
    return {
        "container_id": payload.get("id", container_id),
        "status_code": payload.get("status_code"),
        "status": payload.get("status"),
        "published": False,
        "publish_allowed": payload.get("status_code") == "FINISHED",
    }


@router.post("/drafts/{container_id}/publish")
async def publish_reel_draft(container_id: str, _: bool = Depends(_require_nova_key), __: bool = Depends(require_user), ___: bool = Depends(require_master_enabled)):
    """Explicitly publish a reviewed Reel only when Meta says its container is ready."""
    if not _CONTAINER_ID.fullmatch(container_id):
        raise HTTPException(status_code=422, detail="Invalid Reel container ID.")
    _require_actions_enabled()
    from app.main import instagram_config, meta_request

    _, user_id, _ = instagram_config()
    status_payload = await meta_request(
        "GET",
        container_id,
        params={"fields": "id,status_code,status"},
    )
    if status_payload.get("status_code") != "FINISHED":
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Reel is not ready to publish. Meta must report FINISHED first.",
                "status_code": status_payload.get("status_code"),
                "status": status_payload.get("status"),
            },
        )
    result = await meta_request(
        "POST",
        f"{user_id}/media_publish",
        data={"creation_id": container_id},
    )
    return {"container_id": container_id, "published": True, "result": result}
