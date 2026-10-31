"""Direct Canva-to-Instagram Reel publishing through official APIs.

This endpoint publishes only when explicitly requested and the action flag is enabled.
It creates an MP4 export, waits a bounded time for Canva and Meta processing, then
publishes once Meta reports FINISHED. It does not attach music.
"""
import asyncio
import os
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.canva_api import _canva_request, require_nova_key
from app.security import require_user, require_master_enabled

router = APIRouter(prefix="/canva", tags=["Canva direct publishing"])


class DirectReelPublishRequest(BaseModel):
    design_id: str = Field(min_length=1, max_length=200, pattern=r"^[A-Za-z0-9_-]+$")
    caption: str = Field(default="", max_length=2200)
    share_to_feed: bool = True


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
        raise HTTPException(
            status_code=403,
            detail="Instagram publishing is disabled. Enable only after testing and authorization.",
        )


@router.post("/instagram-reels/publish")
async def publish_canva_reel_direct(
    body: DirectReelPublishRequest,
    _: bool = Depends(require_nova_key),
    __: bool = Depends(require_user),
    ___: bool = Depends(require_master_enabled),
):
    """Export a Canva design as MP4 and publish it as an Instagram Reel."""
    _require_actions_enabled()

    formats_payload = await _canva_request(
        "GET", f"designs/{body.design_id}/export-formats"
    )
    available = _available_format_types(formats_payload)
    if "mp4" not in available:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Canva does not report MP4 as available for this design.",
                "available_formats": sorted(available),
            },
        )

    export_payload = await _canva_request(
        "POST",
        "exports",
        json_body={
            "design_id": body.design_id,
            "format": {"type": "mp4", "quality": "vertical_1080p"},
        },
    )
    export_job = export_payload.get("job", {})
    export_job_id = export_job.get("id")
    if not isinstance(export_job_id, str) or not export_job_id:
        raise HTTPException(status_code=502, detail="Canva did not return an export job ID.")

    # Keep the request bounded. If Canva is still processing, no Instagram content
    # is created; the caller can retry after checking the export job.
    for attempt in range(10):
        if attempt:
            await asyncio.sleep(2)
        export_payload = await _canva_request("GET", f"exports/{export_job_id}")
        export_job = export_payload.get("job", {})
        if export_job.get("status") == "success":
            break
        if export_job.get("status") == "failed":
            raise HTTPException(
                status_code=502,
                detail={"message": "Canva export failed.", "export_job_id": export_job_id, "error": export_job.get("error")},
            )
    else:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Canva export is still processing; no Instagram Reel was created. Retry after it completes.",
                "export_job_id": export_job_id,
                "published": False,
            },
        )

    urls = export_job.get("urls", [])
    video_url = next(
        (url for url in urls if isinstance(url, str) and url.startswith("https://")),
        None,
    ) if isinstance(urls, list) else None
    if not video_url:
        raise HTTPException(status_code=502, detail="Canva did not return a usable HTTPS MP4 export URL.")

    from app.main import instagram_config, meta_request

    _, user_id, _ = instagram_config()
    container = await meta_request(
        "POST",
        f"{user_id}/media",
        data={
            "media_type": "REELS",
            "video_url": video_url,
            "caption": body.caption,
            "share_to_feed": "true" if body.share_to_feed else "false",
        },
    )
    container_id = container.get("id")
    if not container_id:
        raise HTTPException(status_code=502, detail="Meta did not return a Reel container ID.")

    # Publish only after Meta confirms processing is finished. If it takes longer
    # than this bounded wait, return the container ID so it can be checked safely.
    for attempt in range(10):
        if attempt:
            await asyncio.sleep(2)
        status_payload = await meta_request(
            "GET", container_id, params={"fields": "id,status_code,status"}
        )
        if status_payload.get("status_code") == "FINISHED":
            break
        if status_payload.get("status_code") in {"ERROR", "EXPIRED"}:
            raise HTTPException(
                status_code=502,
                detail={
                    "message": "Instagram could not process this Reel.",
                    "container_id": container_id,
                    "status_code": status_payload.get("status_code"),
                    "status": status_payload.get("status"),
                    "published": False,
                },
            )
    else:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Instagram is still processing the Reel. It was not published by this request.",
                "container_id": container_id,
                "export_job_id": export_job_id,
                "published": False,
                "next_step": f"Check GET /instagram/reels/drafts/{container_id}; publish only after status_code is FINISHED.",
            },
        )

    result = await meta_request(
        "POST",
        f"{user_id}/media_publish",
        data={"creation_id": container_id},
    )
    return {
        "design_id": body.design_id,
        "export_job_id": export_job_id,
        "container_id": container_id,
        "published": True,
        "result": result,
        "warning": "The Canva export URL is temporary and expires after 24 hours. No music was attached.",
    }
