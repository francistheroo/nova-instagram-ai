"""Canva-to-Instagram export helper with a deliberate review gate.

Exports are temporary. This module can create an Instagram Reel container from a
successful Canva MP4 export, but never publishes it.
"""
import os
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.canva_api import _canva_request, require_nova_key
from app.security import require_user, require_master_enabled

router = APIRouter(prefix="/canva", tags=["Canva Instagram review"], dependencies=[Depends(require_user)])


class InstagramDraftExportRequest(BaseModel):
    design_id: str = Field(min_length=1, max_length=200, pattern=r"^[A-Za-z0-9_-]+$")
    target: Literal["post", "reel"] = "post"
    caption: str = Field(default="", max_length=2200)


class CreateInstagramReelFromExportRequest(BaseModel):
    caption: str = Field(default="", max_length=2200)
    share_to_feed: bool = True


def _available_format_types(payload: Any) -> set[str]:
    """Extract export type names from Canva's export-formats response."""
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


def _valid_job_id(job_id: str) -> bool:
    return bool(job_id) and len(job_id) <= 200 and all(
        ch.isalnum() or ch in "_-" for ch in job_id
    )


@router.post("/instagram-draft-exports")
async def create_instagram_draft_export(
    body: InstagramDraftExportRequest,
    _: bool = Depends(require_nova_key),
):
    """Check format support, then start an export for review; never publish."""
    export_format = {"type": "png"} if body.target == "post" else {
        "type": "mp4",
        "quality": "vertical_1080p",
    }

    formats_payload = await _canva_request(
        "GET", f"designs/{body.design_id}/export-formats"
    )
    wanted = export_format["type"]
    available = _available_format_types(formats_payload)
    if wanted not in available:
        raise HTTPException(
            status_code=422,
            detail={
                "message": f"Canva does not report {wanted.upper()} as an available export format for this design.",
                "available_formats": sorted(available),
                "target": body.target,
            },
        )

    job_payload = await _canva_request(
        "POST",
        "exports",
        json_body={"design_id": body.design_id, "format": export_format},
    )
    job = job_payload.get("job", {})
    return {
        "target": body.target,
        "caption": body.caption,
        "available_formats_checked": True,
        "export": job_payload,
        "review_required": True,
        "published": False,
        "next_step": (
            f"Poll GET /canva/instagram-draft-exports/{job.get('id', '<job_id>')}; "
            "review the export before using the separate Reel-draft creation endpoint."
        ),
    }


@router.get("/instagram-draft-exports/{job_id}")
async def get_instagram_draft_export(
    job_id: str,
    _: bool = Depends(require_nova_key),
):
    """Poll Canva and return a temporary URL for manual review, not publication."""
    if not _valid_job_id(job_id):
        raise HTTPException(status_code=422, detail="Invalid Canva export job ID.")
    payload = await _canva_request("GET", f"exports/{job_id}")
    job = payload.get("job", {})
    status = job.get("status")
    urls = job.get("urls", []) if status == "success" else []
    return {
        "job_id": job.get("id", job_id),
        "status": status,
        "preview_urls": urls,
        "review_required": True,
        "published": False,
        "warning": "Canva export URLs expire after 24 hours. Review the media and caption before manually approving publication.",
        "error": job.get("error") if status == "failed" else None,
    }


@router.post("/instagram-reel-drafts/{job_id}", dependencies=[Depends(require_master_enabled)])
async def create_instagram_reel_draft_from_canva_export(
    job_id: str,
    body: CreateInstagramReelFromExportRequest,
    _: bool = Depends(require_nova_key),
):
    """Turn a completed Canva MP4 export into an Instagram Reel container, never publish."""
    if not _valid_job_id(job_id):
        raise HTTPException(status_code=422, detail="Invalid Canva export job ID.")
    if os.getenv("INSTAGRAM_AUTOMATION_ENABLED", "false").lower() != "true":
        raise HTTPException(
            status_code=403,
            detail="Instagram actions are disabled. Enable only after testing and authorization.",
        )

    export_payload = await _canva_request("GET", f"exports/{job_id}")
    job = export_payload.get("job", {})
    if job.get("status") != "success":
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Canva export is not ready. Wait for a successful MP4 export.",
                "status": job.get("status"),
            },
        )

    urls = job.get("urls", [])
    video_url = next(
        (url for url in urls if isinstance(url, str) and url.startswith("https://")),
        None,
    ) if isinstance(urls, list) else None
    if not video_url:
        raise HTTPException(
            status_code=502,
            detail="Canva did not return a usable HTTPS export URL.",
        )

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
        raise HTTPException(
            status_code=502,
            detail={"message": "Meta did not return a Reel container ID.", "response": container},
        )
    return {
        "canva_export_job_id": job_id,
        "container_id": container_id,
        "status": "created",
        "published": False,
        "review_required": True,
        "warning": "The Canva export URL expires after 24 hours. Meta must fetch it before expiry. Review the Reel and caption; publish separately only after Meta reports FINISHED.",
        "next_step": f"GET /instagram/reels/drafts/{container_id} to check processing. Publication is a separate explicit action.",
    }
