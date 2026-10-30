"""Protected server-side Canva Connect API endpoints for designs and exports."""
import os
import hmac
from typing import Any

import httpx
import psycopg
from fastapi import APIRouter, Depends, Header, HTTPException, Query

from app.security import require_user
from pydantic import BaseModel, Field

from app.canva_store import CanvaStoreError, load_latest_canva_tokens

router = APIRouter(prefix="/canva", tags=["Canva Connect API"])


def require_nova_key(x_nova_api_key: str | None = Header(default=None)):
    expected = os.getenv("NOVA_API_KEY", "")
    if not expected:
        raise HTTPException(status_code=503, detail="Set NOVA_API_KEY in server environment before using Canva action endpoints.")
    if not x_nova_api_key or not hmac.compare_digest(x_nova_api_key, expected):
        raise HTTPException(status_code=401, detail="Missing or invalid X-NOVA-API-Key.")
    return True


class CanvaExportRequest(BaseModel):
    design_id: str = Field(min_length=1, max_length=200, pattern=r"^[A-Za-z0-9_-]+$")
    format: str = Field(default="png", pattern=r"^(png|jpg|pdf|gif|pptx|mp4|csv|html_bundle|html_standalone)$")


def _canva_token() -> str:
    try:
        bundle = load_latest_canva_tokens()
    except (CanvaStoreError, psycopg.Error):
        raise HTTPException(status_code=503, detail="Canva token storage is unavailable or could not be decrypted.") from None
    if not bundle:
        raise HTTPException(status_code=503, detail="Canva is not connected. Complete /oauth/canva/start first.")
    expiry = bundle.get("expires_at")
    if expiry is not None:
        from datetime import datetime, timezone
        if expiry <= datetime.now(timezone.utc):
            raise HTTPException(status_code=503, detail="Canva access token has expired. Reconnect Canva; automatic refresh is not implemented.")
    token = bundle.get("access_token")
    if not isinstance(token, str) or not token:
        raise HTTPException(status_code=503, detail="Stored Canva token is invalid.")
    return token


async def _canva_request(method: str, path: str, *, params: dict[str, Any] | None = None, json_body: dict[str, Any] | None = None) -> dict[str, Any]:
    token = _canva_token()
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.request(
            method,
            f"https://api.canva.com/rest/v1/{path.lstrip('/')}",
            params=params,
            json=json_body,
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        )
    try:
        payload = response.json()
    except ValueError:
        payload = {"detail": "Canva returned a non-JSON response."}
    if response.is_error:
        # Do not return authorization headers or any token material.
        raise HTTPException(status_code=response.status_code, detail={"canva_api_error": payload if isinstance(payload, dict) else {"message": str(payload)[:500]}})
    if not isinstance(payload, dict):
        raise HTTPException(status_code=502, detail="Canva returned an unexpected response.")
    return payload


@router.get("/designs")
async def list_canva_designs(
    query: str | None = Query(default=None, max_length=255),
    continuation: str | None = Query(default=None, max_length=2048),
    limit: int = Query(default=25, ge=1, le=100),
    _: bool = Depends(require_nova_key),
    __: bool = Depends(require_user),
):
    """List designs available to the connected Canva user."""
    params: dict[str, Any] = {"limit": limit, "sort_by": "modified_descending"}
    if query:
        params["query"] = query
    if continuation:
        params["continuation"] = continuation
    return await _canva_request("GET", "designs", params=params)


@router.get("/designs/{design_id}/export-formats")
async def canva_export_formats(
    design_id: str,
    _: bool = Depends(require_nova_key),
    __: bool = Depends(require_user),
):
    """Return formats Canva says are available for this design."""
    if not design_id or len(design_id) > 200 or not all(ch.isalnum() or ch in "_-" for ch in design_id):
        raise HTTPException(status_code=422, detail="Invalid Canva design ID.")
    return await _canva_request("GET", f"designs/{design_id}/export-formats")


@router.post("/exports")
async def create_canva_export(
    body: CanvaExportRequest,
    _: bool = Depends(require_nova_key),
    __: bool = Depends(require_user),
):
    """Start an asynchronous export job; this does not download the file."""
    return await _canva_request(
        "POST",
        "exports",
        json_body={"design_id": body.design_id, "format": {"type": body.format}},
    )


@router.get("/exports/{job_id}")
async def get_canva_export(
    job_id: str,
    _: bool = Depends(require_nova_key),
    __: bool = Depends(require_user),
):
    """Check an export job; Canva download URLs are temporary and must be handled securely."""
    if not job_id or len(job_id) > 200 or not all(ch.isalnum() or ch in "_-" for ch in job_id):
        raise HTTPException(status_code=422, detail="Invalid Canva export job ID.")
    return await _canva_request("GET", f"exports/{job_id}")
