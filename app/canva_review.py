"""Canva-to-Instagram export helper that stops at a human review gate.

This module never publishes to Instagram. After reviewing the returned temporary
URL, the user must explicitly call the existing Instagram publishing endpoint.
"""
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.canva_api import _canva_request, require_nova_key

router = APIRouter(prefix="/canva", tags=["Canva Instagram review"])


class InstagramDraftExportRequest(BaseModel):
    design_id: str = Field(min_length=1, max_length=200, pattern=r"^[A-Za-z0-9_-]+$")
    target: Literal["post", "reel"] = "post"
    caption: str = Field(default="", max_length=2200)


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
            "inspect the export URL and approve it yourself before calling an Instagram publishing endpoint."
        ),
    }


@router.get("/instagram-draft-exports/{job_id}")
async def get_instagram_draft_export(
    job_id: str,
    _: bool = Depends(require_nova_key),
):
    """Poll Canva and return a temporary URL for manual review, not publication."""
    if not job_id or len(job_id) > 200 or not all(ch.isalnum() or ch in "_-" for ch in job_id):
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
