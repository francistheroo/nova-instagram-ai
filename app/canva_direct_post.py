"""Deprecated direct Canva photo publishing route.

Publishing must go through the separate draft/review workflow. This legacy
endpoint is intentionally non-operational and must never call Canva or Meta.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.canva_api import require_nova_key
from app.security import require_user, require_master_enabled

router = APIRouter(prefix="/canva", tags=["Canva direct publishing"])


class DirectPostPublishRequest(BaseModel):
    design_id: str = Field(min_length=1, max_length=200, pattern=r"^[A-Za-z0-9_-]+$")
    caption: str = Field(default="", max_length=2200)


@router.post("/instagram-posts/publish")
async def publish_canva_photo_direct(
    body: DirectPostPublishRequest,
    _: bool = Depends(require_nova_key),
    __: bool = Depends(require_user),
    ___: bool = Depends(require_master_enabled),
):
    """Reject legacy direct publishing; require reviewed draft workflow."""
    raise HTTPException(
        status_code=410,
        detail={
            "message": "Direct Canva publishing is disabled. Create and review a draft, then use the explicit approved publishing workflow.",
            "published": False,
            "review_required": True,
        },
    )
