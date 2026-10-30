"""Direct Canva-to-Instagram photo-post publishing via official APIs."""
import asyncio
import os
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.canva_api import _canva_request, require_nova_key
from app.security import require_user, require_master_enabled

router = APIRouter(prefix="/canva", tags=["Canva direct publishing"])


class DirectPostPublishRequest(BaseModel):
    design_id: str = Field(min_length=1, max_length=200, pattern=r"^[A-Za-z0-9_-]+$")
    caption: str = Field(default="", max_length=2200)


def _available_format_types(payload: Any) -> set[str]:
    found: set[str] = set()
    def visit(value: Any) -> None:
        if isinstance(value, dict):
            kind = value.get("type")
            if isinstance(kind, str):
                found.add(kind.lower())
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)
    visit(payload)
    return found


def _require_actions_enabled() -> None:
    if os.getenv("INSTAGRAM_AUTOMATION_ENABLED", "false").lower() != "true":
        raise HTTPException(status_code=403, detail="Instagram publishing is disabled. Enable only after testing and authorization.")


@router.post("/instagram-posts/publish")
async def publish_canva_photo_direct(
    body: DirectPostPublishRequest,
    _: bool = Depends(require_nova_key),
    __: bool = Depends(require_user),
):
    """Export a Canva design as PNG and publish it as an Instagram photo post."""
    _require_actions_enabled()
    require_master_enabled()
    formats_payload = await _canva_request("GET", f"designs/{body.design_id}/export-formats")
    available = _available_format_types(formats_payload)
    if "png" not in available:
        raise HTTPException(
            status_code=422,
            detail={"message": "Canva does not report PNG as available for this design.", "available_formats": sorted(available)},
        )

    export_payload = await _canva_request(
        "POST", "exports",
        json_body={"design_id": body.design_id, "format": {"type": "png"}},
    )
    export_job = export_payload.get("job", {})
    export_job_id = export_job.get("id")
    if not isinstance(export_job_id, str) or not export_job_id:
        raise HTTPException(status_code=502, detail="Canva did not return an export job ID.")

    for attempt in range(10):
        if attempt:
            await asyncio.sleep(2)
        export_payload = await _canva_request("GET", f"exports/{export_job_id}")
        export_job = export_payload.get("job", {})
        if export_job.get("status") == "success":
            break
        if export_job.get("status") == "failed":
            raise HTTPException(status_code=502, detail={"message": "Canva PNG export failed.", "export_job_id": export_job_id, "error": export_job.get("error")})
    else:
        raise HTTPException(status_code=409, detail={"message": "Canva export is still processing; no Instagram post was created.", "export_job_id": export_job_id, "published": False})

    urls = export_job.get("urls", [])
    image_url = next((url for url in urls if isinstance(url, str) and url.startswith("https://")), None) if isinstance(urls, list) else None
    if not image_url:
        raise HTTPException(status_code=502, detail="Canva did not return a usable HTTPS PNG export URL.")

    from app.main import instagram_config, meta_request
    _, user_id, _ = instagram_config()
    container = await meta_request(
        "POST", f"{user_id}/media",
        data={"image_url": image_url, "caption": body.caption, "media_type": "IMAGE"},
    )
    container_id = container.get("id")
    if not container_id:
        raise HTTPException(status_code=502, detail="Meta did not return an image container ID.")

    published = await meta_request(
        "POST", f"{user_id}/media_publish",
        data={"creation_id": container_id},
    )
    if not published.get("id"):
        raise HTTPException(status_code=502, detail={"message": "Instagram did not confirm the published media ID.", "container_id": container_id, "published": False})
    return {
        "design_id": body.design_id,
        "export_job_id": export_job_id,
        "container_id": container_id,
        "published_media_id": published["id"],
        "published": True,
        "warning": "The Canva export URL is temporary and expires after 24 hours.",
    }
